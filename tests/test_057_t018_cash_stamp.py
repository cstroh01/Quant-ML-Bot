"""057 T018 / D-10: the settled-cash stamp bound. Synthetic fakes only; every socket is blocked."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace as NS
import pytest
import context  # noqa: F401
from test_057_q139 import blocked, broker, cash_client  # noqa: F401  (autouse fixture)
import fidelity_live
from fidelity_live import SecurityChallenge

START = datetime(2026, 11, 2, 14, 35, tzinfo=timezone.utc)
READ = START + timedelta(seconds=40)
REAL_CLOCK = fidelity_live._read_clock


def stamp(moment):
    return int(moment.timestamp() * 1000)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(fidelity_live, '_read_clock', lambda: READ)


@pytest.mark.parametrize('moment', [
    START - timedelta(minutes=5), START, START + timedelta(seconds=1), READ,
    READ + timedelta(seconds=60)], ids=['before-start', 'at-start', 'after-start', 'at-read', 'skew-limit'])
def test_stamp_up_to_the_bound_counts(moment):
    cash = broker(cash_client(stamp=stamp(moment))).settled_cash(START)
    assert cash['amount'] == 12.5 and cash['as_of'] == moment.isoformat()


def test_stamp_past_the_skew_is_refused():
    with pytest.raises(SecurityChallenge):
        broker(cash_client(stamp=stamp(READ + timedelta(seconds=61)))).settled_cash(START)


def test_clock_is_read_after_the_balance_response(monkeypatch):
    now = {'value': START}
    monkeypatch.setattr(fidelity_live, '_read_clock', lambda: now['value'])
    client = cash_client(stamp=stamp(START + timedelta(seconds=90)))
    get = client.balances.get_balances
    def respond(accounts):
        now['value'] = START + timedelta(seconds=45)
        return get(accounts)
    client.balances.get_balances = respond
    assert broker(client).settled_cash(START)['amount'] == 12.5


def test_slow_clock_never_lowers_the_bound_below_as_of(monkeypatch):
    monkeypatch.setattr(fidelity_live, '_read_clock', lambda: START - timedelta(hours=1))
    assert broker(cash_client(stamp=stamp(START))).settled_cash(START)['amount'] == 12.5


def test_previous_new_york_day_is_refused_even_inside_the_bound(monkeypatch):
    # 00:30 ET: the stamp at 23:50 ET yesterday precedes the bound but is another session date.
    monday = datetime(2026, 11, 2, 5, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(fidelity_live, '_read_clock', lambda: monday)
    with pytest.raises(SecurityChallenge):
        broker(cash_client(stamp=stamp(monday - timedelta(minutes=40)))).settled_cash(monday)


def test_stamp_on_the_next_new_york_day_is_refused_inside_the_skew(monkeypatch):
    # 23:59:50 ET Monday; 30 seconds later is inside the skew but Tuesday in New York.
    late = datetime(2026, 11, 3, 4, 59, 50, tzinfo=timezone.utc)
    monkeypatch.setattr(fidelity_live, '_read_clock', lambda: late)
    with pytest.raises(SecurityChallenge):
        broker(cash_client(stamp=stamp(late + timedelta(seconds=30)))).settled_cash(late)


def test_newest_snapshot_in_bound_wins():
    def timing(moment, amount):
        return NS(as_of_date_time=stamp(moment), cash_detail=NS(settled_amt=amount, core_balance=1.0))
    balance = NS(acct_num='FIXTURE', recent_balance_detail=timing(READ + timedelta(minutes=5), 1.0),
                 intraday_balance_detail=timing(READ, 2.0), close_balance_detail=timing(START, 3.0))
    client = NS(balances=NS(get_balances=lambda a: NS(accounts=[balance])))
    assert broker(client).settled_cash(START)['amount'] == 2.0


def test_refused_read_records_only_counts_and_offsets():
    b = broker(cash_client(amount=777.77, stamp=stamp(READ + timedelta(seconds=90))))
    with pytest.raises(SecurityChallenge): b.settled_cash(START)
    assert b.diagnostic()['cash_stamps'] == {'snapshots': 1, 'stamp_types': ['int'], 'offsets_s': [90]}
    assert '777' not in json.dumps(b.diagnostic()) and 'FIXTURE' not in json.dumps(b.diagnostic())


def test_accepted_read_adds_no_diagnostic_key():
    b = broker(cash_client(stamp=stamp(START)))
    b.settled_cash(START)
    assert 'cash_stamps' not in b.diagnostic()


def test_wrong_account_records_no_stamps():
    b = broker(cash_client(account='OTHER', stamp=stamp(START)))
    with pytest.raises(SecurityChallenge): b.settled_cash(START)
    assert b.diagnostic()['cash_stamps'] == {'snapshots': 0, 'stamp_types': [], 'offsets_s': []}


def test_seconds_stamps_follow_the_same_bound():
    seconds = int(READ.timestamp())
    assert broker(cash_client(stamp=seconds + 60)).settled_cash(START)['amount'] == 12.5
    assert broker(cash_client(stamp=float(seconds))).settled_cash(START)['amount'] == 12.5
    with pytest.raises(SecurityChallenge): broker(cash_client(stamp=seconds + 61)).settled_cash(START)


def test_offset_is_whole_seconds():
    b = broker(cash_client(stamp=stamp(READ) + 90500))
    with pytest.raises(SecurityChallenge): b.settled_cash(START)
    offset = b.diagnostic()['cash_stamps']['offsets_s'][0]
    assert offset == 90 and type(offset) is int


def test_unexpected_stamp_type_is_named_without_its_value():
    b = broker(cash_client(stamp='PRIVATE-2026'))
    with pytest.raises(SecurityChallenge): b.settled_cash(START)
    assert b.diagnostic()['cash_stamps'] == {'snapshots': 1, 'stamp_types': ['str'], 'offsets_s': []}
    assert 'PRIVATE' not in json.dumps(b.diagnostic())


def test_invalid_amount_inside_the_new_range_refuses_the_read():
    good = NS(as_of_date_time=stamp(START - timedelta(minutes=1)), cash_detail=NS(settled_amt=5.0, core_balance=1.0))
    bad = NS(as_of_date_time=stamp(READ), cash_detail=NS(settled_amt=None, core_balance=1.0))
    balance = NS(acct_num='FIXTURE', recent_balance_detail=bad, intraday_balance_detail=good, close_balance_detail=None)
    with pytest.raises(SecurityChallenge):
        broker(NS(balances=NS(get_balances=lambda a: NS(accounts=[balance])))).settled_cash(START)


def test_real_clock_is_aware_utc():
    assert REAL_CLOCK().utcoffset() == timedelta(0)
