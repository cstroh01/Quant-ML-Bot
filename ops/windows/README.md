# Dormant Fidelity preview task (057 Q138 replacement)

Review drafts only. Camden superseded the public-repository self-hosted runner
on 2026-10-17: PR workflow code must not run on a credential-holding machine.
No task is installed by this build. Never use the old PAPER task for Fidelity.

After the 061 adoption and separate protected $200/precision changes are on main,
Camden updates this checkout in GitKraken and supplies that exact 40-character
main commit as `<reviewed-main-sha>`:

```powershell
& C:\GitHub\Quant-ML-Bot\scripts\fidelity_preview_day.ps1 -PinSha <reviewed-main-sha> -CheckPinOnly
& C:\GitHub\Quant-ML-Bot\scripts\install-fidelity-preview-task.ps1 -PinSha <reviewed-main-sha>
```

The installer prompts for the Windows account password, never a Fidelity password.
Task Scheduler stores the Windows logon credential; the XML and receipt contain
no password. The fixed task is `QMB Fidelity Preview`, weekdays 08:40 Chicago
(09:40 Eastern). It runs when logged off, wakes supported sleeping hardware, and
starts after a missed trigger only inside the helper's 09:35–12:00 Eastern
window on an NYSE session. It cannot power on a shut-down laptop.

Keep the laptop connected to AC and the network. Installation saves the prior
AC lid setting and sets lid close to Do Nothing. The running helper requests
system wakefulness, then restores normal sleep inhibition on exit. Battery
behavior is unchanged. Hardware wake, reboot/logged-off access, lid close,
network and vault access require supervised runtime proof; XML parsing alone
does not prove them. Power-setting failures stop with a retained receipt.

The persistent Python 3.12 runtime is `C:\QMB\Fidelity\venv312\Scripts\python.exe`.
KILL/HALTED are checked before pin or credentials. Every Python/PowerShell file
under scripts/exec must match the pinned GitHub main ancestor, with Windows CRLF
normalization. New unreviewed source files refuse. No Git command is run.
The approved launcher uses only the fixed `FIDELITY_LIVE_*` credential references;
the helper does not read .env. The input refresher separately requires the
approved `APCA_API_KEY_ID`/`APCA_API_SECRET_KEY` environment channel. Never paste
those values in a command or a log. Missing credentials stop the run.

Manual preview, using the same reviewed helper:

```powershell
& C:\GitHub\Quant-ML-Bot\scripts\fidelity_preview_day.ps1 -PinSha <reviewed-main-sha>
```

Logs append to `C:\QMB\Fidelity\logs\fidelity-preview.log`. Inputs rebuild for
the current NYSE session, ending at the preceding session's completed close.
An unsettled deposit is a normal refusal and contributes no clean evidence.
A redirect/challenge may latch HALTED: preserve it and stop for Camden's review.
Never retry a completed or failed daily lease automatically.

If `C:\QMB\Fidelity\holdings\YYYY-MM-DD.csv` exists for today's session, the
helper passes it for the real dedicated-account CSV comparison. Export that
day's Fidelity holdings before the fifth morning (or a later new session);
never relabel an old CSV or rerun a consumed session. Each clean, unarmed daily
record feeds `scripts/fidelity_preview_evidence.py --record`, which copies only
typed fields, hashes immutable days, and updates item 6 in the gate manifest.
Fewer than five distinct clean NYSE days, or no latest-day CSV match, stays
MISSING. These locally generated artifacts still require human publication.

Uninstall only this task and restore its saved AC lid setting:

```powershell
& C:\GitHub\Quant-ML-Bot\scripts\uninstall-fidelity-preview-task.ps1
```

The receipt remains at `C:\QMB\Fidelity\preview-task-install.json`; no broker
state, HALTED file, credential or other Windows task is removed. After uninstall,
review the receipt before a future installation. `-WhatIf` is supported.

Arming later requires all §11.3 evidence, exact-arming-SHA final mutations, and
Camden's separate signed arming action. This task never supplies an arming file
or submit switch. Even after such a file exists, this preview task remains
preview-only until a separate reviewed operator change. No arming is authorized
by installing it.
