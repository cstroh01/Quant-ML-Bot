# Spec 018 handoff

_Written 2026-09-12 by the agent that ran steps 1–3. No `git` command was run.
No production code was written or modified. Camden reviews `spec.md`, `plan.md`
and `tasks.md` before anything is implemented._

Artifacts:
- [spec.md](../../.specify/specs/018-terminal-truthfulness/spec.md)
- [plan.md](../../.specify/specs/018-terminal-truthfulness/plan.md)
- [tasks.md](../../.specify/specs/018-terminal-truthfulness/tasks.md)
- [research.md](../../.specify/specs/018-terminal-truthfulness/research.md)
- [data-model.md](../../.specify/specs/018-terminal-truthfulness/data-model.md)
- [contracts/](../../.specify/specs/018-terminal-truthfulness/contracts/)
- [quickstart.md](../../.specify/specs/018-terminal-truthfulness/quickstart.md)
- [checklists/requirements.md](../../.specify/specs/018-terminal-truthfulness/checklists/requirements.md)

---

## 1. Step 1 — Spec Kit folder configuration

### What controls it

**There is no configuration setting.** `.specify/init-options.json` has no
path key, and `SPECIFY_FEATURE_DIRECTORY` is a per-feature override, not a
base directory. The root `specs/` path is hardcoded in exactly the two places
that create a new spec:

1. **The bash script** used by the Spec Kit workflow.
2. **The Claude skill.** This is the one that actually runs for
   `/speckit.specify` in this repository, because the skill creates the
   directory itself and never calls the script.

`/speckit.plan` and `/speckit.tasks` resolve paths through
`.specify/feature.json`, so they needed no change.

### Changes (before → after)

**File 1: `.specify/scripts/bash/create-new-feature.sh`, line 200**

```diff
- SPECS_DIR="$REPO_ROOT/specs"
+ SPECS_DIR="$REPO_ROOT/.specify/specs"
```

**File 2: `.claude/skills/speckit-specify/SKILL.md`, lines 84–93**

| Line | Before | After |
|---|---|---|
| 84 | `Specs live under the default \`specs/\` directory unless the user explicitly provides \`SPECIFY_FEATURE_DIRECTORY\`.` | `Specs live under this project's \`.specify/specs/\` directory unless the user explicitly provides \`SPECIFY_FEATURE_DIRECTORY\`. (Project override: …a root \`specs/\` would start a second numbering sequence. See \`.specify/scripts/bash/create-new-feature.sh\`, which resolves the same path.)` |
| 88 | `2. Otherwise, auto-generate it under \`specs/\`:` | `2. Otherwise, auto-generate it under \`.specify/specs/\`:` |
| 91 | `…after scanning existing directories in \`specs/\`)` | `…after scanning existing directories in \`.specify/specs/\`)` |
| 93 | `Set \`SPECIFY_FEATURE_DIRECTORY\` to \`specs/<directory-name>\`` | `Set \`SPECIFY_FEATURE_DIRECTORY\` to \`.specify/specs/<directory-name>\`` |

**Machine-local state, not a configuration change:**
`.specify/feature.json` changed from
`{"feature_directory":".specify/specs/017-position-sizing-risk"}` to
`{"feature_directory":".specify/specs/018-terminal-truthfulness"}`. It is
gitignored (`.specify/.gitignore:6`).

### Verification (before any spec was created)

| Run | Result |
|---|---|
| Dry run **before** the change | `{"BRANCH_NAME":"001-terminal-truthfulness","SPEC_FILE":".../specs/001-terminal-truthfulness/spec.md","FEATURE_NUM":"001"}` — the second numbering sequence |
| Dry run **after** the change | `{"BRANCH_NAME":"018-terminal-truthfulness","SPEC_FILE":".../.specify/specs/018-terminal-truthfulness/spec.md","FEATURE_NUM":"018"}` |
| After, with `--number 17` (already used) | `Warning: --number 017 conflicts with an existing spec directory; using 018 instead`, then 018 |
| Root `specs/` directory | Does not exist; nothing was created there |

The dry runs used the script's own `--dry-run` mode, which creates nothing.

