# 061 plan

1. T001: prepare the new family declaration, without changing 059 or 058.
2. T002: test the buffered weights against A1 (red), then implement equal weights.
3. T003: prepare a recorder composing existing accounting, primary costs and
   ledger APIs. Preflight is read-only; only Camden invokes --record-trial.
4. T004: run focused tests, serial planted mutants and the required full suite;
   verify production ledger bytes unchanged. Supply one command for T005.
5. T005 HUMAN GATE: Camden freezes/records once. Stop on any refusal or failure.
6. T006: reviewed adoption, replay, gates and operational changes only after T005.

No dependency added. Historical allocation/report code remains reproducible.
