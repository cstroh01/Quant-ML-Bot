"""Queue Q111 follow-up: the allocation's cash buffer must leave headroom under the gate's gross cap.

The safety gate prices every held position at the last close plus the loop's ``GAP_ALLOWANCE``.
With ``ALLOCATION_CASH_BUFFER`` equal to that allowance, a fully deployed book reads as gross
(1 - 0.05) * 1.05 = 0.9975 -- 0.25% under the cap. The real-data replay of 2020-02-03..2020-04-30
(Tiingo bodies from 058 T008) then denied a TLT buy on four sessions running (MAX_GROSS_PCT_BREACH,
gross 5010-5032 on ~5000 equity): ordinary drift between the decision close and the buy day used
up the 0.25%. A 7% buffer passed both §11.3.5 windows with no denial, abort or error.
"""
from __future__ import annotations

import sys
from pathlib import Path

import context  # noqa: F401 -- makes scripts importable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

from paper_loop import ALLOCATION_SAFETY_CONFIG, GAP_ALLOWANCE  # noqa: E402
from paper_targets import ALLOCATION_CASH_BUFFER, plan_allocation  # noqa: E402

# Minimum slack between a fully deployed book's worst-case gross and the gate cap. Daily moves of
# 1-2% between the decision close and a deferred buy are routine for the bond and gold sleeves.
MIN_GROSS_HEADROOM = 0.015


def test_fully_deployed_book_leaves_headroom_under_the_gross_cap():
    worst_case_gross = (1.0 - ALLOCATION_CASH_BUFFER) * (1.0 + GAP_ALLOWANCE)
    headroom = ALLOCATION_SAFETY_CONFIG.max_gross_pct - worst_case_gross
    assert headroom >= MIN_GROSS_HEADROOM, (
        f"Q111 HEADROOM: worst-case gross {worst_case_gross:.4f} leaves {headroom:.4f} under the "
        f"{ALLOCATION_SAFETY_CONFIG.max_gross_pct} cap; need >= {MIN_GROSS_HEADROOM}")


def test_planner_default_is_the_module_buffer():
    assert plan_allocation.__kwdefaults__["cash_buffer"] == ALLOCATION_CASH_BUFFER
