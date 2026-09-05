# Quickstart — 001 Data Ingestion

## Fetch bars

```python
from data import download_market_data

prices = download_market_data(["AAPL", "MSFT"], period="2y")
```

First call downloads and writes `data/cache/AAPL-MSFT_2y.csv`. Later calls
with the same tickers and period read that file and make no network call.
Ticker order does not matter — `["MSFT", "AAPL"]` hits the same cache entry.

```python
prices = download_market_data(["AAPL"], period="2y", force_refresh=True)
```

Returned frame, always:

```
        Date Ticker    Open    High     Low   Close    Volume
0 2024-09-05   AAPL  ...
```

Sorted by `Ticker` then `Date`. `Date` is a tz-naive midnight timestamp
denoting the session — same dtype whether the data came from the network or
the cache.

## Inspect calendar gaps

```python
from data import find_missing_bars

gaps = find_missing_bars(prices)
if not gaps.empty:
    print(gaps)
```

Each row is an NYSE session inside that ticker's own history with no bar.
Weekends and holidays never appear — a row means no US market holiday
explains the absence.

This is a **report**. The frame is not modified, nothing is filled, and
nothing raises. What to do about a gap is the caller's call, deliberately
(`research.md` R1).

## Ask the calendar directly

```python
from datetime import date
from data import is_market_holiday, trading_days

is_market_holiday(date(2024, 3, 29))          # True  — Good Friday
is_market_holiday(date(2024, 10, 14))         # False — Columbus Day, NYSE open
len(trading_days(date(2024, 1, 1), date(2024, 12, 31)))   # 252
```

## Tests

```bash
python -m unittest discover -s tests
```

No network, no test dependencies. The download path is exercised through the
`downloader` parameter:

```python
def fake_downloader(tickers, **kwargs):
    return some_multiindex_frame

download_market_data(["AAPL"], downloader=fake_downloader)
```