### Left unchanged, stated so it is not mistaken for done

- **Illustrative text still says `specs/`:** `SKILL.md:107` (an example path),
  `.specify/templates/plan-template.md:5` and `:50`, and
  `.specify/templates/tasks-template.md:8`. These are template text only; they
  do not decide where a spec is created, and spec 018's own documents state
  the correct path.
- **Manifest hashes still describe the original files**:
  `.specify/integrations/speckit.manifest.json:6` and
  `.specify/integrations/claude.manifest.json:13`. A future Spec Kit refresh or
  upgrade may flag both edited files as modified, or overwrite them back to
  `specs/`. The durable fix is a supported override with a dry-run test, which
  is finding 65 (spec 041). Rerun the dry run after any Spec Kit upgrade.

---

## 2. Finding IDs in scope

Exactly the 15 findings REMEDIATION_PLAN.md assigns to Stage 3.1. Each is
mapped to file and line in `spec.md` → *Scope*.

| ID | P | Summary | User story / PR |
|---|---|---|---|
| 45 | P0 | Literal significance p-values | US1 / B |
| 46 | P0 | Literal P(Up)/logit; rules shown as ML | US1 / B |
| 47 | P0 | Hardcoded Gate 1 pass, "301", header "311/311" | US1 / B |
| 48 | P1 | `holding_bars=1`; commission-only friction; rounded export | US4 / D |
| 49 | P1 | Gate decoder mismatch, p-value tutoring, Kelly, 0.00 for unknown correlation, volume narrative | US5 / E (rundown part in B) |
| 36 | P1 | Conditioning presented as proof | US5 / E (`capital_gate.py:28` in B) |
| 54 | P1 | CV illustration unlabelled; SMA tearsheet beside ML labels | US5 / E |
| 03 | P0 | NaN fills, NaN signals, NaN "reconciles", literal reconciliation flag | US2 / C |
| 04 | P0 | Cost checks accept NaN/inf; slippage 10000 accepted | US2 / C |
| 50 | P1 | Invalid requests return 500 or 200 | US2 / C |
| 51 | P1 | CORS wildcard with credentials | US6 / F |
| 29 | P1 | Unfavoured one-sided McNemar tail | US4 / D |
| 35 | P1 | Pseudo-inverse VIF on singular/constant columns | US4 / D |
| 57 | P1 | API tests fail on a clean checkout | US3 / A |
| 58 | P1 | Independent oracles; in-repository mutation scripts | A (runner), B–D (oracles), G (closure) |

**Excluded explicitly** (`spec.md` → *Explicitly excluded*):
- Real inference, saved-run artifacts and an experiment store are Stage 3.3.
  Stage 3.1 replaces every fabricated value with a *not computed* state and
  constructs nothing.
- Findings 26 and 30 stay open.
- Three of finding 58's six oracles are deferred (see §4c).

---

## 3. CI root cause (finding 57)

Three independent causes; fixing one leaves the other two.

1. **CI cannot import the API test module.**
   - `.github/workflows/test.yml:16` installs only `requirements.txt`.
   - `tests/test_reports_api.py:10` imports `fastapi.testclient` at module
     level.
   - `fastapi` and `httpx` are declared only in
     `reports/requirements-ui.txt:7-9`.

   Test discovery raises `ImportError`, which unittest records as an error, so
   the job fails before any API assertion runs. *This is derived from the
   workflow and requirements files. The remote CI run history was not
   inspected, which would need `git`/GitHub access; treat "CI is currently red"
   as inferred, not observed.*
2. **Six tests read the developer's gitignored cache.**
   - `get_cached_ticker_data` (`reports/api/routes/data.py:26-57`) reads the
     module-level `CACHE_DIR = data/cache/` (`scripts/data.py:46`).
   - That directory is ignored by `.gitignore:19`, and every CSV by `*.csv` at
     `:20`.
   - With no seam to supply data, a clean checkout reaches the 404 at `:57`.
3. **One test needs a built frontend.** `test_static_frontend_root` requires
   `reports/web/dist`.
   - That directory is build output, ignored by `reports/web/.gitignore:11`.
   - It is mounted at import time, and only if it exists
     (`reports/api/main.py:54-56`).
   - CI never builds it.

