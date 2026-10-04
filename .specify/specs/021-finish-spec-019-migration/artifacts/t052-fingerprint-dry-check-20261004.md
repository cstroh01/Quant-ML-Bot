# 021 T052 — offline fingerprint dry check, 2026-10-04

**What this is.** A re-run of T004's two fingerprint methods against
`origin/main` at `489a178a2ed6f60b456d66711db1140912774396` (committed
2026-10-03 23:31 -0400; run 2026-10-04 UTC),
by the cloud scheduled-session lane (queue item Q6). It is evidence only. It
does **not** check T052's box: Camden directed on 2026-09-23 to leave T052
open and keep the original T004 snapshot (`tasks.md`, Evidence → T004;
`HANDOFF.md`, "Gate limits"). Provenance of the compared values: the T004
prefixes were first recorded in `446fa62` (2026-09-18); the T052 column in
`54e6e0b` (2026-09-23). No replacement baseline is proposed here.

**Method.** A scratch-only script (not committed, per T004) on Linux, Python
3.12:

- (i) Regions: `ast.get_source_segment` of each named top-level function or
  assignment, read with `Path.read_text(encoding="utf-8")`, SHA-256 of the
  UTF-8 segment. Universal-newline reading makes this independent of line
  endings.
- (ii) Whole files: SHA-256 of the raw bytes, computed twice — as checked out
  here (LF, per `.gitattributes` `* text=auto eol=lf`) and with every line
  ending rewritten to CRLF. `.gitattributes` (`* text=auto eol=lf`, since
  `416781f`, 2026-09-06) should give LF on every platform, so the CRLF form
  is tried only because some T004 prefixes reproduce from it (below).
- To date any drift, the same two hashes were taken of every committed blob of
  each file (`git show <commit>:<path>`), newest first, until one reproduced
  the T004 prefix.

Only 16-hex prefixes are recorded in `tasks.md`, so a match means "prefix
matches", the same standard T052 used on 2026-09-23.

## (i) Frozen regions — 14 of 14 match T004

`make_signalled_prices`, `COSTS`, `make_prices`, `sawtooth_prices`,
`_synthetic_features`, and all nine `scripts/logistic_baseline.py` regions
(`FEATURE_COLUMNS` … `build_ml_signal`) reproduce their T004 prefixes exactly.
FR-020's fixture freeze and the frozen `logistic_baseline.py` functions hold at
`489a178`.

## (ii) Whole files — the line-ending finding first

Some T004 prefixes reproduce only from the CRLF form of a committed blob,
others only from the LF form (table below). The inference — not verified here —
is that T004 hashed a working tree whose line endings were mixed or differed
from the `.gitattributes` setting. A Linux checkout therefore cannot
reproduce T004 by hashing bytes as checked out, and a whole-file "mismatch"
from a different machine is not by itself evidence of a content change. The
CRLF/LF column says which form reproduced the prefix.

