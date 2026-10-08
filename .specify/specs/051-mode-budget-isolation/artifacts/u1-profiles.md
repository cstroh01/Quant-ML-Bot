# 051 U1 evidence, 2026-10-07 (Linux, Python 3.13.16)

Red first: `tests/test_051_profiles.py` failed collection (module absent).
Green: 23 passed. Mutants (copy of `scripts/mode_config.py`, restored after each):
| Mutant | Result |
|---|---|
| broker/mode check removed (URL-only LIVE) | killed |
| shared namespace/identity allowed | killed (4) |
| raw account id accepted as fingerprint | killed |
| arming for a different account | killed |
| expired arming accepted | killed |
| LIVE without an arming record | killed |
| default profile may be LIVE | killed |
