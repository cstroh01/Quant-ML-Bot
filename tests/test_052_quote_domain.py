"""052 T008: quote domains cannot silently disable executable exclusions. Synthetic only."""
import dataclasses
from datetime import date, datetime, timedelta, timezone

import pytest

import context  # noqa: F401
from asset_registry import EligibilityLimits, ExecutableQuote, executable_eligibility

NOW = datetime(2026, 10, 8, 13, 25, tzinfo=timezone.utc)
LIMITS = EligibilityLimits(5, 5.0, 1_000_000.0, 50.0, 0.01)
QUOTE = ExecutableQuote(True, False, date(2026, 10, 7), "us_equity", 10.0, 100_000.0, 1.0,
                        NOW - timedelta(seconds=5))
KW = dict(previous_session=date(2026, 10, 7), allowed_classes=("us_equity",), order_qty=500,
          order_notional=10_000.0, limits=LIMITS, now=NOW, max_quote_age_seconds=60)


@pytest.mark.parametrize("age", [float("inf"), float("nan"), float("-inf"), -1, True, "bad", None],
                         ids=["infinite", "nan", "negative-infinite", "negative", "boolean", "nonnumeric", "missing"])
def test_invalid_age_configuration_refused(age):
    with pytest.raises(ValueError, match="max_quote_age_seconds"):
        executable_eligibility(QUOTE, **(KW | {"max_quote_age_seconds": age}))


def test_finite_age_control_still_distinguishes_stale_from_fresh():
    stale = dataclasses.replace(QUOTE, quoted_at=NOW - timedelta(seconds=61))
    assert executable_eligibility(stale, **KW) == ["stale_quote"]
    assert executable_eligibility(QUOTE, **KW) == []


def test_zero_age_accepts_only_the_exact_instant():
    exact = dataclasses.replace(QUOTE, quoted_at=NOW)
    assert executable_eligibility(exact, **(KW | {"max_quote_age_seconds": 0})) == []
    assert executable_eligibility(QUOTE, **(KW | {"max_quote_age_seconds": 0})) == ["stale_quote"]


@pytest.mark.parametrize("field,reason", [("spread_bps", "spread_invalid"),
                                         ("min_notional_usd", "broker_minimum_invalid")])
@pytest.mark.parametrize("bad", [-1.0, -100.0])
def test_negative_quote_domain_refused_with_valid_sibling(field, reason, bad):
    invalid = dataclasses.replace(QUOTE, **{field: bad})
    assert reason in executable_eligibility(invalid, **KW), f"{reason}: negative domain admitted"
    assert executable_eligibility(QUOTE, **KW) == []


def test_zero_spread_and_zero_minimum_are_valid_boundaries():
    zero = dataclasses.replace(QUOTE, spread_bps=0.0, min_notional_usd=0.0)
    assert executable_eligibility(zero, **KW) == []
