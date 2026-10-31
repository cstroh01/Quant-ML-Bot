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
import re
from typing import Any, Mapping, Protocol
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from live_safety_gate import OrderIntent
from mode_config import ArmingRecord, ModeProfile, ProfileError, require_armed
from ops_runtime import open_intents, record_intent

TERMINAL_STATUSES = frozenset({"FILLED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED"})


class BrokerError(RuntimeError):
    """A broker call failed. The message never contains a credential."""


class SubmissionUnknown(BrokerError):
    """The order may or may not have reached Fidelity. Do not retry; reconcile."""


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
        conf_num = self._call("preview", self._broker.preview, intent.instrument, side, quantity)
        record_intent(self._state_dir, intent.client_order_id,
                      {"symbol": intent.instrument, "side": side, "qty": quantity, "conf_num": conf_num})
        try:
            return self._broker.place(intent.instrument, side, quantity, conf_num)
        except SecurityChallenge:
            self._halted = True
            raise HaltProfile(f"{self._profile.name}: security challenge at placement; halted; "
                              f"{intent.client_order_id} outcome unknown, reconcile") from None
        except Exception as exc:  # noqa: BLE001 - once place is called, the order may exist
            raise SubmissionUnknown(f"{intent.client_order_id}: placement outcome unknown "
                                    f"({type(exc).__name__}); reconcile, never retry") from None

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
        """Fidelity's status for the bot's client id, or None if never previewed/recorded."""
        self._check_halt()
        previous = self._recorded(client_order_id)
        if previous is None:
            return None
        return self._call("status", self._broker.status, previous["conf_num"])


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
            if getattr(context, 'has_atp_access', None) is not True or getattr(context, 'errors', None) != []:
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
            if url.path.endswith('/context/security'):
                self.entitlement = _entitlement_facts(response.json())
        except Exception:
            pass

    def diagnostic(self) -> dict:
        """Redacted login facts for a failed session record (FR-013)."""
        facts = {'reason': getattr(self, 'failure', None), 'totp_step': bool(getattr(self, 'totp_step', False)),
                 'responses': list(getattr(self, 'trace', []))}
        if getattr(self, 'entitlement', None) is not None:
            facts['entitlement'] = self.entitlement  # D-9
        if getattr(self, 'cash_stamps', None) is not None:
            facts['cash_stamps'] = self.cash_stamps  # D-10
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
        response = self._client.equity_orders.preview_order(self._order(symbol, side, quantity))
        if response.acct_num != self.__account: raise SecurityChallenge('Fidelity preview account refused')
        conf = response.conf_num
        if not conf:
            raise BrokerError("preview returned no confirmation number")
        return conf

    def place(self, symbol: str, side: str, quantity: float, conf_num: str) -> str:
        order = self._order(symbol, side, quantity)  # built before the send: errors here sent nothing
        try:
            response = self._client.equity_orders.place_order(order, conf_num)
        except SecurityChallenge:
            raise
        except Exception as exc:  # noqa: BLE001 - the request may have reached Fidelity
            raise SubmissionUnknown(f"place outcome unknown: {type(exc).__name__}") from None
        if response.acct_num != self.__account: raise SecurityChallenge('Fidelity placement account refused')
        return response.conf_num or conf_num

    def status(self, conf_num: str) -> str | None:
        summary = self._client.order_status.get_order_status([self.__account])
        if any(getattr(row, 'acct_num', None) != self.__account for row in
               (getattr(summary,'account_summaries',[]) or []) + (getattr(summary,'orders',[]) or [])):
            raise SecurityChallenge('Fidelity status account refused')
        for order in getattr(summary, "orders", []) or []:
            if getattr(getattr(order, 'id_detail', None), 'conf_num', None) == conf_num:
                detail = getattr(order, 'status_detail', None)
                return getattr(detail, 'status_code', None) or getattr(detail, 'status_desc', None)
        return None

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
