[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference='Stop'
$TaskName='QMB Fidelity Preview'
$Receipt='C:\QMB\Fidelity\preview-task-install.json'
if (-not (Test-Path -LiteralPath $Receipt)) { throw 'Installation receipt missing; no task or power setting changed.' }
$Saved=Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json
if ($Saved.PSObject.Properties.Name -contains 'uninstalled_at_utc') { throw 'This task was already uninstalled; no settings changed.' }
if ($Saved.task -ne $TaskName -or $Saved.power_scheme -notmatch '^[0-9a-fA-F-]{36}$' -or $Saved.prior_ac_lid -notin @(0,1,2,3)) { throw 'Receipt does not match the preview task.' }
if (-not $PSCmdlet.ShouldProcess($TaskName,'Remove only this preview task and restore its saved AC lid setting')) { return }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
& powercfg /setacvalueindex $Saved.power_scheme SUB_BUTTONS LIDACTION $Saved.prior_ac_lid
if ($LASTEXITCODE -ne 0) { throw 'Task removed; restoring the saved AC lid setting failed. Preserve the receipt.' }
$CurrentScheme=([regex]::Match((& powercfg /getactivescheme | Out-String),'[0-9a-fA-F-]{36}')).Value
if ($CurrentScheme -eq $Saved.power_scheme) {
    & powercfg /setactive $Saved.power_scheme
    if ($LASTEXITCODE -ne 0) { throw 'Task removed; power-plan activation failed. Preserve the receipt.' }
}
$Saved | Add-Member -NotePropertyName uninstalled_at_utc -NotePropertyValue ([DateTimeOffset]::UtcNow.ToString('o'))
$Saved | ConvertTo-Json | Set-Content -LiteralPath $Receipt -Encoding UTF8
Write-Output 'Preview task removed and saved AC lid behavior restored. Receipt retained; no broker state or other task changed.'
