# Spec 058 T005 — family declaration contract

EXAMPLE — NOT A RESULT. Synthetic ledgers only; no market data; no `docs/trials/` write.
Base: main `e4899f3`. This change does not tick T005.

## What it adds
- `.specify/specs/058-edge-research-program/declaration.json` freezes the preregistration as
  committed, reviewable content:
  - the 15 configurations
  - the 25-ETF universe
  - the holdout and research-end dates
  - `n_family_cap` 50
  - the costs and CV conventions
  - the Rule 4 baselines
  - the selection rule
  - the D-4 pass condition
  - the voiding rule
- `scripts/trial_registry.py` gains `declare_family`, `verify_family` and `family_status`.
  - `TrialLedger.start` refuses any `058-edge` trial unless a verified declaration exists at
    `docs/trials/families/058-edge.json`.
  - The declaration is write-once (`immutable_write`).
  - Writing it to production requires `production_recording`.
  - The declaration refuses when the family already has trials.
  - Its record and declaration hashes are verified on every start.
- `scripts/declare_family.py` is Camden's T006 command. It refuses without `--record`.
  - Usage: `python scripts/declare_family.py 058-edge --record`
- `family_status` counts candidate starts against the cap. More than 50 sets `within_cap = False`,
  which voids family N under D-1.
- The ledger event schema is unchanged. Other families are unaffected; there is a control test.

## Red proof
New `tests/test_058_family.py` on the unmodified registry: 7 failed and 2 passed
(`AttributeError: declare_family`). The 2 that passed check the committed declaration content and the
unrelated-family control. The CLI test was added after that run.

## Rule 12 — `python tests/mutation/run_058_t005_mutants.py`

| Mutant | Witness |
|---|---|
| start gate removed | T005 REQUIRE |
| altered record accepted | T005 TAMPER |
| record overwritten | T005 ONCE |
| source family unchecked | T005 FAMILY |
| enablement skipped | T005 ENABLE |
| cap off by one | T005 CAP |
| cli writes without flag | T005 CLI |

- 7/7 killed by JUnit failures carrying the named witnesses.
- Control: the unchanged copy is green with 10 tests collected.
- Sources and all 5 `docs/trials/` files are byte-identical after the run.

## Suite and ledger (Linux, Python 3.13.16)
- Full suite: 1733 passed, 1386 subtests passed, 1 warning, exit 0. That is main's 1723 plus 10 new tests.
- `trials.jsonl` `1bb5dbfe…` and `trials.head.json` `f83b1b9b…` are unchanged before and after. `returns/` and `families/` are absent.
