"""064 T002: pure attributable USD transfer journal; no budget or order authority.

Caller supplies an approved source policy and immutable evidence digests. Neither
valid JSON nor this journal verifies broker evidence. A quarantine blocks the
whole batch and remains latched across restart; resolution needs external review.
Returned acknowledgement must be persisted atomically with the consuming snapshot
by a later integration. No I/O, implicit clock, equity inference or auto-unblock.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
import re

_DIGEST = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_FIELDS = frozenset({"transfer_id", "account_fingerprint", "source_id", "evidence_ref",
                     "direction", "amount", "currency", "observed_at", "effective_at", "status"})
_IMMUTABLE = _FIELDS - {"observed_at", "status"}
_REASONS = frozenset({"invalid_event", "account_mismatch", "source_not_approved",
                      "future_event", "identity_conflict"})


@dataclass(frozen=True)
class JournalResult:
    """New JSON-compatible journal, attributable signed flow, redacted reasons."""
    journal: dict
    net_flow: Decimal
    quarantined: tuple[dict, ...]


def _instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("aware instant required")
    return value.astimezone(timezone.utc)


def _policy(account, sources):
    if not isinstance(account, str) or not _DIGEST.fullmatch(account):
        raise ValueError("account fingerprint required")
    if not isinstance(sources, (set, frozenset, list, tuple)) or not sources:
        raise ValueError("approved sources required")
    if any(not isinstance(s, str) or not _TOKEN.fullmatch(s) for s in sources):
        raise ValueError("approved sources required")
    return sorted(set(sources))


def empty_journal(account_fingerprint: str, approved_sources) -> dict:
    """Construct empty in-memory data, never an account/state-ready assertion."""
    return {"schema": 1, "account_fingerprint": account_fingerprint,
            "approved_sources": _policy(account_fingerprint, approved_sources),
            "as_of": None, "entries": {}, "blocked": False, "quarantine_reasons": []}


def _event(raw, account, sources, as_of):
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ValueError("invalid_event")
    for name in ("transfer_id", "source_id"):
        if not isinstance(raw[name], str) or not _TOKEN.fullmatch(raw[name]):
            raise ValueError("invalid_event")
    if raw["account_fingerprint"] != account:
        raise ValueError("account_mismatch")
    if raw["source_id"] not in sources:
        raise ValueError("source_not_approved")
    if not isinstance(raw["evidence_ref"], str) or not _DIGEST.fullmatch(raw["evidence_ref"]):
        raise ValueError("invalid_event")
    value = raw["amount"]
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("invalid_event")
    try:
        if len(str(value)) > 80:
            raise ValueError("invalid_event")
        amount = Decimal(value)
        # Representation bounds ensure exact bounded arithmetic, not a risk limit.
        if not amount.is_finite() or amount == 0 or amount.adjusted() > 30 or amount.as_tuple().exponent < -18:
            raise ValueError("invalid_event")
        if raw["direction"] not in ("deposit", "withdrawal") or (amount > 0) != (raw["direction"] == "deposit"):
            raise ValueError("invalid_event")
        observed, effective = _instant(raw["observed_at"]), _instant(raw["effective_at"])
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        raise ValueError("invalid_event") from None
    if raw["status"] not in ("pending", "settled") or raw["currency"] != "USD":
        raise ValueError("invalid_event")
    if observed > as_of or (raw["status"] == "settled" and effective > as_of):
        raise ValueError("future_event")
    canonical = format(amount, "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    return raw | {"amount": canonical, "observed_at": observed.isoformat(),
                  "effective_at": effective.isoformat()}


def _same(left, right):
    return all(left[field] == right[field] for field in _IMMUTABLE)


def _journal(raw, account, sources, as_of):
    expected = set(empty_journal(account, sources))
    try:
        if not isinstance(raw, dict) or set(raw) != expected or type(raw["schema"]) is not int or raw["schema"] != 1:
            raise ValueError
        if raw["account_fingerprint"] != account or raw["approved_sources"] != sources:
            raise ValueError
        if type(raw["blocked"]) is not bool or not isinstance(raw["quarantine_reasons"], list):
            raise ValueError
        reasons = raw["quarantine_reasons"]
        if any(not isinstance(r, str) or r not in _REASONS for r in reasons) or reasons != sorted(set(reasons)):
            raise ValueError
        if raw["blocked"] != bool(reasons) or not isinstance(raw["entries"], dict):
            raise ValueError
        previous = _instant(raw["as_of"]) if raw["as_of"] is not None else None
        if (previous is not None and previous > as_of) or (previous is None and (raw["entries"] or reasons)):
            raise ValueError
        for key, record in raw["entries"].items():
            if not isinstance(record, dict) or set(record) != {"event", "applied"} or type(record["applied"]) is not bool:
                raise ValueError
            event = _event(record["event"], account, sources, previous)
            if event != record["event"] or key != event["transfer_id"]:
                raise ValueError
            if record["applied"] != (event["status"] == "settled"):
                raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("journal validation refused") from None
    return deepcopy(raw)


def reconcile(journal: dict, events: list[dict], *, account_fingerprint: str,
              approved_sources, as_of: datetime) -> JournalResult:
    """Propose a whole-batch transition; invalid snapshots refuse, events quarantine.

    Amount is explicitly signed (deposit positive, withdrawal negative). Identity
    is transfer_id within the expected account; swapping even an approved source
    conflicts. Evidence/direction/amount/effective time are immutable, while
    observation time may advance and pending may settle. Settled never regresses.
    A future-effective pending transfer is persisted but cannot contribute flow;
    future observations or future-effective settled transfers quarantine instead.
    All conflicts are checked before any flow applies. On quarantine the prior
    entries remain unchanged and net_flow is zero; the latch is not self-clearing.
    """
    sources = _policy(account_fingerprint, approved_sources)
    try:
        instant = _instant(as_of)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("as_of must be aware") from None
    result = _journal(journal, account_fingerprint, sources, instant)
    if not isinstance(events, (list, tuple)) or len(events) > 10000:
        raise ValueError("bounded event batch required")
    pending, quarantined = {}, []
    for index, raw in enumerate(events):
        try:
            candidate = _event(raw, account_fingerprint, sources, instant)
        except ValueError as error:
            quarantined.append({"index": index, "reason": str(error)})
            continue
        key = candidate["transfer_id"]
        prior = pending.get(key) or result["entries"].get(key, {}).get("event")
        if prior is not None and not _same(prior, candidate):
            quarantined.append({"index": index, "reason": "identity_conflict"})
            continue
        if prior is not None:
            candidate["status"] = "settled" if "settled" in (prior["status"], candidate["status"]) else "pending"
            candidate["observed_at"] = max(prior["observed_at"], candidate["observed_at"])
        pending[key] = candidate
    if result["blocked"] or quarantined:
        result["blocked"] = True
        result["quarantine_reasons"] = sorted(set(result["quarantine_reasons"]) | {q["reason"] for q in quarantined})
        result["as_of"] = instant.isoformat()
        return JournalResult(result, Decimal(0), tuple(quarantined) or ({"index": None, "reason": "journal_quarantined"},))
    with localcontext(Context(prec=100)):
        flow = Decimal(0)
        for key, candidate in sorted(pending.items()):
            applied = result["entries"].get(key, {}).get("applied", False)
            if candidate["status"] == "settled" and not applied:
                flow += Decimal(candidate["amount"])
                applied = True
            result["entries"][key] = {"event": candidate, "applied": applied}
    result["entries"] = dict(sorted(result["entries"].items()))
    result["as_of"] = instant.isoformat()
    return JournalResult(result, flow, ())
