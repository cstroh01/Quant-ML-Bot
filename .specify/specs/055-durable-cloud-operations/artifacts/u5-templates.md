# 055 U5 evidence, 2026-10-08

Templates only (`ops/workflows/`), not active in this repo. `actionlint` (actionlint-py) clean on both.
Action pins reuse SHAs already used by this repo's CI (checkout, setup-python) and `upload-artifact@v7`
as in `dev-loop.yml`. Concurrency group + `max-parallel: 1` give one run at a time; the due-run gate
and per-session lease (U1/U2/U4) refuse a second run for the same session.
