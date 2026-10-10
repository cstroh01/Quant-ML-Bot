# Spec 058 T007 — holdout seal contract (FR-002, D-3)

EXAMPLE — NOT A RESULT. Synthetic frames only; no `docs/trials/` write. Base `d4ca12f`, queue Q23.

## What it adds
`scripts/data_sources.py`: `RESEARCH_END` 2023-09-29, `HOLDOUT_START` 2023-10-02 (checked against
`declaration.json` and the NYSE calendar), `sealed_sessions`, `HoldoutToken`, `require_holdout_token`.
Labels after `RESEARCH_END` are refused without a token bound to `config_hash` and a spend path. The
spend record is created exclusively before the frame is returned; refusals never create it. Aware
or NaT labels are refused.

## Evidence
- Red: `tests/test_058_holdout.py` against main fails collection (`ImportError: HoldoutSealError`).
- Rule 12: `python tests/mutation/run_058_t007_mutants.py` kills 6/6 (cutoff early, late and
  inclusive; token reused; wrong hash; NaT accepted). The control is green with 16 collected, and
  sources and `docs/trials/` are byte-identical.

## Open limits (adversarial review; why T007 stays unticked)
- **Not wired.** No §4 loader exists yet. FR-002 holds only once that loader calls the seal on raw
  prices; the seal sees index labels, not columns derived from later rows.
- **Binding.** `config_hash` is caller-supplied. Tying it to the §5 selection record waits on T014.
- **One-shot per spend path.** A different `spent_path` reopens. A fixed or ledger-backed record
  (D-3, T016) is a placement decision, possibly outside `data_sources.py`.