**Why nobody noticed.** Three of the four tests that pass on a clean checkout
pass *because* they assert fabricated or fallback values:
- the four hardcoded significance entries
- the hardcoded Gate 1 pass
- the hardcoded fallback ticker list (`data.py:72-74`)

**Common root.** Spec 016's API tests were written against a warmed working
tree, and CI was not updated alongside them.

**The fix** (research R4, R5):
- a FastAPI dependency seam for the cache directory
- an app factory for static assets
- seeded synthetic fixtures generated inside the tests
- installing the already-declared `reports/requirements-ui.txt`
- a separate `web` job for `npm ci`, lint and build

Nothing pins local state, commits data, or skips a test.

---

## 4. Contradictions with REMEDIATION_PLAN.md, and other flags

### a. Spec grouping

The plan proposes 018 = 45, 46, 47, 48, 49, 36, 54; 019 = 03, 04, 50, 51;
020 = 29, 35; and 021 = 57, 58. The run request put all 15 findings in spec 018,
and that instruction was followed.

The plan's own size rule then strains. The mitigation is eight PRs, A through
G with B spanning US1 (`plan.md` → *Order of work*). **Camden should confirm
one spec with eight PRs, or split it back into specs 018–021.**

### b. Finding 45's "Change" text conflicts with the run constraint

The plan says "Replace hardcoded p-values … with saved run artifacts." The run
request says this stage deletes and does not construct, and that artifacts are
Stage 3.3. The constraint was followed, so spec 018 delivers only the "tickers
with no run show unavailable" half. The artifact half of 45 needs a home in
spec 028. Finding 47's ↪ already says so; 45's row does not.

### c. Finding 58 — three of six oracles deferred

The plan assigns all six oracles to Stage 3.1. Three have subjects that don't
exist yet, or are about to be rebuilt:
- **The funded-ledger oracle**: no funded ledger exists (023).
- **The overnight-only timing oracle**: the current target fails it by design
  until 022.
- **The planted-signal-versus-noise and whole-pipeline future perturbation
  oracles**: they would pin a timing contract that 022 rebuilds.

The plan's own sentence "Each later spec adds its own oracle" supports
deferring them, but its table does not. Spec 018 adds a fourth oracle instead:
holding bars and cost breakdown.

### d. Finding 49's "Where" column is wrong for one item

The volume-flow narrative is in `reports/api/routes/ml_rundown.py:145-168`, not
`MarketDataView.tsx`, which has no volume narrative.

### e. Findings 26 and 30 — counting ambiguity

The plan lists both as Stage 3.5 findings, but routes a "wording fix" (26) and
a "gate text fix" (30) to 018. They were not counted in the 15. The strings in
question ("Sharpe ≤ 0.3", "Deflated Sharpe remains positive", the friction
advice on a direction reading) are removed anyway, as unsupported claims under
46 and 47. No replacement criterion is defined, and both findings stay open.

### f. The pass condition exists in two wordings

Codex's wording at `AUDIT.md:229` is "…clean API fixtures". The plan's
`REMEDIATION_PLAN.md:71-74` rewords it to "API tests pass on a clean checkout
with fixtures", which is stronger. Spec 018 quotes both verbatim and holds
itself to the stronger one.

### g. The plan's Stage 3.1 differs from Codex's work order 1

`AUDIT.md:229` lists 03–04, 45–50 and 57–58, ten IDs. The plan adds five more:
- **29**: in Codex's work order 5 (25–30).
- **51**: in work order 6 (51–63).
- **54**: in work order 6 (51–63).
- **35**: in no work-order row.
- **36**: in no work-order row.

The plan is authoritative for scope, so these were followed.

### h. Finding 48 "spread"

The harness models commission and slippage only. Spread is reported as *not
modeled*, never zero. Computing holding bars and the cost breakdown from the
request's own simulation is treated as correcting a derivation, not
"constructing" a number. The interpretation is recorded in `spec.md` with its
fallback. **Camden should confirm.**

