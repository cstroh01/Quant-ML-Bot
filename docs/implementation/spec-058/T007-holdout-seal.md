# Spec 058 T007 — holdout seal contract (FR-002, D-3)

EXAMPLE — NOT A RESULT. Synthetic frames only; no market data; no `docs/trials/` write.
Base: main `d4ca12f`. Queue item Q23. This change does not tick T007.

## What it adds
- `scripts/data_sources.py` gains the seal the §4 loader must call before serving a frame:
  - `RESEARCH_END = 2023-09-29` and `HOLDOUT_START = 2023-10-02`. A test checks both against
    `declaration.json` and checks that they are adjacent NYSE sessions.
  - `sealed_sessions(index)` marks every label after `RESEARCH_END`. Non-session labels in the
    weekend gap are sealed too. Labels must be naive session dates; an aware index or a NaT
    label is refused.
  - `HoldoutToken(config_hash)` carries a SHA-256 configuration hash and nothing else.
  - `require_holdout_token(frame, config_hash=, token=, spent_path=)`:
    - A frame with no sealed label is returned untouched. Nothing is read or spent.
    - A sealed label with no token, a token bound to another hash, or no spend path is refused.
      None of these refusals creates the spend record.
    - Otherwise the spend record is created exclusively (`open(..., "x")`) before the frame is
      returned. A second opening, by any token sharing that path, is refused.
- The loader that serves §4 data does not exist yet (Q24/Q25 build on this). Wiring the seal into
  it is part of that work. The spend-record location for the real T016 run is Camden's choice;
  it must not be under `docs/trials/`.

## Red proof
New `tests/test_058_holdout.py` against main's `scripts/data_sources.py`: collection error
(`ImportError: cannot import name 'HoldoutSealError'`).

## Rule 12 — `python tests/mutation/run_058_t007_mutants.py`

| Mutant | Witness | Result |
|---|---|---|
| cutoff one session early (`RESEARCH_END` 2023-09-28) | T007 CUTOFF | killed |
| cutoff one session late (`RESEARCH_END` 2023-10-02) | T007 CUTOFF | killed |
| cutoff inclusive (compare against `HOLDOUT_START`) | T007 CUTOFF | killed |
| token reused (`"x"` → `"w"`) | T007 REUSE | killed |
| token bound to another hash (check removed) | T007 BIND | killed |
| NaT label accepted (check removed) | T007 NAT | killed |

Control: the unchanged copy is green with 16 tests collected. The guard source, the test, the
declaration and `docs/trials/` (6 files) are byte-identical after the run.

## Open limits (adversarial review, not fixed here)
These are why T007 stays unticked:
- **Not wired.** No loader calls the seal yet. FR-002 is met only once the §4 loader is the one
  path that returns data and it calls `require_holdout_token` on raw prices.
- **Binding is to a caller-supplied hash.** Nothing yet ties `config_hash` to the configuration
  the §5 selection rule chose; that record does not exist until T014. Binding the token to the
  selection record is follow-up work.
- **One-shot is per spend path.** A different `spent_path` opens the holdout again. The global
  record is the T016 ledger entry (D-3). A fixed spend path, or a ledger-backed check, is a
  placement decision. It may also move the spend state out of `data_sources.py` (module boundary).
- **Derived columns.** The seal sees index labels only. Labels or features built from rows after
  the cutoff onto research rows are not caught; the docstring requires sealing raw prices first.
