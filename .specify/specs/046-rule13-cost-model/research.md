# 046 research record — published-source verification (FR-001, SC-001)

Approval: Camden, 2026-10-09 (gate packet `claude/gate-packet-20261009.md`; 046 spec.md
"T001 source review — APPROVED"). Recorded here 2026-10-15; no decision changes.

## 1. Half-spread source
- Ardia, Guidotti & Kröncke (2024), *Journal of Financial Economics* 161, 103916,
  doi:10.1016/j.jfineco.2024.103916, CC BY 4.0.
- Estimator: EDGE, Eqs. (23)–(25), p. 6. Implemented as the authors' reference algorithm
  `bidask` v2.1.0 (MIT), which adds return de-meaning to the printed equations.
- Convention: S is the full relative effective spread (Eq. (1), p. 3). A fill pays S/2.
- Minimum data (p. 9): at least 3 observations.

## 2. Impact source
- Tóth et al. (2011), *Physical Review X* 1, 021006, doi:10.1103/PhysRevX.1.021006.
- impact = Y · σ_daily · √(Q / ADV); Y = 1.0 preregistered (D-1), not calibrated; 0.5 and 2.0 are
  labelled robustness rows only.

## 3. Conventions as implemented (`scripts/cost_model.py`, `CONVENTIONS`)
- Window (D-2): 21 NYSE sessions trailing through t for a t+1 fill. Compatible with the paper's
  ≥3-observation minimum.
- σ: 21 daily close-to-close log returns from the 22 closes t−21..t, ddof = 1, not annualized.
- ADV: mean share volume over t−20..t, on Q's split basis. `volume_basis` must be
  `nominal_reconstructed` or `provider_nominal`. A split inside the window refuses.
- Warm-up: refuse until 22 sessions through t exist; never zero, shortened or stale.

## 4. Deliberate deviations from the paper
1. Negative S²: spread = √|S²| (G1-N = b), not the paper's §3.2 reset to zero. A zero spread would understate cost.
2. Undefined S (fewer than 2 informative bars, or zero open/close probabilities): refuse the fill
   (`CostUnavailable("spread_undefined")`), never zero.
3. Malformed days: the paper drops days with missing O/H/L/C or O/C outside [L, H] (p. 9). This
   implementation refuses the whole estimate (`malformed_bar`) instead of dropping the day, so a window
   never silently shrinks below 21 sessions. Conservative: it skips the order rather than costing it on fewer days.

## 5. Numerical oracle (independently checked 2026-10-09)
- `bidask==2.1.0`, test-only dependency, absolute tolerance 1e-12.
- Fixture: seed 20261009, 21 sessions, true spread 0.01 → 0.007795522223312195.
- Negative case: seed 1, true spread 0.0005 → signed −0.003000259646810344 (as recorded in spec.md).
- Fixture generator: private, Codex lane.
- Test: `tests/test_046_cost_model.py::test_half_spread_matches_bidask_oracle`. Mutants M7 (full spread as
  half; negative S² → 0) are killed: `artifacts/u1.txt`.

## 6. Scope of this record
Establishes the source and conventions only. It is not real-data acceptance (T015, SC-006). It is not
a Gate 3 or capital-readiness claim. Costs remain "modeled, not calibrated against real fills".
