# 055 U4 evidence, 2026-10-08 (Linux, Python 3.13.16)

Red first: collection failed (module absent). Green: 5 passed. The wrapped command in tests is a
Python one-liner; the runner never imports broker code or reads credentials.
| Mutant | Result |
|---|---|
| lease skipped (concurrent worker runs) | killed |
| failure incident dropped | killed |
| missed sessions not reported | killed |
| not-due session still executes | killed |
