# Spec 057 Q138 replacement: reviewed local preview only; never supplies arming.
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$PinSha,
    [string]$RepoRoot='C:\GitHub\Quant-ML-Bot',
    [string]$DataRoot='C:\QMB\Fidelity',
    [string]$Python='C:\QMB\Fidelity\venv312\Scripts\python.exe',
    [switch]$CheckPinOnly
)
$ErrorActionPreference='Stop'
$StateRoot=Join-Path $DataRoot 'state'
if (Test-Path -LiteralPath (Join-Path $StateRoot 'KILL')) { throw 'KILL present; no preview started.' }
if (Test-Path -LiteralPath (Join-Path $StateRoot 'HALTED')) { throw 'HALTED present; Camden review required. Never delete it.' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Reviewed Python runtime missing.' }

# One public GitHub tree request and a main-ancestry check. No Git process or broker.
$PinGuard=@'
import base64,hashlib,json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(); pin=sys.argv[2]
def api(path):
 p=subprocess.run(['gh','api',path],capture_output=True,text=True,check=True)
 return json.loads(p.stdout)
try:
 tree=api('repos/cstroh01/Quant-ML-Bot/git/trees/'+pin+'?recursive=1')
 assert not tree.get('truncated')
 status=api('repos/cstroh01/Quant-ML-Bot/compare/'+pin+'...main')['status']
 assert status in ('ahead','identical')
 expected={row['path']:row['sha'] for row in tree['tree'] if row['type']=='blob'
           and row['path'].startswith(('scripts/','exec/')) and row['path'].endswith(('.py','.ps1'))}
 actual={p.relative_to(root).as_posix() for folder in ('scripts','exec') for p in (root/folder).rglob('*')
         if p.suffix in ('.py','.ps1') and '__pycache__' not in p.parts}
 assert set(expected)==actual
 for name,sha in expected.items():
  raw=(root/name).read_bytes(); body=raw.replace(b'\r\n',b'\n')
  variants=(raw,body,body.replace(b'\n',b'\r\n'))
  if sha not in {hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest() for value in variants}:
   # Mixed reviewed endings cannot be reconstructed from a digest alone.
   blob=api('repos/cstroh01/Quant-ML-Bot/git/blobs/'+sha)
   assert blob['encoding']=='base64'
   remote=base64.b64decode(blob['content'])
   assert hashlib.sha1(b'blob '+str(len(remote)).encode()+b'\0'+remote).hexdigest()==sha  # BLOB_IDENTITY
   assert remote.replace(b'\r\n',b'\n')==body  # NEWLINE_ONLY
 assert 'scripts/allocation_policy.py' in expected
 assert '--preview' in (root/'scripts/ops_runner.py').read_text(encoding='utf-8')
 sys.path.insert(0,str(root/'scripts'))
 from allocation_policy import POLICY_ID
 from mode_config import MAX_LIVE_BUDGET_USD
 assert POLICY_ID=='061-b7-ew-v1' and MAX_LIVE_BUDGET_USD==200.0
 assert sys.version_info[:2]==(3,12)
 print('PIN_AND_SOURCE_TREE_PASS')
except Exception:
 print('Reviewed pin/source/runtime guard refused',file=sys.stderr); raise SystemExit(2)
'@
& $Python -c $PinGuard $RepoRoot $PinSha
if ($LASTEXITCODE -ne 0) { throw 'Pin/tree/runtime guard failed; no credentials loaded.' }
if ($CheckPinOnly) { return }

$Eastern=[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTimeOffset]::UtcNow,'Eastern Standard Time')
if ($Eastern.TimeOfDay -lt [TimeSpan]::FromHours(9.5833333333) -or $Eastern.TimeOfDay -ge [TimeSpan]::FromHours(12)) {
    throw 'Outside the reviewed 09:35-12:00 Eastern preview window.'
}
$Session=$Eastern.ToString('yyyy-MM-dd')
Push-Location -LiteralPath $RepoRoot
$PriorPin=$env:QMB_PINNED_SHA
$KeepAwake=$false
try {
    & $Python -c 'from datetime import date; import sys; sys.path.insert(0,"scripts"); from data import trading_days; d=date.fromisoformat(sys.argv[1]); raise SystemExit(0 if trading_days(d,d)==[d] else 3)' $Session
    if ($LASTEXITCODE -eq 3) { Write-Output 'NYSE closed; no preview due.'; return }
    if ($LASTEXITCODE -ne 0) { throw 'NYSE calendar guard failed.' }
    if (-not $PSCmdlet.ShouldProcess('live_fidelity','Build fresh inputs and launch an unarmed preview')) { return }
    if (-not ('QMB.PreviewPower' -as [type])) {
        Add-Type -Namespace QMB -Name PreviewPower -MemberDefinition '[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);'
    }
    [QMB.PreviewPower]::SetThreadExecutionState(0x80000001L) | Out-Null
    $KeepAwake=$true
    $LogRoot=Join-Path $DataRoot 'logs'
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    $LogFile=Join-Path $LogRoot 'fidelity-preview.log'
    ('{0} preview start' -f [DateTimeOffset]::UtcNow.ToString('o')) | Add-Content -LiteralPath $LogFile
    $env:QMB_PINNED_SHA=$PinSha
    & $Python scripts/fidelity_inputs.py --out (Join-Path $DataRoot 'inputs') --session $Session 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw 'Input refresh refused; no Fidelity credentials loaded or preview attempted.' }
    # The approved launcher loads vault values only into its child's environment.
    $LaunchArgs=@('scripts/fidelity_launch.py','--',$Python,'exec/live_loop.py',
        '--profile','live_fidelity','--profiles-file',(Join-Path $DataRoot 'profiles.json'),
        '--state-dir',$StateRoot,'--closes-file',(Join-Path $DataRoot 'inputs\closes.csv'),
        '--sources-file',(Join-Path $DataRoot 'inputs\sources.json'))
    $Csv=Join-Path $DataRoot ('holdings\'+$Session+'.csv')
    if (Test-Path -LiteralPath $Csv -PathType Leaf) { $LaunchArgs+=@('--holdings-csv',$Csv) }
    & $Python @LaunchArgs 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw 'Preview refused; inspect local evidence. No automatic rerun.' }
    & $Python scripts/fidelity_preview_evidence.py (Join-Path $StateRoot ('preview-sessions\'+$Session+'.json')) --record 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw 'Clean-session evidence was refused; review local record. No automatic rerun.' }
    ('{0} preview finished; inspect clean/refused/HALTED evidence' -f [DateTimeOffset]::UtcNow.ToString('o')) | Add-Content -LiteralPath $LogFile
} finally {
    if ($KeepAwake) { [QMB.PreviewPower]::SetThreadExecutionState(0x80000000L) | Out-Null }
    if ($null -eq $PriorPin) { Remove-Item Env:\QMB_PINNED_SHA -ErrorAction SilentlyContinue } else { $env:QMB_PINNED_SHA=$PriorPin }
    Pop-Location
}
