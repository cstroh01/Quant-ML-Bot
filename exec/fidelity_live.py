"""Fidelity LIVE order adapter (spec 057). Rule 7: read every line before merge.

Unofficial integration. Fidelity publishes no retail trading API; Camden accepted
in writing (docs/SCOPE-V1.md §10, 2026-10-07) that this may breach Fidelity's
terms and risk account restriction. This module adds no detection evasion.

What this module guarantees:

- **LIVE profile only, preview by default.** It refuses any profile that is not
  ``mode == "LIVE"`` with ``broker == "fidelity"``. Without a valid arming record
  (spec 051) every placement refuses; previews and reads still work.
- **One session per run.** ``connect`` logs in once; a second login in the same
  process refuses. A login challenge or security prompt halts the profile.
- **Credentials from the environment only**, by the names the profile lists,
  held privately, never logged, printed, in ``repr`` or in an exception message.
- **Cash account, equities only, no retries.** Every order is sent with account
  type ``C`` (cash). The underlying client is built with ``max_retries=0``, so a
  timeout is reported as unknown and never replayed (duplicate-order risk).
- **Intent before placement.** The preview's confirmation number is durably
  recorded against the bot's deterministic client id (spec 055) before the
  place call, so an unknown outcome is reconcilable by confirmation number.
- **Any error once ``place`` is called is outcome-unknown.** The request may have
  reached Fidelity whatever the exception, so it is ``SubmissionUnknown``: never
  retried, reconciled by confirmation number.
- **Only Fidelity's own codes count (spec 068).** A preview counts only when its reply
  says ``V`` (validated) and a placement only when its reply says ``A`` (accepted) with
  a confirmation number. A refused order leaves a marker beside the intent log, and
  reads as ``REJECTED`` only while Fidelity's status list shows no such order.
- **A placed order's outcome is kept (spec 069).** After an accepted placement it looks the
  order up a few times (read-only) and records the first terminal status Fidelity reports.
  That record answers only when a later status list shows none of the order's numbers; the
  observation never changes the placement's result.
- **A client id is used once.** A repeat ``submit`` for a recorded client id never
  previews or places again: it returns the known order, or raises
  ``SubmissionUnknown`` if Fidelity has no record yet; a different order under the
  same id refuses.
- **Errors are redacted.** Broker exceptions surface only as their type name, with
  no chained cause, so URLs, account numbers or tokens in a library message never
  reach a log.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping, Protocol
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from live_safety_gate import OrderIntent
from mode_config import ArmingRecord, ModeProfile, ProfileError, require_armed
from ops_runtime import atomic_write, open_intents, record_intent, require_storage_identifier

TERMINAL_STATUSES = frozenset({"FILLED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED"})
_OUTCOMES = "order-outcomes"  # spec 068 FR-003: one record per client id, beside intents.jsonl
_OBSERVED = "observed"  # spec 069 FR-002: Fidelity's terminal status, seen right after placement
_OBSERVE_WAITS = (2.0, 3.0, 5.0, 10.0)  # spec 069 D-1: looks at about 2, 5, 10 and 20 s after placement
_sleep = time.sleep  # module-level so tests replace it; nothing else here waits


def _same_quantity(executed: Any, ordered: float) -> bool:
    """Spec 069 FR-002: a reply without an executed quantity passes (the next run's ownership check
    compares the account); otherwise it must be a finite number equal to the order at 0.001."""
    if executed is None:
        return True
    if isinstance(executed, bool):
        return False
    try:
        value = float(executed)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and abs(value - ordered) < 0.0005


class BrokerError(RuntimeError):
    """A broker call failed. The message never contains a credential."""


class SubmissionUnknown(BrokerError):
    """The order may or may not have reached Fidelity. Do not retry; reconcile."""


class PreviewRefused(BrokerError):
    """Spec 068 FR-001: Fidelity did not validate the preview, so placement never ran."""


class PlacementRejected(BrokerError):
    """Spec 068 FR-002: Fidelity answered the placement without accepting it. Never retried.

    ``conf_num`` is the reply's confirmation number, if it had one; it is never in the message."""

    def __init__(self, message: str, conf_num: str | None = None) -> None:
        super().__init__(message)
        self.conf_num = conf_num


class SecurityChallenge(BrokerError):
    """Fidelity asked for extra verification or warned the account."""


class HaltProfile(BrokerError):
    """Stop all activity for this profile until Camden reviews."""


class NotArmed(BrokerError):
    """Placement refused: the LIVE profile is not armed."""


