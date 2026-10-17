# HUMAN INSTALL: prompts for Windows account password; never a Fidelity credential.
[CmdletBinding(SupportsShouldProcess)]
param([Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$PinSha,
      [string]$RepoRoot='C:\GitHub\Quant-ML-Bot')
$ErrorActionPreference='Stop'
$TaskName='QMB Fidelity Preview'
$DataRoot='C:\QMB\Fidelity'
$Python=Join-Path $DataRoot 'venv312\Scripts\python.exe'
$Receipt=Join-Path $DataRoot 'preview-task-install.json'
if ((Get-TimeZone).Id -ne 'Central Standard Time') { throw 'This template requires the reviewed Chicago Windows time zone.' }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw 'Preview task already exists; inspect before replacing.' }
if (Test-Path -LiteralPath $Receipt) { throw 'Prior installation receipt exists; inspect it first.' }
$Script=Join-Path $RepoRoot 'scripts\fidelity_preview_day.ps1'
$Template=Join-Path $RepoRoot 'ops\windows\fidelity-preview-task.xml'
if (-not (Test-Path -LiteralPath $Python) -or -not (Test-Path -LiteralPath $Script) -or -not (Test-Path -LiteralPath $Template)) { throw 'Reviewed runtime/script/task template missing.' }
& $Script -PinSha $PinSha -RepoRoot $RepoRoot -CheckPinOnly
if ($LASTEXITCODE -ne 0) { throw 'Reviewed pin verification failed; no task installed.' }
if (-not $PSCmdlet.ShouldProcess($TaskName,'Install weekday unarmed preview and keep the laptop awake on AC when its lid closes')) { return }
$WindowsCredential=Get-Credential -Message 'Windows account password for the local preview task (not a Fidelity password).'
if ($null -eq $WindowsCredential) { throw 'Windows task credentials were not supplied.' }
$PowerQuery=& powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION | Out-String
if ($LASTEXITCODE -ne 0 -or $PowerQuery -notmatch 'Current AC Power Setting Index:\s*0x([0-9a-fA-F]+)') { throw 'Cannot record the existing AC lid setting; no task installed.' }
$PriorAc=[Convert]::ToInt32($Matches[1],16)
$InstalledPower=([regex]::Match((& powercfg /getactivescheme | Out-String),'[0-9a-fA-F-]{36}')).Value
if (-not $InstalledPower) { throw 'Active power-plan identity unavailable.' }
[xml]$Definition=Get-Content -LiteralPath $Template -Raw
$Ns=New-Object Xml.XmlNamespaceManager($Definition.NameTable)
$Ns.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
$Definition.SelectSingleNode('//t:UserId',$Ns).InnerText=$WindowsCredential.UserName
$Definition.SelectSingleNode('//t:Command',$Ns).InnerText=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Definition.SelectSingleNode('//t:WorkingDirectory',$Ns).InnerText=$RepoRoot
$Definition.SelectSingleNode('//t:Arguments',$Ns).InnerText='-NoProfile -NonInteractive -File "'+$Script+'" -PinSha "'+$PinSha+'" -RepoRoot "'+$RepoRoot+'"'
try {
    Register-ScheduledTask -TaskName $TaskName -Xml $Definition.OuterXml -User $WindowsCredential.UserName -Password $WindowsCredential.GetNetworkCredential().Password | Out-Null
    @{task=$TaskName;power_scheme=$InstalledPower;prior_ac_lid=$PriorAc;pin_sha=$PinSha;installed_at_utc=[DateTimeOffset]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath $Receipt -Encoding UTF8
    & powercfg /setacvalueindex $InstalledPower SUB_BUTTONS LIDACTION 0
    if ($LASTEXITCODE -ne 0) { throw 'Task installed, but AC lid setting failed. Stop and inspect the receipt; do not rerun.' }
    & powercfg /setactive $InstalledPower
    if ($LASTEXITCODE -ne 0) { throw 'Task installed; power-plan activation failed. Inspect before use.' }
    Write-Output 'Preview task installed for 08:40 Chicago weekdays. AC lid close will not sleep; battery behavior is unchanged. No arming or immediate run.'
} finally { $WindowsCredential=$null }
