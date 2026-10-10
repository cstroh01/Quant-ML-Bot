"""Spec 058 T007 (FR-002, D-3): the holdout seal.

EXAMPLE — NOT A RESULT. Synthetic frames only; spend records live under pytest's tmp_path.
"""
import hashlib
import json

import pandas as pd
import pytest
from context import SCRIPTS_DIR
import data
import data_sources
from data_sources import HoldoutSealError, HoldoutToken, require_holdout_token, sealed_sessions

DECLARATION = SCRIPTS_DIR.parent / ".specify/specs/058-edge-research-program/declaration.json"
SELECTED = hashlib.sha256(b"selected configuration").hexdigest()
OTHER = hashlib.sha256(b"another configuration").hexdigest()


def frame(*labels):
    index = pd.DatetimeIndex(pd.to_datetime(list(labels)), name="date")
    return pd.DataFrame({"close": range(1, len(labels) + 1)}, index=index, dtype=float)


def test_cutoff_matches_the_declaration_and_the_calendar():
    body = json.loads(DECLARATION.read_text(encoding="utf-8"))
    assert str(data_sources.RESEARCH_END) == body["research_end"], "T007 CUTOFF research_end"
    assert str(data_sources.HOLDOUT_START) == body["holdout_start"], "T007 CUTOFF holdout_start"
    sessions = data.trading_days(data_sources.RESEARCH_END, data_sources.HOLDOUT_START)
    assert sessions == [data_sources.RESEARCH_END, data_sources.HOLDOUT_START], "T007 CUTOFF adjacent sessions"


def test_last_research_session_is_open_and_first_holdout_session_is_sealed():
    marks = sealed_sessions(frame("2023-09-28", "2023-09-29", "2023-10-02", "2023-10-03").index)
    assert marks.tolist() == [False, False, True, True], "T007 CUTOFF boundary"


def test_weekend_labels_in_the_gap_are_sealed():
    marks = sealed_sessions(frame("2023-09-29", "2023-09-30", "2023-10-01").index)
    assert marks.tolist() == [False, True, True], "T007 CUTOFF gap"


def test_research_window_needs_no_token_and_spends_nothing(tmp_path):
    spent = tmp_path / "holdout.spent"
    research = frame("2023-09-27", "2023-09-28", "2023-09-29")
    out = require_holdout_token(research, config_hash=SELECTED, token=HoldoutToken(SELECTED), spent_path=spent)
    assert out is research, "T007 CUTOFF research frame altered"
    assert not spent.exists(), "T007 CUTOFF research window spent the token"


def test_sealed_session_without_token_is_refused(tmp_path):
    with pytest.raises(HoldoutSealError, match="sealed"):
        require_holdout_token(frame("2023-09-29", "2023-10-02"), config_hash=SELECTED,
                              spent_path=tmp_path / "holdout.spent")
    assert not (tmp_path / "holdout.spent").exists(), "T007 SEAL refusal spent the token"


def test_first_holdout_session_alone_is_refused_without_token(tmp_path):
    try:
        require_holdout_token(frame("2023-10-02"), config_hash=SELECTED, spent_path=tmp_path / "s")
    except HoldoutSealError:
        return
    raise AssertionError("T007 CUTOFF 2023-10-02 served without a token")


def test_token_opens_the_holdout_once_and_records_the_spend(tmp_path):
    spent = tmp_path / "holdout.spent"
    holdout = frame("2023-09-29", "2023-10-02", "2024-01-02")
    out = require_holdout_token(holdout, config_hash=SELECTED, token=HoldoutToken(SELECTED), spent_path=spent)
    assert out is holdout, "T007 ONCE first use refused"
    record = json.loads(spent.read_text(encoding="utf-8"))
    assert record == {"config_hash": SELECTED, "first_session": "2023-10-02", "last_session": "2024-01-02"}, "T007 ONCE record"


def test_second_use_of_the_token_is_refused(tmp_path):
    spent = tmp_path / "holdout.spent"
    holdout = frame("2023-10-02", "2023-10-03")
    require_holdout_token(holdout, config_hash=SELECTED, token=HoldoutToken(SELECTED), spent_path=spent)
    before = spent.read_bytes()
    try:
        require_holdout_token(holdout, config_hash=SELECTED, token=HoldoutToken(SELECTED), spent_path=spent)
    except HoldoutSealError as error:
        assert "already been opened" in str(error), f"T007 REUSE wrong refusal: {error}"
    else:
        raise AssertionError("T007 REUSE second use served the holdout")
    assert spent.read_bytes() == before, "T007 REUSE spend record rewritten"


def test_token_bound_to_another_configuration_is_refused_and_spends_nothing(tmp_path):
    spent = tmp_path / "holdout.spent"
    try:
        require_holdout_token(frame("2023-10-02"), config_hash=SELECTED, token=HoldoutToken(OTHER), spent_path=spent)
    except HoldoutSealError as error:
        assert "different configuration" in str(error), f"T007 BIND wrong refusal: {error}"
    else:
        raise AssertionError("T007 BIND token for another hash opened the holdout")
    assert not spent.exists(), "T007 BIND refusal spent the token"


def test_opening_without_a_spend_record_is_refused():
    with pytest.raises(HoldoutSealError, match="spend record"):
        require_holdout_token(frame("2023-10-02"), config_hash=SELECTED, token=HoldoutToken(SELECTED))


@pytest.mark.parametrize("bad", ["", "abc", SELECTED.upper(), None])
def test_token_needs_a_sha256_hash(bad):
    with pytest.raises(HoldoutSealError, match="SHA-256"):
        HoldoutToken(bad)


def test_aware_or_non_datetime_index_is_refused():
    aware = frame("2023-09-29").tz_localize("America/New_York")
    with pytest.raises(ValueError, match="naive"):
        sealed_sessions(aware.index)
    with pytest.raises(ValueError, match="DatetimeIndex"):
        sealed_sessions(pd.RangeIndex(3))


def test_nat_label_is_refused_not_served():
    index = pd.DatetimeIndex([pd.Timestamp("2023-09-29"), pd.NaT])
    try:
        sealed_sessions(index)
    except ValueError as error:
        assert "NaT" in str(error), f"T007 NAT wrong refusal: {error}"
    else:
        raise AssertionError("T007 NAT label passed the seal")