class Broker(Protocol):
    def login(self, username: str, password: str, totp_secret: str) -> None: ...
    def preview(self, symbol: str, side: str, quantity: float) -> str: ...
    def place(self, symbol: str, side: str, quantity: float, conf_num: str) -> str: ...
    def status(self, conf_num: str) -> str | None: ...
    def status_detail(self, conf_num: str) -> tuple[str | None, float | None]: ...
    def positions(self) -> dict[str, float]: ...


def _credential(environ: Mapping[str, str], refs: tuple[str, ...], suffix: str) -> str:
    names = [ref for ref in refs if ref.endswith(suffix)]
    if len(names) != 1 or not environ.get(names[0]):
        raise BrokerError(f"profile must name exactly one set credential ending {suffix}")
    return environ[names[0]]


class FidelityLive:
    def __init__(self, profile: ModeProfile, *, broker: Broker, state_dir,
                 environ: Mapping[str, str] | None = None) -> None:
        if profile.mode != "LIVE" or profile.broker != "fidelity":
            raise ProfileError(f"{profile.name}: FidelityLive needs a LIVE fidelity profile")
        env = os.environ if environ is None else environ
        self.__username = _credential(env, profile.credential_refs, "_USERNAME")
        self.__password = _credential(env, profile.credential_refs, "_PASSWORD")
        self.__totp = _credential(env, profile.credential_refs, "_TOTP")
        self._profile = profile
        self._broker = broker
        self._state_dir = state_dir
        self._connected = False
        self._halted = False
        self.observations: list[dict] = []  # spec 069 FR-004: one entry per observed placement

    def __repr__(self) -> str:
        return f"FidelityLive(profile={self._profile.name!r}, connected={self._connected})"

    def _check_halt(self) -> None:
        if self._halted:
            raise HaltProfile(f"{self._profile.name} halted; Camden must review before any further call")

    def connect(self) -> None:
        """Log in exactly once per process; a challenge halts the profile."""
        self._check_halt()
        if self._connected:
            raise BrokerError("one session per run: already connected")
        try:
            self._broker.login(self.__username, self.__password, self.__totp)
        except SecurityChallenge:
            self._halted = True
            raise HaltProfile(f"{self._profile.name}: Fidelity security challenge; halted") from None
        except Exception as exc:
            raise BrokerError(f"login failed: {type(exc).__name__}") from None
        self._connected = True

    def _call(self, stage: str, fn, *args):
        """Run a non-placing broker call; challenges halt, anything else is redacted to its type."""
        try:
            return fn(*args)
        except SecurityChallenge:
            self._halted = True
            raise HaltProfile(f"{self._profile.name}: security challenge at {stage}; halted") from None
        except PreviewRefused:
            raise  # spec 068: this module's own text, naming only a reduced code
        except BrokerError as exc:
            raise type(exc)(f"{stage} failed: {type(exc).__name__}") from None
        except Exception as exc:  # noqa: BLE001 - library messages may carry URLs or account data
            raise BrokerError(f"{stage} failed: {type(exc).__name__}") from None

    def positions(self) -> dict[str, float]:
        self._check_halt()
        return self._call("positions", self._broker.positions)

    def preview(self, intent: OrderIntent) -> dict:
        """Preview only: connected, sleeve-only; no arming, intent write or placement."""
        from signals import ALLOCATION_SLEEVES
        self._check_halt()
        if not self._connected or intent.instrument not in ALLOCATION_SLEEVES:
            raise BrokerError('connected sleeve preview required')
        side = 'B' if intent.delta_quantity > 0 else 'S'
        qty = abs(float(intent.delta_quantity))
        conf = self._call('preview', self._broker.preview, intent.instrument, side, qty)
        if not isinstance(conf, str) or not conf:
            raise BrokerError('preview confirmation missing')
        return {'symbol': intent.instrument, 'side': side, 'qty': qty, 'conf_num': conf}

    def settled_cash(self, now: datetime) -> dict:
        self._check_halt()
        return self._call('settled_cash', self._broker.settled_cash, now)

    def prices(self) -> dict:
        self._check_halt()
        return self._call('prices', self._broker.prices)

    def submit(self, intent: OrderIntent, *, arming: ArmingRecord | None, now: datetime) -> str:
        """Preview, record, then place one market order. Call only via order_gateway after ALLOW."""
        self._check_halt()
        if not self._connected:
            raise BrokerError("not connected")
        try:
            require_armed(self._profile, arming, now=now)
        except ProfileError as exc:
            raise NotArmed(str(exc)) from None
        side = "B" if intent.delta_quantity > 0 else "S"
        quantity = abs(float(intent.delta_quantity))
        previous = self._recorded(intent.client_order_id)
        if previous is not None:
            return self._resubmission(intent.client_order_id, previous, intent.instrument, side, quantity)
        try:
            conf_num = self._call("preview", self._broker.preview, intent.instrument, side, quantity)
        except PreviewRefused:
            self._mark(intent.client_order_id, "not_sent", ())  # FR-001: placement never ran
            raise
        record_intent(self._state_dir, intent.client_order_id,
                      {"symbol": intent.instrument, "side": side, "qty": quantity, "conf_num": conf_num})
        try:
            placed = self._broker.place(intent.instrument, side, quantity, conf_num)
        except SecurityChallenge:
            self._halted = True
            raise HaltProfile(f"{self._profile.name}: security challenge at placement; halted; "
                              f"{intent.client_order_id} outcome unknown, reconcile") from None
        except PlacementRejected as exc:
            # FR-002/FR-003: a known refusal, re-raised as itself once its marker is durable.
            self._settle(intent.client_order_id, "rejected", (conf_num, exc.conf_num))
            raise
        except Exception as exc:  # noqa: BLE001 - once place is called, the order may exist
            raise SubmissionUnknown(f"{intent.client_order_id}: placement outcome unknown "
                                    f"({type(exc).__name__}); reconcile, never retry") from None
        if not isinstance(placed, str) or not placed:
            raise SubmissionUnknown(f"{intent.client_order_id}: placement returned no confirmation; reconcile")
        if placed != conf_num:  # FR-002.3: status lookups must also try the placement's number
            self._settle(intent.client_order_id, "placed", (conf_num, placed))
        self._observe(intent.client_order_id, (conf_num, placed), quantity)
        return placed

    def _observe(self, client_order_id: str, numbers, quantity: float) -> None:
        """Spec 069 FR-001: look a placed order up at the D-1 waits until Fidelity reports a terminal
        status, record it (FR-002) and note the result (FR-004). Read-only, never retried, and it
        never changes the placement's result; only a security challenge escapes (it halts)."""
        detail = getattr(self._broker, "status_detail", None)
        if not callable(detail):
            return  # a broker without it (a test fake) is not observed
        numbers = [n for n in dict.fromkeys(numbers) if isinstance(n, str) and n]
        result = "none"
        try:
            for wait in _OBSERVE_WAITS:
                _sleep(wait)
                found = self._look(detail, numbers)
                if found is None or found[0] not in TERMINAL_STATUSES:
                    continue  # not listed yet, or still working
                code, executed = found
                if code == "FILLED" and not _same_quantity(executed, quantity):
                    result = "quantity_mismatch"  # recorded nowhere: the order stays unknown
                    break
                self._record_observation(client_order_id, numbers, code)
                result = code
                break
        except HaltProfile:
            raise
        except Exception as exc:  # noqa: BLE001 - the order is placed; a failed look only leaves it unrecorded
            result = f"error {type(exc).__name__}"
        self.observations.append({"client_order_id": client_order_id, "observed": result})

    def _look(self, detail, numbers) -> tuple[str, Any] | None:
        """The first listed status (normalized as fidelity_reconcile does) and its executed quantity."""
        for number in numbers:
            status, executed = self._call("status", detail, number)
            if status is not None:
                return "_".join(str(status).upper().split()), executed
        return None

    def _record_observation(self, client_order_id: str, numbers, status: str) -> None:
        """Spec 069 FR-002: write the observed terminal status atomically. It supersedes only a 068
        ``placed`` record for the same numbers; any other different record refuses."""
        record = {"client_order_id": client_order_id, "outcome": _OBSERVED,
                  "conf_nums": sorted(set(numbers)), "status": status}
        current = self._outcome(client_order_id)
        if current is not None and current != record and not (
                current["outcome"] == "placed" and current["conf_nums"] == record["conf_nums"]):
            raise BrokerError(f"{client_order_id}: a different order outcome is already recorded")
        atomic_write(self._outcome_path(client_order_id), json.dumps(record, sort_keys=True))

    def _settle(self, client_order_id: str, outcome: str, numbers) -> None:
        """Record a placement's outcome; if that fails the order stays unknown (never retried)."""
        try:
            self._mark(client_order_id, outcome, numbers)
        except Exception as exc:  # noqa: BLE001 - without its record the order must read as unknown
            raise SubmissionUnknown(f"{client_order_id}: placement outcome not recorded "
                                    f"({type(exc).__name__}); reconcile, never retry") from None

    def _outcome_path(self, client_order_id: str) -> Path:
        try:
            name = require_storage_identifier(client_order_id, "client order id")
        except ValueError:
            raise BrokerError("client order id is not a storage identifier") from None
        return Path(self._state_dir) / _OUTCOMES / f"{name}.json"

    def _mark(self, client_order_id: str, outcome: str, numbers) -> None:
        """FR-003: write one outcome record atomically; a different existing record refuses."""
        record = {"client_order_id": client_order_id, "outcome": outcome,
                  "conf_nums": sorted({n for n in numbers if isinstance(n, str) and n})}
        if self._outcome(client_order_id) not in (None, record):
            raise BrokerError(f"{client_order_id}: a different order outcome is already recorded")
        atomic_write(self._outcome_path(client_order_id), json.dumps(record, sort_keys=True))

    def _outcome(self, client_order_id: str) -> dict | None:
        """The FR-003 record for a client id, or None. A malformed record refuses (fail closed)."""
        path = self._outcome_path(client_order_id)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            numbers = record["conf_nums"]
            observed = record["outcome"] == _OBSERVED  # spec 069: carries one terminal status
            valid = (set(record) == {"client_order_id", "outcome", "conf_nums"} | ({"status"} if observed else set())
                     and record["client_order_id"] == client_order_id
                     and record["outcome"] in ("not_sent", "rejected", "placed", _OBSERVED)
                     and (not observed or record["status"] in TERMINAL_STATUSES)
                     and isinstance(numbers, list) and all(isinstance(n, str) and n for n in numbers)
                     and (record["outcome"] == "not_sent") == (numbers == []))
        except Exception:  # noqa: BLE001 - unreadable is refused below
            valid = False
        if not valid:
            raise BrokerError(f"{client_order_id}: order outcome record unreadable")
        return record

    def _recorded(self, client_order_id: str) -> dict | None:
        for row in open_intents(self._state_dir):
            if row["client_order_id"] == client_order_id:
                return row["intent"]
        return None

    def _resubmission(self, client_order_id: str, previous: dict, symbol: str, side: str, quantity: float) -> str:
        """A client id already previewed: return the known order; never preview or place twice."""
        if (previous["symbol"], previous["side"], previous["qty"]) != (symbol, side, quantity):
            raise BrokerError(f"{client_order_id} was recorded for a different order; refusing")
        status = self._call("status", self._broker.status, previous["conf_num"])
        if status is None:
            raise SubmissionUnknown(f"{client_order_id}: recorded but Fidelity has no order yet; "
                                    "reconcile by confirmation number, never resubmit")
        return previous["conf_num"]

    def order_status(self, client_order_id: str) -> str | None:
        """Fidelity's status for the bot's client id; None when its outcome is unknown.

        Spec 068 FR-003: ``REJECTED`` comes from this module only when its preview was refused
        (no intent recorded, placement never ran), or when Fidelity refused the placement and
        its status list shows no order under any recorded confirmation number. An order that
        Fidelity does list keeps Fidelity's status, whatever the marker says. Spec 069 FR-003: an
        observed terminal status answers likewise, only when the list shows none of the numbers."""
        self._check_halt()
        previous = self._recorded(client_order_id)
        outcome = self._outcome(client_order_id)
        if previous is None:
            return "REJECTED" if outcome is not None and outcome["outcome"] == "not_sent" else None
        numbers = [previous["conf_num"]]
        numbers += [n for n in (outcome or {}).get("conf_nums", []) if n not in numbers]
        for number in numbers:
            status = self._call("status", self._broker.status, number)
            if status is not None:
                return status
        if outcome is not None and outcome["outcome"] == _OBSERVED:
            return outcome["status"]  # spec 069 FR-003: Fidelity no longer lists it
        return "REJECTED" if outcome is not None and outcome["outcome"] == "rejected" else None


