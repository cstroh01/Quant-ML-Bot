# 067 — Evidence records are written and hashed as committed (LF) bytes

Date: 2026-11-13 America/New_York. Status: implemented, merge held (see "Landing").
Baseline: main `0a6b5ff` (merge of PR #328). Post-v1.2 hardening; no SCOPE item changes.

## Why

SCOPE §11.3 item 1's evidence record is written by `scripts/run_mutation_suite.py`. Before this
spec it used `Path.write_text`, which on Windows writes CRLF line endings. The packet script
`apply_item1.py` (Camden's orchestration packet `final-20261112-gate-items-1-7`, outside the repo)
then took SHA-256 over those CRLF bytes and wrote it into
`docs/implementation/spec-059/gate-manifest.json`.

`.gitattributes` (`* text=auto eol=lf`) stores and checks out text as LF. So the committed record
was LF, every checkout held LF, and the recorded digest matched no checkout. `scripts/gate_checklist.py`
hashes the bytes on disk, so it printed item 1 MISSING and PR #328 NOT ARMABLE until a hand-made
third commit (`23ee7ba`, "item 1 manifest digest over the committed (LF) record bytes") fixed the
digest. This is the same class as the nine mutation-driver restore fixes in PR #327, where
`write_text` restores left CRLF behind and item 1 counted the file as changed.

## FR-001 — The runner writes LF bytes

`run_mutation_suite.record_bytes(record) -> bytes` returns the record exactly as the repository
stores it: `json.dumps(record, indent=1)` plus one trailing `\n`, UTF-8, no CR on any platform.
`main` writes it with `Path.write_bytes`, never a text-mode write.

## FR-002 — The runner prints the digest of the bytes on disk

The runner's last printed line ends `; record sha256 <hex> (LF bytes, as committed)`, where `<hex>`
is SHA-256 over `out.read_bytes()` after the write. That is the value a manifest records.

## FR-003 — How every future manifest digest is taken (normative)

Applies to any `sha256` recorded in `docs/implementation/spec-059/gate-manifest.json` or any other
manifest that `gate_checklist.py` or an arming check compares against files in the repository.

1. **The digest covers the committed bytes.** SHA-256 over the artifact as the repository stores
   it. For text under `.gitattributes`, that is the LF form, which is also what every checkout
   holds. Never a digest over a CRLF working copy, and never over text re-encoded in memory.
2. **The producer writes those bytes itself.** Evidence files are written with `write_bytes`
   of UTF-8 text joined by `\n`, or `open(path, "w", encoding="utf-8", newline="\n")`. Not
   `Path.write_text` and not a text-mode `open` without `newline="\n"`.
3. **The recorder refuses CR; it does not normalize.** A script that records a digest (such as
   `apply_item1.py`) hashes `path.read_bytes()` and stops with an error if those bytes contain
   `\r`. A CR means the producer broke rule 2; normalizing would hide that and leave the working
   copy disagreeing with the manifest until the next checkout. For item 1 the recorded digest must
   also equal the `record sha256` the runner printed (FR-002).
4. **Check from a fresh checkout before the PR is opened.** Run `python scripts/gate_checklist.py`
   in a clean checkout of the PR head and require every changed item `EVIDENCED`. This is the step
   that would have caught PR #328 before its third commit.

Changing an existing manifest entry stays governed by spec 059 and Camden's own arming act; this
spec changes how a digest is computed, not who may record it.

## FR-004 — Rule 12 proof

`tests/test_059_mutation_suite_runner.py::test_record_is_written_as_the_lf_bytes_the_repository_stores`
emulates a CRLF platform on any OS by setting `newline="\r\n"` on every default text-mode
`io.open`/`open` (the argument that decides whether text output gains a CR; `Path.write_text` and
the builtin `open` both reach it). Its control asserts that emulation is live: `write_text("a\n")`
gives `b"a\r\n"`. It then requires the record to contain no CR, to equal `record_bytes` of itself,
and the printed digest to be SHA-256 over the bytes on disk.

`tests/mutation/run_067_lf_record_mutants.py` plants three plausible regressions in place, one at a
time, and restores the runner's exact bytes: `write_text` restored, a builtin text-mode `open` without
`newline`, and a digest taken over the unterminated text instead of the file. Each must turn the test
red. Source: the driver run on 2026-11-13 printed `3/3 killed`, and the runner's SHA-256 was
identical before and after it.

## Out of scope (follow-ups, not changed here)

- **Other evidence producers still use `write_text`:** `scripts/restore_drill.py` (drill evidence),
  `scripts/paper_report.py`, `scripts/run_059_t004.py` and `scripts/report_058.py`. Any of their
  outputs that a manifest hashes carries the same risk. Each needs its own audit against FR-003.
- **`apply_item1.py`** lives in Camden's packet folder, not the repository. Camden updates it to
  FR-003 rule 3 (refuse CR, cross-check the printed digest).
- The live gate manifest, every evidence file, `exec/`, pins and anything armed are untouched.

## Landing

This changes `scripts/run_mutation_suite.py` and adds tests only. It does not change the manifest,
any evidence file or any pinned file, so the arming digest is unaffected. It still changes main's
tree, and LIVE is armed at pin `0a6b5ff` (first run 2026-11-16). Merge only after the v1.2 tag, with
Camden's go-ahead, and with any repin planned by Camden. The next item 1 refresh after merge is the
first to use FR-002's printed digest, and its record gains one driver row (`run_067_lf_record_mutants.py`).

## Tasks

- [x] T001 Spec (this file).
- [x] T002 FR-001/FR-002 in `scripts/run_mutation_suite.py`.
- [x] T003 FR-004 test in `tests/test_059_mutation_suite_runner.py`; red on the unfixed runner
  ("067 LF record contains CR"), green after T002.
- [x] T004 FR-004 driver `tests/mutation/run_067_lf_record_mutants.py`, 3/3 killed.
- [x] T005 Full suite: `python -m pytest tests` (result in the PR body).
