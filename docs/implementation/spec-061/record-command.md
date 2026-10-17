# 061 T005 — fresh buffered trial (Camden's human gate)

Recording completed by Camden on 2026-10-17: all 22 fresh series completed and
ledger verification passed at 898 lines. **Do not rerun.** The procedure below
is retained for audit; it is not a pending action. See trial-report-20261017.md.

The reviewed recording procedure used Python 3.12 from the repository root:

```powershell
python scripts/run_061_buffered_trial.py --panel <frozen-private-T008-panel> --record-trial --out <new-private-output-directory>
```

This is one invocation: read-only preflight, freeze `061-buffered-allocation`
using the existing trial-registry API, verify the declaration, start all 22
series, evaluate the fresh B7-EW candidate and both baseline types with spec
046 primary costs, persist funded log returns, and verify the ledger.
The output contains report.json and report.md, including receipts and limitations.
No network call, broker order, arming, execution-policy change or budget change.

Optional read-only check: substitute `--dry-run` and omit `--out`.
It hashes the weight book but computes no performance or P&L and writes nothing.

Never run the old `run_059_t004.py` to relabel its result, never amend the
already-traded 059 declaration, and never pass another family to avoid a guard.
A second invocation after any 061 start, including an errored start, is refused.
An orphan lock requires human inspection; do not delete it or automatically retry.
No performance is accepted until the new trial and immutable returns verify.
Publication and adoption into the execution/gate paths remain separate reviews.