_AUTH_PATHS = ('/user/session/login', '/user/factor/password/authentication', '/user/factor/totp/authentication')
_TRACE_LIMIT = 20
_ENTITLEMENT_LIMIT = 60  # D-9: rows kept from one security-context response
_ERROR_LIMIT = 5
_KEY_LIMIT = 40
_LABEL = re.compile(r'[A-Za-z][A-Za-z0-9_ -]{0,31}')
_CASH_STAMP_SKEW = timedelta(seconds=60)  # D-10: allowed Fidelity clock lead over the runner
_LOGIN_PAGE_MOVE = ('https://digital.fidelity.com/prgw/digital/login/atp',  # D-6a: Fidelity's permanent move,
                    'https://digital.fidelity.com/prgw/digital/signin/atp')  # compared as exact strings


def _read_clock() -> datetime:
    return datetime.now(timezone.utc)


def _masked_path(url) -> str:
    """Path only: no host, query or fragment; a segment holding a digit or over 24 characters is '*'."""
    segments = urlparse(str(url)).path.split('/')
    return '/'.join('*' if any(c.isdigit() for c in s) or len(s) > 24 else s for s in segments)[:80]


def _label(value) -> str:
    """D-9: a short plain name as is; anything that could hold an identifier or free text is '*'."""
    return value if isinstance(value, str) and _LABEL.fullmatch(value) and not re.search(r'[0-9]{3}', value) else '*'


