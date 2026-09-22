# Spec 033 source discrepancy — approved correction

Status: APPROVED by Camden on 2026-09-22 and applied. Approval explicitly
covers only the numeric source correction below, not T031/T032 backfill.

The controlling primary paper is Bailey and Lopez de Prado (2014),
https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf, printed pages 9–10.
The locally inspected source and page images are in this directory. The
downloaded PDF's hash, transcribed inputs, independent standard-library
calculation, and UTC calculation date are in `paper-oracle-check.json`.

**EXAMPLE — NOT A RESULT:** the paper specifies annualized Sharpe 2.5, annualized
trial-Sharpe variance 0.5, 1,250 observations, 250 observations/year, skewness
−3, and Pearson kurtosis 10. Its main example uses N=100 and reports 0.9004.
Its N=46 control reports 0.9505. The paper's separate N=88 paragraph changes
the moments to normal returns (skewness 0, kurtosis 3); it is not the original
non-normal case.

**EXAMPLE — NOT A RESULT:** holding the original non-normal inputs fixed and
using N=88 gives 0.910153014744707, not 0.905 ± 0.001. Both SciPy primitives
in the implementation and an independent Python `statistics.NormalDist`
calculation agree. This still fails the unchanged 0.95 threshold, and the
unchanged N=46 control passes.

Approved narrow correction: preserve N=88/N=46,
raw lifetime counting, all thresholds, formulas, and fixed non-history inputs;
change the asserted N=88 DSR target from 0.905 to 0.910153014744707 throughout
FR-027, T036, Rule 12 fixture descriptions, and their corresponding examples.
Describe N=88 as an evaluation of the paper's inputs, while retaining an
additional test of the paper's actual published N=100 result.

T036/T046 verification is recorded in `T046-approved-correction-green.txt`.
Original red logs and the independent paper oracle remain unchanged.
The current authorized scope ends after Phase 7; no Gate 3 artifact/API work.
