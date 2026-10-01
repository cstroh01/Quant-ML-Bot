# Triage of `review-phase1.md` (5 P1, 5 P2)

Date: 2026-10-01. Unattended cloud run (Rule 10 cloud scheduled-session lane),
Linux, Python 3.12.3. Scope of this run: triage every finding; implement only
accepted fixes that touch **Phase 1 test/support files**. Nothing in `scripts/`,
`reports/`, `docs/trials/`, or spec 044 was edited.

| # | Sev | Spec | Disposition | Implemented here? |
|---|---|---|---|---|
| F1 | P1 | 044 | Accept | No — 044 R2, queue item 5 |
| F2 | P1 | 044 | Accept | No — 044 file scope |
| F3 | P1 | 044 | Accept | No — 044 file scope |
| F4 | P1 | 043 | Accept; mostly already fixed on `main`, remainder fixed here | Yes |
| F5 | P1 | 043 | Accept | Yes |
| F6 | P2 | 044 | Accept | No — 044 R10, queue item 5 |
| F7 | P2 | 044 | Accept | No — 044 file scope |
| F8 | P2 | 044 | Accept | No — 044 file scope |
| F9 | P2 | 043 | Accept (evidence wording only); resolves at T021 | Recorded here |
| F10 | P2 | 043 | Accept | Yes |

## Spec 043 findings

### F4 — strict xfail markers — accept

- **State on `main` (3e52db9):** all 14 nodes already carry
  `xfail(strict=True)`; the clean-main suite reports `14 xfailed`. The
  "no marker in any file" part of the finding is already fixed.
- **Remaining defect:** `test_043_entry_points.py` used one module-level
  `pytestmark`, so E1–E4 (green at T025, U2) and E5 (green at T027, U3) shared a
  single mark. The review requires separate marks because they flip in
  different units.
- **Fix (done):** module `pytestmark` replaced by per-parameter marks
  `RED_UNTIL_U2` (E1–E4) and `RED_UNTIL_U3` (E5 and the new F5 contract). Root
  and registry cases were already per-test. Enabled control and incident keep
  their module marks (one node each).

### F5 — E5 can pass with a permanently closed route — accept

- **Why it is right:** the old oracle accepted any two ledger-silent 409s
  containing `--record-trial`. A route that never looks anything up passes it.
  AC-10's green branch ("after recording, it returns 200 from the recorded
  trial; two identical GETs change zero bytes and leave N unchanged") was not
  tested at all.