def _key_names(value: dict) -> list:
    return sorted(_label(k) for k in value)[:_KEY_LIMIT]


def _error_fact(error) -> dict:
    """D-9: key names plus only short code/type/status values; never message text."""
    if not isinstance(error, dict):
        return {'kind': type(error).__name__}
    fact = {'keys': _key_names(error)}
    for name in ('code', 'type', 'status'):
        if name in error:
            value = error[name]
            fact[name] = value if type(value) is int and abs(value) < 100000 else _label(value)
    return fact


def _entitlement_facts(payload) -> dict:
    """D-9: shape and entitlement names of a security-context response. Never an internal
    system id, a persona value or error text; a value is only 'true', 'false' or 'other'."""
    if not isinstance(payload, dict):
        return {'kind': type(payload).__name__}
    facts = {'keys': _key_names(payload)}
    rows, errors = payload.get('entitlements'), payload.get('errors')
    if isinstance(rows, list):
        facts['entitlement_count'] = len(rows)
        facts['entitlements'] = [
            {'display': _label(row.get('display')), 'classification': _label(row.get('classification')),
             'value': row['value'].lower() if isinstance(row.get('value'), str) and row['value'].lower() in ('true', 'false') else 'other'}
            if isinstance(row, dict) else {'kind': type(row).__name__} for row in rows[:_ENTITLEMENT_LIMIT]]
    if isinstance(errors, list):
        facts['error_count'] = len(errors)
        facts['errors'] = [_error_fact(error) for error in errors[:_ERROR_LIMIT]]
    return facts


