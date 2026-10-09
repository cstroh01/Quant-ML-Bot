# T002a evidence: 043 review F2, F3, F7, F8 in the P-1 probe

Date: 2026-10-08. Lane: local worktree agent (origin/main checkout). No Git, no network.
Only `--self-check` was run; `--revision` was never run. The self-check was confirmed offline by
reading the code first: `self_check()` calls no `fetch`, and `refuses()` only parses arguments.

## Starting state

The worktree's `p1_rules.py` (296 lines) and `p1_probe.py` (270 lines) already held the four fixes
and 47 self-check cases, all `ok`. Their origin was not checked (no Git). T002a was unticked and had
no evidence. So this unit audited the existing fixes by mutation instead of writing them anew.

| Finding | Fix already present | Where |
|---|---|---|
| F2 | `last > completed` returns STOP before lag is measured | `p1_rules.horizon` |
| F3 | Self-check covers Q-P1, Q-P3, D-3, `read_inputs`, and `determine()` (the decision core of `run`, no writes) | `p1_probe.self_check` |
| F7 | `read_inputs` rejects blank cells, bad `form`, off-basket tickers, duplicate keys on parsed dates; `--revision` uses `type=full_sha` (`[0-9a-f]{40}`, fullmatch) | `p1_rules.read_inputs`, `p1_probe.full_sha` |
| F8 | `sessions` requires every `Dividends` cell finite and >= 0 before `> 0` event selection | `p1_rules.sessions` |

## Red first: three mutants survived the existing self-check

Driver: `<scratchpad>/t002a_mutants.py`, outside the repo. It copies both files per mutant, plants
one textual defect (anchor must match exactly once), and runs `--self-check`.

| Mutant | Defect | Before (47 cases) | Why it survived |
|---|---|---|---|
| F3d | Q-P3 required-case gate disabled | SURVIVED | The case was red for the wrong reason: its declared row had no provider dividend, so a later check stopped it |
| F7h | `re.match` in place of `re.fullmatch` | SURVIVED | No case had a full sha plus a suffix |
| F8b | Dividend `isfinite` check dropped | SURVIVED | NaN already fails `>= 0`; no `+inf` case |

## Change (`p1_probe.py` only; `p1_rules.py` unchanged)

1. `Q-P3 required case missing (F3)` now uses a fixture with two dividends before the split. It
   declares only the earlier one, a row that would PASS alone. The case checks the STOP message
   `required cases have no declared row`.
2. New `dividend infinite refused (F8)`.
3. New `revision sha with a suffix refused (F7)`: a 40-hex sha plus `-dirty`.

## Green: self-check after the change

`python -B artifacts/p1_probe.py --self-check` exit 0, **49 `ok`, 0 `FAIL`**. Lines 1-15 are the
pre-T002a cases. Lines 16-49, verbatim:

```
ok   horizon future-dated response (F2): got 'STOP', expected 'STOP'
ok   dividend NaN refused (F8): got True, expected True
ok   dividend negative refused (F8): got True, expected True
ok   dividend infinite refused (F8): got True, expected True
ok   Q-P1 control: got 'PASS', expected 'PASS'
ok   Q-P1 provider inside the range (F3): got 'STOP', expected 'STOP'
ok   Q-P1 filed after the split (F3): got 'STOP', expected 'STOP'
ok   Q-P3 control: got 'PASS', expected 'PASS'
ok   Q-P3 required case missing (F3): got 'required cases have no declared row', expected 'required cases have no declared row'
ok   Q-P1 rebuilt outside the range (F3): got 'STOP', expected 'STOP'
ok   Q-P1 low above high (F3): got 'STOP', expected 'STOP'
ok   Q-P1 one later split only (F3): got 'STOP', expected 'STOP'
ok   Q-P1 RANGES form 8-K refused (F7): got 'STOP', expected 'STOP'
ok   Q-P3 same-day control: got 'PASS', expected 'PASS'
ok   Q-P3 same-day basis disagrees (F3): got 'STOP', expected 'STOP'
ok   Q-P3 declared after ex-date (F3): got 'STOP', expected 'STOP'
ok   Q-P3 amount fits neither basis (F3): got 'STOP', expected 'STOP'
ok   Q-P3 share_basis off a split day (F3): got 'STOP', expected 'STOP'
ok   D-3 control: got 'PASS', expected 'PASS'
ok   D-3 no pre-2016 split (F3): got 'STOP', expected 'STOP'
ok   D-3 unclean ratio (F3): got 'STOP', expected 'STOP'
ok   read_inputs control: got False, expected False
ok   read_inputs blank accession (F7): got True, expected True
ok   read_inputs empty accession (F7): got True, expected True
ok   read_inputs duplicate key, unpadded date (F7): got True, expected True
ok   read_inputs invalid form (F7): got True, expected True
ok   read_inputs duplicate key (F7): got True, expected True
ok   read_inputs off-basket ticker (F7): got True, expected True
ok   revision full sha accepted: got False, expected False
ok   revision short sha refused (F7): got True, expected True
ok   revision sha with a suffix refused (F7): got True, expected True
ok   run control: got ['Horizon: PASS', 'boom: STOP', 'pass: PASS'], expected ['Horizon: PASS', 'boom: STOP', 'pass: PASS']
ok   run future-dated response (F2): got ['Horizon: STOP', 'boom: STOP', 'pass: STOP'], expected ['Horizon: STOP', 'boom: STOP', 'pass: STOP']
ok   run NaN dividend (F8): got ['Horizon: STOP', 'boom: STOP', 'pass: STOP'], expected ['Horizon: STOP', 'boom: STOP', 'pass: STOP']
```

