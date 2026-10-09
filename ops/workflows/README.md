# Workflow templates (spec 055 U5)

Templates for the PRIVATE companion repo (ADR 0001). They are not active here.
Install by copying into that repo's `.github/workflows/` (Camden's human step, 055 T006).

| File | Runs | Uses minutes for |
|---|---|---|
| `paper-loop.yml` | weekdays 12:00 and 13:00 UTC; the due-run gate decides | daily PAPER session per profile, state on `ops-state` |
| `nightly-research.yml` | daily 06:17 UTC | full suite + mutation drivers on the pinned commit |

Required in the private repo: variable `QMB_PINNED_SHA` (a merged `main` commit), secrets
`PAPER_SMALL_KEY_ID`, `PAPER_SMALL_SECRET`, `PAPER_LARGE_KEY_ID`, `PAPER_LARGE_SECRET`,
`QMB_PROFILES_JSON` (the spec 051 profile list: `paper_small` $5,000 budget, `paper_large`
$100,000 with a larger daily deploy fraction), and an `ops-state` branch. Never run the local
paper loop against an account a cloud profile also trades. Agents never see secret values.

Until spec 051 T007 (reviewed `exec/` wiring) merges, each profile runs the existing 049 loop
against its own Alpaca paper account; the per-profile budget and daily cap apply after that wiring.