_ORDER_PATHS = (('/equity/preview/v1', 'preview'), ('/equity/place/v1', 'place'))  # the pinned wheel's endpoints
_ORDER_KEY_LIMIT = 20
_ORDER_ENTRY_LIMIT = 5


def _short(value):
    """FR-005: a small integer code as is; any other value only as a D-9 label."""
    return value if type(value) is int and abs(value) < 100000 else _label(value)


def _order_reply_facts(endpoint: str, payload) -> dict:
    """Spec 068 FR-005 (D-9 pattern): reduced respTypeCode, key names, and each message or error
    entry's short code/type/severity values. Never message text, account values, amounts,
    quantities or confirmation numbers (D-2)."""
    facts = {'endpoint': endpoint}
    if not isinstance(payload, dict):
        facts['kind'] = type(payload).__name__
        return facts
    reply = payload.get(endpoint) if isinstance(payload.get(endpoint), dict) else {}
    detail = reply.get('orderConfirmDetail') if isinstance(reply.get('orderConfirmDetail'), dict) else {}
    facts['resp_type_code'] = _label(detail.get('respTypeCode'))
    facts['keys'] = {level: sorted(_label(k) for k in value)[:_ORDER_KEY_LIMIT]
                     for level, value in (('top', payload), ('reply', reply), ('orderConfirmDetail', detail))}
    entries = [entry for level in (payload, reply, detail) for key, value in level.items()
               if isinstance(key, str) and ('message' in key.lower() or 'error' in key.lower())
               and isinstance(value, list) for entry in value]
    facts['entry_count'] = len(entries)
    facts['entries'] = [
        {'keys': sorted(_label(k) for k in entry)[:_ORDER_KEY_LIMIT],
         **{_label(k): _short(v) for k, v in entry.items()
            if isinstance(k, str) and k.lower().endswith(('code', 'type', 'severity'))}}
        if isinstance(entry, dict) else {'kind': type(entry).__name__} for entry in entries[:_ORDER_ENTRY_LIMIT]]
    return facts


def account_hmac(account, key):
    import hashlib, hmac, re
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key) or not isinstance(account,str) or not account:
        raise HaltProfile('account fingerprint credentials refused')
    return hmac.new(bytes.fromhex(key),account.encode(),hashlib.sha256).hexdigest()