- **Fix (done):**
  1. New red contract `test_e5_serves_recorded_configuration_read_only`
     (strict xfail, U3). The child (`E5_recorded`) records through the E1 CLI
     with `--record-trial`, then **replaces `run_backtest`,
     `research_attempt` and `baseline_results` in the route module with a
     function that raises**, then makes two identical GETs. A 200 therefore
     cannot come from a fresh evaluation, and an unconditional 409 fails.
     `assert_e5_served` requires: exit 0; total bytes = exactly the E1
     recording (44 records, 22 sidecars); both GETs 200; zero byte deltas per
     GET; `n_post_ledger` unchanged per GET; identical response bodies (SHA-256).
  2. The 409 branch now goes through `assert_e5_refused`: zero byte deltas,
     N unchanged per request, and the body names the full recording command —
     `ma_crossover_backtest` **and** `--record-trial` (T027: "the recording
     command is the E1-style CLI"). A vague "pass --record-trial" no longer
     satisfies it.
  3. Each GET now records `n_before`/`n_after` (via `verify()`) and the body hash.
- **Observed red today, right reason:** `E5_recorded` exits 2 at argparse
  rejecting the unimplemented `--record-trial` (same reason as the enabled
  control); 0 records, 0 sidecars. It turns green only after T025 **and** T027.
- **Rule 12:** `test_e5_served_rejects_each_planted_defect` plants four
  plausible defects against `assert_e5_served` — unconditional 409, recompute
  per view (pre-043 route), N bump without byte writes, non-identical bodies —
  plus a green control; `test_e5_refused_requires_the_recording_command` plants
  the vague-409 body. Mutant proof: deleting the `status == 200` assertion
  turns `test_e5_served_rejects_each_planted_defect[planted0-…]` red.
- **Open question for Camden (not decided here):** spec D-2's table notes the
  route's runner string (`reports/api/routes/backtest.py:run_backtest`) differs
  from E1's (`scripts/ma_crossover_backtest.py:run_backtest`), "so it is a
  separate configuration", while D-2 A1 / T027 make the E1 CLI the recording
  command. T027 therefore has to define how GET's lookup key matches a trial
  recorded by E1 (e.g. config hash excluding the runner, or a route-specific
  `--record-trial` target). The new contract is deliberately agnostic: it only
  requires that recording via the command the 409 names makes GET serve 200.
  If Camden picks a different recording command, `E5_RECORDING_COMMAND` and the
  `E5_recorded` child branch change with it.

### F9 — six root cases red at one prerequisite — accept (wording)

- The six `test_project_root_contract` parameters all stop at
  `assert source.exists()` (`_project.py` missing). That is one shared
  missing-resolver red plus six **pending** semantic contracts, not six
  independently observed reds.
- Per-parameter strict-xfail marks are already in place, so after T021 each
  case independently XPASSes (and must lose its marker in that PR) or stays red
  for its own assertion. No code change needed; T021's PR must report which of
  the six went green and, for any still red, the assertion it stopped at.

### F10 — `run_child` mutates the checkout — accept

- **Confirmed in this run:** the clean-`main` suite created an untracked
  `.specify/specs/043-ledger-write-guard/artifacts/phase1-events.jsonl` in
  the checkout. (This run left that file in place uncommitted; it is not part
  of the PR.)
- **Fix (done):** `run_child` returns its evidence as `result["evidence"]` and
  writes nothing under `REPO`. Harvesting into a file is an explicit act: set
  `SPEC043_EVIDENCE_LOG=<path>`.
- **Rule 12:** `test_run_child_leaves_the_checkout_untouched` runs `run_child`
  against a stand-in repository and asserts its file set is unchanged. Mutant
  proof: restoring the old default destination (`REPO/…/phase1-events.jsonl`)
  turns it red, naming the path. `test_run_child_harvests_evidence_only_when_named`
  is the opt-in control.

## Spec 044 findings (triage only; not implemented in this run)

| # | Accept? | Reason | Exact fix |
|---|---|---|---|
| F1 (R2) | Accept | Comparing median volume across *different* sessions cannot identify the provider's share basis; activity is an uncontrolled cause of post/pre. "Internal consistency" evidence cannot select a verified branch. | Q-P4 may only emit `provider_unverified` unless a same-observation or primary-source contract identifies the convention. Keep the median ratio as a recorded diagnostic. Add a self-check case where the heuristic is unanimous and the output is still `provider_unverified`. |
| F2 | Accept | A response ending after `last_completed_session` gives a reversed (empty) interval, so lag = 0 and future rows pass. | In spec and `p1_probe.py`, require `last_response_session <= last_completed_session` before measuring lag; reject otherwise. Self-check: a future-session planted case (red) and a same-session control (green). |
| F3 | Accept | `--self-check` never exercises Q-P1, Q-P3, D-3, `read_inputs` or aggregation/writing, so those gates have no red proof (Rule 12). | Offline fixtures that make each decision gate fail for its named defect plus a passing control; include F2's future-session case and F7's rejections. |
| F6 (R10) | Accept | A 382-line Unit 0 exceeds the stated hard 300-line cap; "two reading passes" does not divide the unit. | Split the probe physically so each committed unit is ≤300 changed lines, or amend SC-007 openly. Queue item 5 takes the split. |
| F7 | Accept | Blank `accession`/`source_url`, invalid `form`, duplicate `(ticker, ex_date)` and arbitrary `--revision` all pass silently. | Reject each in `read_inputs`/Q-P3 (duplicates detected before the dict comprehension; tickers restricted to the basket; revision = full 40-hex SHA). Plant each in the self-check. |
| F8 | Accept | `Dividends > 0` filters NaN/negative cells out before `positive()` sees them, contradicting FR-013. | Validate the whole `Dividends` column first (finite, ≥0; 0 means no dividend), then select events. Self-check planted NaN and negative cases. |

## Counts after this run

`python -m pytest tests` (Linux, Python 3.12.3): see the PR body. The expected
xfail count rises from 14 to 15 (the new F5 contract).
