# Phase 3 gates and handoff, T032-T036, 2026-10-08

Tree: `claude/043-t031-alias` (U2 through U6 stacked on `main` 0c7f674).

## T032, AC-6
`python -m pytest tests`, Linux Python 3.13.16: exit 0; 1236 passed, 0 failed,
0 errors, 0 xfailed, 1 warning (starlette httpx deprecation).
Windows CI (`test-windows`, `python -m pytest tests`): success at each unit's
head; counts are in the Actions log. `main` was 1204 passed + 4 strict xfails
(1208 collected); 043 U2-U6 add 28 tests and retire all four xfails.
T003's 1003 predates later merged specs, so `main` is the comparator.

## T033, D-5 side effect
rootdir is the repository root, as at T003. `configfile: pyproject.toml` now
appears (D-5's marker; T003's tree had none). Harmless: collecting with an
empty `-c` ini instead yields the identical 1236 node IDs (`cmp` equal).

## T034, AC-4
`artifacts/ledger-post.json`: line count, both hashes, head content, verify()
head, `n_post_ledger` 87 and 174 events equal `ledger-pre.json`; `returns/`
absent. The real Windows tree re-hashed read-only equals T002 byte for byte.
Finding for 040 AC-4a: the Windows working copy of `backfill/manifest.json`
is CRLF; an LF checkout hashes `d7a303ac...`. Hash comparisons across
checkouts must normalize line endings or pin one checkout.

## T035, acceptance
AC-1/2/3 (U2, `u2-t025-t026.md`), AC-5 (U1), AC-6 (T028 `u4a-t028.md` + T032),
AC-7 (`u5-t030.md`), AC-8 (`u4b-t029.md`), AC-9 (`u6-t031.md`),
AC-10 (`u3b-t027.md`) are green in T032. Phase 1 red artifacts remain here.

## T036, handoff
Decisions: D-1 B, D-2 A1, D-3 (a) 1 and (b) iii, D-4 a + c, D-5 a; Camden's
T025-only pin exception and two T027 fixture alignments (spec.md, 2026-10-07).

| Unit | PR | Files | Added+removed |
|---|---|---|---|
| U2, T025-T026 | #55 | 15 | 242 |
| U3a, T027 prep | #57 | 4 | 268 |
| U3b, T027 | #58 | 14 | 296 |
| U4a, T028 | #59 | 6 | 84 |
| U4b, T029 | #60 | 7 | 178 |
| U5, T030 | #61 | 8 | 81 |
| U6, T031 | #62 | 3 | 43 |

Merge order: #55, #57, #58 ... #62, then this PR. Spec 040 needs the seven
amendments in spec section 6 applied by Camden before 040 T001, plus the
CRLF note above for 040 AC-4a.