class LibraryBroker:
    """Thin wrapper over the pinned ``fidelity-trader-api==0.2.2`` (audit: spec 057 research.md)."""

    def __init__(self, account_number_env: str, environ: Mapping[str, str] | None = None) -> None:
        if account_number_env != 'FIDELITY_LIVE_ACCOUNT': raise SecurityChallenge('fixed account reference required')
        from fidelity_sdk import client
        env = os.environ if environ is None else environ
        self.__account = env[account_number_env]
        self.__fp_key = env.get('FIDELITY_LIVE_FP_KEY')
        self._client: Any = client()
        self.totp_step = False
        self._totp_present = False
        self.failure = None
        self.trace = []
        self.entitlement = None
        self._auth_started = False
        self._client._http.event_hooks['request'].append(self._request_hook)
        self._client._http.event_hooks['response'].append(self._response_hook)

    def __repr__(self) -> str:
        return "LibraryBroker(fidelity-trader-api==0.2.2)"

    def login(self, username: str, password: str, totp_secret: str) -> None:
        self.totp_step = False
        self._totp_present = bool(totp_secret)
        try:
            self._client.login(username, password, totp_secret=totp_secret)
            context = self._client.security_context.get_context()
            # D-11: ATP is not required (false for this Trader+ login); at least one named entitlement
            # and errors == [] suffice. Later account-matched reads still fail closed.
            if not isinstance(getattr(context, 'entitlements', None), list) or not any(getattr(row, 'display', '') for row in context.entitlements) or getattr(context, 'errors', None) != []:
                raise SecurityChallenge('Fidelity entitlement refused')
        except Exception as exc:
            # FR-013: this module's own fixed text, or only the library exception's type name.
            self._note_refusal(str(exc) if isinstance(exc, SecurityChallenge) else 'library ' + type(exc).__name__)
            raise SecurityChallenge('Fidelity authentication or entitlement refused') from None

    def _note_refusal(self, reason: str) -> None:
        """Keep the first refusal; later ones are consequences of it."""
        if getattr(self, 'failure', None) is None:
            self.failure = reason

    def _note_response(self, response) -> None:
        """FR-013: one redacted response fact, keeping the latest 20; never raises, so it cannot change a guard."""
        try:
            trace = getattr(self, 'trace', None)
            if trace is None:
                return
            url = urlparse(str(response.request.url))
            entry = {'host': url.hostname if self._allowed(url.geturl()) else 'other',
                     'method': str(response.request.method), 'path': _masked_path(url.geturl()),
                     'status': int(response.status_code)}
            location = response.headers.get('location')
            if location:
                entry['redirect'] = _masked_path(urljoin(url.geturl(), location))
            if url.path.endswith(_AUTH_PATHS):
                try:
                    code = response.json()['responseBaseInfo']['status']['code']
                except Exception:
                    code = None
                entry['auth_code'] = code if type(code) is int else None
            trace.append(entry)
            del trace[:-_TRACE_LIMIT]
            for suffix, endpoint in _ORDER_PATHS:  # spec 068 FR-005: reduced at once, raw never kept
                if url.path.endswith(suffix):
                    self._replies()[endpoint] = _order_reply_facts(endpoint, response.json())
            if url.path.endswith('/context/security'):
                self.entitlement = _entitlement_facts(response.json())
        except Exception:
            pass

    def _replies(self) -> dict:
        """FR-005: the latest reduced reply facts per order endpoint, in memory only."""
        return self.__dict__.setdefault('_order_replies', {})

    def _refused(self, endpoint: str, response) -> str:
        """FR-005: keep this request's reduced reply facts for diagnostic(); return the reduced code."""
        code = _label(getattr(getattr(response, 'order_confirm_detail', None), 'resp_type_code', None))
        self.order_reply = self._replies().get(endpoint) or {'endpoint': endpoint, 'resp_type_code': code}
        return code

    def diagnostic(self) -> dict:
        """Redacted login facts for a failed session record (FR-013)."""
        facts = {'reason': getattr(self, 'failure', None), 'totp_step': bool(getattr(self, 'totp_step', False)),
                 'responses': list(getattr(self, 'trace', []))}
        if getattr(self, 'entitlement', None) is not None:
            facts['entitlement'] = self.entitlement  # D-9
        if getattr(self, 'cash_stamps', None) is not None:
            facts['cash_stamps'] = self.cash_stamps  # D-10
        if getattr(self, 'order_reply', None) is not None:
            facts['order_reply'] = self.order_reply  # spec 068 FR-005
        return facts

    @staticmethod
    def _allowed(url) -> bool:
        parsed = urlparse(str(url))
        return parsed.scheme == 'https' and bool(parsed.hostname) and parsed.hostname.endswith('.fidelity.com')

    def _request_hook(self, request) -> None:
        try:
            self._check_request(request)
        except SecurityChallenge as exc:
            self._note_refusal(str(exc))
            raise

    def _check_request(self, request) -> None:
        if not self._allowed(request.url):
            raise SecurityChallenge('Fidelity request host refused')
        if request.url.host == 'ecaap.fidelity.com':
            self._auth_started = True
        if any(p in request.url.path for p in ('/position/', '/balance/', '/order-status/', '/equity/', '/accounts')):
            try: accounts = self._account_ids(json.loads(request.content))
            except Exception: raise SecurityChallenge('Fidelity account filter missing') from None
            if not accounts or set(accounts) != {self.__account}:
                raise SecurityChallenge('Fidelity account filter refused')

    @staticmethod
    def _account_ids(value):
        if isinstance(value, list): return [a for v in value for a in LibraryBroker._account_ids(v)]
        if not isinstance(value, dict): return []
        return [a for k,v in value.items() for a in ([v] if k in ('acctNum','accountNumber','account_number') else LibraryBroker._account_ids(v))]

    def _response_hook(self, response) -> None:
        try:
            self._check_response(response)
        except SecurityChallenge as exc:
            self._note_refusal(str(exc))
            raise
        finally:
            self._note_response(response)

    def _check_response(self, response) -> None:
        self._request_hook(response.request)
        try:
            response.read(); payload = response.json()
        except Exception: payload = None
        if any(a != self.__account for a in self._account_ids(payload)):
            raise SecurityChallenge('Fidelity response account refused')
        location = response.headers.get('location')
        if location:
            target = urljoin(str(response.url), location)
            from_moved_page = urlparse(str(response.request.url)).path.lower().startswith('/prgw/digital/signin/atp')
            if not self._page_moved(response, target) and (from_moved_page or not self._allowed(target)
                    or any(x in urlparse(target).path.lower() for x in ('/signin', '/login'))):
                raise SecurityChallenge('Fidelity redirect refused')
        if response.status_code in (401, 403):
            raise SecurityChallenge('Fidelity session refused')
        path = response.request.url.path
        if response.request.method == 'POST' and path.endswith(_AUTH_PATHS):
            try:
                response.read()
                code = response.json()['responseBaseInfo']['status']['code']
            except Exception:
                raise SecurityChallenge('Fidelity auth payload refused') from None
            if type(code) is not int:
                raise SecurityChallenge('Fidelity auth status refused')
            if code == 1201 and path.endswith('/user/session/login') and self._totp_present:
                self.totp_step = True
            elif code != 1200 or isinstance(code, bool):
                raise SecurityChallenge('Fidelity authentication refused')

    def _page_moved(self, response, target) -> bool:
        """D-6a: only the pre-credential page load may follow Fidelity's permanent login-page move."""
        base, sep, query = str(response.request.url).partition('?')
        return (response.request.method == 'GET' and response.status_code == 308
                and not getattr(self, '_auth_started', True)
                and base == _LOGIN_PAGE_MOVE[0] and target == _LOGIN_PAGE_MOVE[1] + sep + query)

    def settled_cash(self, as_of: datetime) -> dict:
        """Configured-account settled cash only; fresh NY session, never buying power.

        ``as_of`` names the session. A snapshot may be stamped up to the clock read after the
        response plus ``_CASH_STAMP_SKEW`` (D-10); a later stamp or another NY day never counts.
        """
        offsets, types = [], []
        try:
            from data import trading_days
            if as_of.utcoffset() is None:
                raise ValueError
            session = as_of.astimezone(ZoneInfo('America/New_York')).date()
            if trading_days(session, session) != [session]:
                raise ValueError
            accounts = self._client.balances.get_balances([self.__account]).accounts
            if len(accounts) != 1 or accounts[0].acct_num != self.__account:
                raise ValueError
            latest = max(as_of, _read_clock())
            snapshots = [getattr(accounts[0], name, None) for name in
                         ('recent_balance_detail', 'intraday_balance_detail', 'close_balance_detail')]
            candidates = []
            for snapshot in snapshots:
                if snapshot is None:
                    continue
                stamp = snapshot.as_of_date_time
                types.append(type(stamp).__name__)
                if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
                    raise ValueError
                when = datetime.fromtimestamp(stamp / 1000 if abs(stamp) > 100000000000 else stamp, timezone.utc)
                offsets.append(int((when - latest).total_seconds()))
                if when > latest + _CASH_STAMP_SKEW or when.astimezone(ZoneInfo('America/New_York')).date() != as_of.astimezone(ZoneInfo('America/New_York')).date():
                    continue
                amount = snapshot.cash_detail.settled_amt
                if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                    raise ValueError
                core = getattr(snapshot.cash_detail, 'core_balance', None)
                if core is not None and (isinstance(core,bool) or not isinstance(core,(int,float)) or not math.isfinite(core) or core<0): raise ValueError
                candidates.append((when, float(amount), core))
            when, amount, core = max(candidates, key=lambda row: row[0])
            return {'amount': amount, 'settled_amt': amount, 'coreBalance': core, 'as_of': when.isoformat()}
        except Exception:
            self.cash_stamps = {'snapshots': len(types), 'stamp_types': types, 'offsets_s': offsets}  # D-10: no values
            raise SecurityChallenge('Fidelity settled cash unavailable or stale') from None

    def _order(self, symbol: str, side: str, quantity: float):
        from fidelity_trader.models.equity_order import EquityOrderRequest

        return EquityOrderRequest(acctNum=self.__account, symbol=symbol, orderActionCode=side,
                                  acctTypeCode="C", qty=quantity, priceTypeCode="M", tifCode="D")

    def preview(self, symbol: str, side: str, quantity: float) -> str:
        self._replies().pop('preview', None)  # FR-005: never report an earlier request's reply
        response = self._client.equity_orders.preview_order(self._order(symbol, side, quantity))
        if response.acct_num != self.__account: raise SecurityChallenge('Fidelity preview account refused')
        conf = response.conf_num
        if not response.is_validated or not conf:  # spec 068 FR-001: only "V" with a number counts
            raise PreviewRefused(f"preview not validated: respTypeCode {self._refused('preview', response)}")
        return conf

    def place(self, symbol: str, side: str, quantity: float, conf_num: str) -> str:
        order = self._order(symbol, side, quantity)  # built before the send: errors here sent nothing
        self._replies().pop('place', None)  # FR-005: never report an earlier request's reply
        try:
            response = self._client.equity_orders.place_order(order, conf_num)
        except SecurityChallenge:
            raise
        except Exception as exc:  # noqa: BLE001 - the request may have reached Fidelity
            raise SubmissionUnknown(f"place outcome unknown: {type(exc).__name__}") from None
        if response.acct_num != self.__account: raise SecurityChallenge('Fidelity placement account refused')
        if not response.is_accepted:  # spec 068 FR-002: only "A" counts as placed
            raise PlacementRejected(f"placement not accepted: respTypeCode {self._refused('place', response)}",
                                    response.conf_num)
        if not response.conf_num:  # accepted without a number: the order may exist
            raise SubmissionUnknown("placement accepted without a confirmation number")
        return response.conf_num

    def status(self, conf_num: str) -> str | None:
        return self.status_detail(conf_num)[0]

    def status_detail(self, conf_num: str) -> tuple[str | None, float | None]:
        """Fidelity's status for one confirmation number and, for spec 069, its executed quantity
        (``amountDetail.qtyExec``); ``(None, None)`` when the list shows no such order."""
        summary = self._client.order_status.get_order_status([self.__account])
        if any(getattr(row, 'acct_num', None) != self.__account for row in
               (getattr(summary,'account_summaries',[]) or []) + (getattr(summary,'orders',[]) or [])):
            raise SecurityChallenge('Fidelity status account refused')
        for order in getattr(summary, "orders", []) or []:
            if getattr(getattr(order, 'id_detail', None), 'conf_num', None) == conf_num:
                detail = getattr(order, 'status_detail', None)
                executed = getattr(getattr(detail, 'amount_detail', None), 'qty_exec', None)
                return getattr(detail, 'status_code', None) or getattr(detail, 'status_desc', None), executed
        return None, None

    def positions(self) -> dict[str, float]:
        result = self._client.positions.get_positions([self.__account])
        if len(result.accounts) != 1 or result.accounts[0].acct_num != self.__account:
            raise SecurityChallenge('Fidelity positions account refused')
        held: dict[str, float] = {}
        self._prices = {}
        for account in result.accounts:
            for position in account.positions:
                if not position.symbol or position.quantity is None:
                    raise SecurityChallenge('Fidelity position quantity unknown')
                if position.symbol and position.quantity is not None:
                    held[position.symbol] = held.get(position.symbol, 0.0) + float(position.quantity)
                    self._prices[position.symbol] = getattr(position.price_detail, 'last_price', None)
        return held

    def prices(self) -> dict:
        if not hasattr(self, '_prices'): self.positions()
        return dict(self._prices)

    @property
    def account_fingerprint(self) -> str:
        return account_hmac(self.__account,self.__fp_key)