## Rule 12 mutant table (after the change)

Green control (unmodified copies): exit 0, no FAIL. Every mutant: exit 1, and every named case red.

| Mutant | Finding | Planted defect | Cases turned red | Result |
|---|---|---|---|---|
| F2a | F2 | future-horizon check removed | horizon future-dated; run future-dated | killed |
| F2b | F2 | `>=` in place of `>` (stuck red on the current session) | horizon weekend lag; run control | killed |
| F3a | F3 | `determine` runs questions after a horizon STOP | run future-dated; run NaN dividend | killed |
| F3b | F3 | a question's exception recorded as PASS | run control | killed |
| F3c | F3 | Q-P1 no longer requires provider closes outside the band | Q-P1 provider inside the range | killed |
| F3d | F3 | Q-P3 required-case gate disabled | Q-P3 required case missing | killed (survived before) |
| F3e | F3 | Q-P1 filed-before-split uses `>` | Q-P1 filed after the split | killed |
| F7a | F7 | blank-cell check removed | blank accession; empty accession | killed |
| F7b | F7 | blank check without `strip()` | blank accession | killed |
| F7c | F7 | form check removed | invalid form; RANGES 8-K refused | killed |
| F7d | F7 | basket check removed | off-basket ticker | killed |
| F7e | F7 | duplicate-key check removed | duplicate key; duplicate key, unpadded date | killed |
| F7f | F7 | duplicate check on raw strings, before date parsing | duplicate key, unpadded date | killed |
| F7g | F7 | sha regex `{7,40}` | short sha refused | killed |
| F7h | F7 | `re.match` in place of `re.fullmatch` | sha with a suffix refused | killed (survived before) |
| F7i | F7 | `type=full_sha` removed from the parser | short sha; sha with a suffix | killed |
| F8a | F8 | dividend validation removed (the original bug) | NaN; negative; infinite; run NaN dividend | killed |
| F8b | F8 | `isfinite` dropped | infinite | killed (survived before) |
| F8c | F8 | NaN accepted, sign unchecked | NaN; negative; run NaN dividend | killed |
| F8d | F8 | `>= 0` dropped | negative | killed |

**20 of 20 killed, 0 survived.** Before the change: 17 killed, 3 survived.

## Suite and ledger

- `python -B -m pytest tests -q -p no:cacheprovider`: **1394 passed, 1386 subtests passed**, 1
  warning (Starlette deprecation), 0 failed, 0 errors.
- `docs/trials/**` SHA-256 identical before and after (5 files). `trials.jsonl`
  `1bb5dbfe…f30f`, `trials.head.json` `f83b1b9b…d764`.

## Size (SC-007)

`p1_probe.py` 275 lines; `p1_rules.py` 296 lines. Both ≤ 300. Unit diff, measured with the
tasks.md command against `<scratchpad>/pre-unit-t002a/` (new file against empty): `p1_rules.py`
0, `p1_probe.py` 9, `tasks.md` 5, this file 129. **Total 143 ≤ 300.**

## Open items, not fixed here (outside T002a's files)

- F2 asked for the same `last <= completed` rule in the spec contract. FR-002's horizon text
  (`spec.md` §FR-002) still states only the lag bound. It needs a dated amendment.
- The `--self-check` list in spec §5 does not yet name the F2, F3, F7 and F8 cases.
- F3's "run" is covered through `determine()`, run's decision core. `run()` itself writes files,
  and the registered self-check "writes nothing", so its hashing and writing stay untested offline.