| File | T004 prefix | Now (CRLF form) | Status at `489a178` | Last T004-matching blob → first later change |
|---|---|---|---|---|
| `scripts/targets.py` | `2b455778e3b150e5` | `2b455778e3b150e5` | matches T004 (CRLF) | `8b5afb7` (2026-09-14), unchanged since |
| `scripts/features.py` | `3aea331409667b1b` | `3aea331409667b1b` | matches T004 (CRLF) | `35eddb1` (2026-09-18), unchanged since |
| `scripts/walk_forward_cv.py` | `2744be2e971947cd` | LF form `2744be2e971947cd` | matches T004 (LF) | `416781f` (2026-09-06), unchanged since |
| `scripts/estimators.py` | `884ec1c1c0c3b72a` | `d8bcfc703ebfda8b` | drifted; **equals the T052 value**, no change since 2026-09-23 | `35eddb1` → `a14ab62` (2026-09-23) |
| `scripts/model_cv.py` | `ece3ce1b4a6cf0e7` | `f0bf4df33159f2f4` | drifted; **equals the T052 value**, no change since 2026-09-23 | `ab7d56e` → `22dca26` (2026-09-22) |
| `scripts/feature_set_comparison.py` | `de1e53acb2382074` | `af35aa3098065b97` | drifted; **further** change after T052 | `e6b39f5` (2026-09-18) → `22dca26` (2026-09-22); since T052: `e96aaed` (2026-09-26) |
| `scripts/multi_ticker_comparison.py` | `5ef8d26d2245e30a` | `063f0bf8e7e73dd9` | drifted; **further** change after T052 | `e6b39f5` (2026-09-18) → `22dca26` (2026-09-22); since T052: `e96aaed` (2026-09-26), `266d395` (2026-09-27) |
| `reports/api/routes/backtest.py` | `c7c8a3d164d5ef7c` | `c2836285590ca3be` | drifted; T052 value `9a6b6eace184a883` reproduces from **no** committed blob, so "since T052" is unanchored | `ab7d56e` (LF) → `22dca26` (2026-09-22); later: `266d395` (2026-09-27), `9457d8f` (2026-09-29) |
| `docs/PROJECT_CONTEXT.md` | `b3aea859acb06db5` | `55f7ef3124cccabc` | drifted; **further** change after T052 | `a6981c1` (2026-09-14, LF) → `446fa62` (2026-09-18); T052 value reproduces from `a14ab62` (LF); since: `54e6e0b` (2026-09-23), `e96aaed` (2026-09-26) |
| `scripts/backtest_harness.py` | `84dce49de93fd03b` | `48a2559617794129` | **new drift** (T052 recorded a match) | `ab7d56e` (2026-09-12, CRLF) → `9457d8f` (2026-09-29) |
| `requirements.txt` | `816ab9586ad6f145` | `78616268d3c78215` | **new drift** (T052 recorded a match) | `416781f` (2026-09-06, CRLF) → `649eca5` (2026-10-02, Dependabot) |
| `requirements-dev.txt` | `39a274047a205e6e` | `aa13c37aa6abe9d0` | **new drift** (T052 recorded a match) | `8b5afb7` (2026-09-14, LF) → `649eca5` (2026-10-02, Dependabot) |
| `scripts/metrics.py` | `af42f6074cb4ea99` | `5d0200600d0f09d4` | **unexplained** | no committed blob reproduces the prefix in either form |
| `scripts/ml_signal.py` | `aeb766e8b15bf219` | `69b56ecf526efbfe` | **unexplained** | no committed blob reproduces the prefix in either form |

Full current digests (LF form, as checked out at `489a178`) are reproducible by
re-running the method above; prefixes are given here to match the T004 table.

## Reading

- **Content freeze that 021 owns (FR-020, frozen regions): holds.**
- **Whole files: 3 match, 11 do not.** Of the 11, 2 are unchanged since the
  2026-09-23 T052 run, 4 changed again after it (for `routes/backtest.py` the
  T052 value itself is unreproducible, so its post-T052 attribution is
  inferred), 3 drifted for the first time after it, and 2 cannot be explained
  offline.
- `scripts/metrics.py` and `scripts/ml_signal.py`: T004 was taken "after
  T002(a) holds", and T052 recorded both as matching on 2026-09-23, yet no
  commit's blob — LF or CRLF — reproduces either prefix. Their last commit is
  `e6b39f5` (2026-09-18). One explanation is that both T004 and T052 hashed a
  Windows working tree whose bytes differed from any commit (uncommitted edits,
  or mixed endings); the tree was moving at the time (`446fa62`, which recorded
  T004, changed `PROJECT_CONTEXT.md` 1h41m after `e6b39f5`). This lane cannot see that tree;
  a re-run on the Windows checkout would settle it.
- Not established here whether any drift is a spec 021 edit (FR-019 binds
  021's own edits): `54e6e0b` and `e96aaed` are mixed checkpoints that touch
  021's `tasks.md`/`HANDOFF.md` and drifted files together. Their drifted-file
  hunks read as non-021 work (vendor-access notes; specs 036/037), but that is
  a reading, not a proof. `feature_set_comparison.py` and `multi_ticker_comparison.py` are
  pinned 019 files; their post-T052 changes (`e96aaed`, `266d395`) are
  reported, not judged, here.

## Not done here

- T052 stays unchecked. Whether to keep the historical snapshot, re-baseline,
  or retire T052 against the drift above is a Camden decision.
- No file was hashed outside the repository; no network; no write outside this
  file.
