# Plan: 055
Module `scripts/ops_runtime.py` (pure). Tests `tests/test_055_*.py`. Workflows under `.github/` are
governance drafts made only on Camden's per-change instruction; private-repo copies live in the companion repo.
- **U1** due-run calendar + missed-run detection (FR-001).
- **U2** leases, idempotent client ids, persisted-before-submit (FR-002/003) with crash fakes.
- **U3** summary and alert payloads + incident dedupe, fake sink (FR-005).
- **U4** runner entrypoint `scripts/ops_runner.py`-style CLI wrapping 049 with state dir + lease (no `exec/` edits).
- **U5** workflow templates (`ops/workflows/*.yml` in this repo as templates; installed in the private repo).