### i. Finding 51 "bind to loopback" is already satisfied

`reports/api/main.py:62` already binds `127.0.0.1`. Only CORS is defective. The
bind is pinned by a test so it stays that way.

### j. Line references

| Finding | Plan cites | Correction |
|---|---|---|
| 29 | `feature_set_comparison.py:348` | That is the function definition; the defect is at `:391-402` |
| 45 | `diagnostics.py:92` | The audit cites `:90`; the literals span `:92`–`:116` |

### k. Precedent attribution in the run request

The request said the AST and mutation precedent was set by specs 003, 007 and
012. **Specs 003 and 007 contain no AST or mutation check.** Spec 003 sets
synthetic-data proof tests, and spec 007 sets "must fail against the pre-fix
code". The AST and mutation shape comes from specs 012 and 017 (and 009–011,
013, 014). Spec 018 follows all of them and cites each accurately.

### l. "Clean at audit time" is local, not CI

The plan's "541 unit tests pass" was on the warmed local tree. On a clean
install, CI cannot import the API tests (§3).

---

## 5. Found and not fixed (out of scope; recorded so they are not lost)

- **Hardcoded risk-free rate.** `BacktestTearsheetView.tsx:133` and `:170`
  hardcode "Rf = 3.78% (3m T-Bill)" (finding 12, Stage 3.2).
- **Tutoring outside finding 49's named files.** `BacktestTearsheetView.tsx:171-172`
  has Sharpe tiers and "beats the Random Baseline by more than 2 standard
  deviations" (findings 32 and 49 in spirit; candidates for 029 or 038).
- **The rundown is still one session stale.** Its `as_of_date` stays behind
  the raw data (finding 23, Stage 3.2). Spec 018 neither fixes nor labels it.
- **The rundown URL still says "ml".** `/api/ml/rundown` is kept although the
  content becomes rule readings, to avoid renaming a URL no finding requires.
- **Weak McNemar test.** `tests/test_feature_scaling.py:746-752` could not
  detect finding 29; spec 018 extends it.
- **Module table incomplete.** The CLAUDE.md module table has no row for
  `scripts/portfolio_risk.py` (Stage 0.6), and will also need one for
  `scripts/cost_domain.py`. CLAUDE.md was not edited.

---

## 6. Rules that do not exist (constitution not edited)

- **No rule forbids fabricated or unsourced figures in a report or UI.**
  Rule 3 covers only costless figures. FR-037 enforces a project convention
  that the constitution does not state.
- **No rule requires the suite to pass on a clean checkout.** Rule 5 and the
  CLAUDE.md *Tests* section come closest.
- **CLAUDE.md "no test dependencies" conflicts with the API tests.** The API
  test client needs `httpx`, and FR-025 requires the HTTP boundary to be
  tested. The tension is recorded in `plan.md` Complexity Tracking #4 and not
  resolved.

---

## 7. Decisions needed from Camden before `/speckit.implement`

From `plan.md` Complexity Tracking **FLAG** entries, and §4 above:

1. One spec plus eight PRs, or split back into specs 018–021 (§4a).
2. Where the artifact half of finding 45 lives (§4b).
3. Accept deferring three of finding 58's oracles (§4c).
4. Accept the finding 48 scope interpretation, or take the *not computed*
   fallback (§4h).
5. New module `scripts/cost_domain.py`, and a CLAUDE.md table row for it (#1).
6. CI installing `reports/requirements-ui.txt` despite "no test
   dependencies" (#4).
7. The mutation runner under `tests/mutation/` (#5).
8. Appending a dated audit note to spec 014 (#6).
9. Editing, rather than deleting, `scripts/scratch_multiticker_collinearity.py`
   (#7).

---

## 8. What was not done

- No `git` command of any kind.
- No production code written or modified. The only non-spec file edits are
  the two step-1 files and machine-local `.specify/feature.json`.
- `.specify/specs/017-position-sizing-risk/` was read for format precedent
  only, and not modified.
- Spec 013 not run.
- No spec 019 or later created.
- `.specify/memory/constitution.md` and `CLAUDE.md` not edited.
- `/speckit.implement` not run.
