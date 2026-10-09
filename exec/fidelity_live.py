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
"""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any, Mapping, Protocol

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

    def positions(self) -> dict[str, float]:
        self._check_halt()
        return self._broker.positions()

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
        try:
            conf_num = self._broker.preview(intent.instrument, side, quantity)
        except SecurityChallenge:
            self._halted = True
            raise HaltProfile(f"{self._profile.name}: security challenge at preview; halted") from None
        record_intent(self._state_dir, intent.client_order_id,
                      {"symbol": intent.instrument, "side": side, "qty": quantity, "conf_num": conf_num})
        try:
            return self._broker.place(intent.instrument, side, quantity, conf_num)
        except SecurityChallenge:
            self._halted = True
            raise HaltProfile(f"{self._profile.name}: security challenge at placement; halted") from None
        except TimeoutError:
            raise SubmissionUnknown(f"{intent.client_order_id}: placement outcome unknown") from None

    def order_status(self, client_order_id: str) -> str | None:
        """Fidelity's status for the bot's client id, or None if never previewed/recorded."""
        self._check_halt()
        for row in open_intents(self._state_dir):
            if row["client_order_id"] == client_order_id:
                return self._broker.status(row["intent"]["conf_num"])
        return None
