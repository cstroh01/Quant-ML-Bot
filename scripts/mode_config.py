"""Spec 051: immutable PAPER/LIVE mode profiles and LIVE arming checks.

Guarantees: a profile never holds a credential value or a raw account id; two
loaded profiles never share a namespace or identity; with no explicit choice the
small PAPER profile is selected; a LIVE profile is usable only with a valid,
unexpired arming record for its own account. Pure: no network, no broker code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

PAPER_BROKERS = frozenset({"alpaca_paper"})
LIVE_BROKERS = frozenset({"fidelity"})
INSTRUMENTS = frozenset({"us_equity", "etf"})
DEFAULT_PROFILE = "paper_small"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,63}")
_UNIQUE = ("state_dir", "log_namespace", "account_fingerprint", "credential_refs")


class ProfileError(ValueError):
    """A profile or arming record that must not be used."""


@dataclass(frozen=True)
class ModeProfile:
    name: str
    mode: str
    broker: str
    account_fingerprint: str
    credential_refs: tuple[str, ...]
    state_dir: str
    log_namespace: str
    bot_budget_usd: float
    daily_deploy_fraction: float
    instruments: tuple[str, ...]
    fractional: bool
    safety_config_version: str

    def __post_init__(self) -> None:
        if self.mode not in ("PAPER", "LIVE"):
            raise ProfileError(f"{self.name}: mode must be PAPER or LIVE")
        allowed = PAPER_BROKERS if self.mode == "PAPER" else LIVE_BROKERS
        if self.broker not in allowed:
            raise ProfileError(f"{self.name}: broker {self.broker!r} not allowed for {self.mode}")
        if not _DIGEST.fullmatch(self.account_fingerprint):
            raise ProfileError(f"{self.name}: account_fingerprint must be a SHA-256 hex digest")
        if not self.credential_refs or not all(_ENV_NAME.fullmatch(r) for r in self.credential_refs):
            raise ProfileError(f"{self.name}: credential_refs must be environment variable names")
        if not (self.bot_budget_usd > 0):
            raise ProfileError(f"{self.name}: bot_budget_usd must be positive")
        if not (0 < self.daily_deploy_fraction <= 1):
            raise ProfileError(f"{self.name}: daily_deploy_fraction must be in (0, 1]")
        if not self.instruments or not set(self.instruments) <= INSTRUMENTS:
            raise ProfileError(f"{self.name}: instruments must be a subset of {sorted(INSTRUMENTS)}")
        for field in ("name", "state_dir", "log_namespace", "safety_config_version"):
            if not str(getattr(self, field)).strip():
                raise ProfileError(f"{self.name}: {field} is required")


def load_profiles(raw_profiles: list[dict]) -> dict[str, ModeProfile]:
    """Validate every profile and refuse any shared namespace or identity."""
    profiles: dict[str, ModeProfile] = {}
    seen: dict[str, dict] = {field: {} for field in _UNIQUE}
    for raw in raw_profiles:
        values = dict(raw)
        values["credential_refs"] = tuple(values.get("credential_refs", ()))
        values["instruments"] = tuple(values.get("instruments", ()))
        try:
            profile = ModeProfile(**values)
        except TypeError as error:
            raise ProfileError(f"profile fields: {error}") from error
        if profile.name in profiles:
            raise ProfileError(f"duplicate profile name {profile.name!r}")
        for field in _UNIQUE:
            keys = getattr(profile, field)
            for key in (keys if field == "credential_refs" else (keys,)):
                if key in seen[field]:
                    raise ProfileError(f"{field} shared by {seen[field][key]!r} and {profile.name!r}")
                seen[field][key] = profile.name
        profiles[profile.name] = profile
    return profiles


def default_profile_name(profiles: dict[str, ModeProfile]) -> str:
    """The profile used when nothing is chosen: always the small PAPER profile."""
    profile = profiles.get(DEFAULT_PROFILE)
    if profile is None or profile.mode != "PAPER":
        raise ProfileError(f"default profile {DEFAULT_PROFILE!r} must exist and be PAPER")
    return DEFAULT_PROFILE


@dataclass(frozen=True)
class ArmingRecord:
    profile_name: str
    account_fingerprint: str
    capital_gate_evidence_sha256: str
    activated_by: str
    activated_at: datetime
    expires_at: datetime


def require_armed(profile: ModeProfile, record: ArmingRecord | None, *, now: datetime) -> None:
    """Refuse LIVE use unless ``record`` arms exactly this profile and account now.

    An arming record is Camden's activation, not evidence that the capital gate passed.
    """
    if now.tzinfo is None:
        raise ProfileError("now must be timezone-aware")
    if profile.mode == "PAPER":
        return
    if record is None:
        raise ProfileError(f"{profile.name}: LIVE profile is not armed")
    if record.profile_name != profile.name:
        raise ProfileError(f"{profile.name}: arming record is for profile {record.profile_name!r}")
    if record.account_fingerprint != profile.account_fingerprint:
        raise ProfileError(f"{profile.name}: arming record is for a different account")
    if not _DIGEST.fullmatch(record.capital_gate_evidence_sha256):
        raise ProfileError(f"{profile.name}: capital-gate evidence digest missing")
    if record.activated_by != "Camden":
        raise ProfileError(f"{profile.name}: only Camden arms LIVE")
    if record.activated_at.tzinfo is None or record.expires_at.tzinfo is None:
        raise ProfileError(f"{profile.name}: arming timestamps must be aware")
    if record.activated_at > now:
        raise ProfileError(f"{profile.name}: arming activated in the future")
    if record.expires_at <= now:
        raise ProfileError(f"{profile.name}: arming expired")


# --- U2: budget-bounded, daily-capped, settled-cash buy sizing (FR-004/005/007/008) ---

from decimal import ROUND_FLOOR, Decimal
import math

_SIX = Decimal("0.000001")


@dataclass(frozen=True)
class BuyRequest:
    ticker: str
    quantity: float
    ref_price: float
    fractionable: bool


@dataclass(frozen=True)
class SizedBuy:
    ticker: str
    quantity: float
    notional: float


def sizing_equity(profile: ModeProfile, *, bot_owned_value: float, bot_cash: float) -> float:
    """Equity the bot may size against: its budget, never the broker account's balance."""
    return min(profile.bot_budget_usd, bot_owned_value + bot_cash)


def _floor_qty(quantity: Decimal, fractional: bool) -> Decimal:
    if fractional:
        return quantity.quantize(_SIX, rounding=ROUND_FLOOR)
    return quantity.to_integral_value(rounding=ROUND_FLOOR)


def bound_buys(profile: ModeProfile, buys: list[BuyRequest], *, settled_cash: float,
               deployed_today_usd: float, min_notional_usd: float
               ) -> tuple[list[SizedBuy], list[tuple[str, str]]]:
    """Shrink buys, in order, to fit the daily deploy cap and settled cash.

    Guarantees: total accepted notional <= min(daily cap remaining, settled cash);
    quantities only ever shrink and are floored (whole shares unless both the
    profile and the instrument allow fractions, then six decimals); each dropped
    buy carries one reason: daily_cap, insufficient_settled_cash, budget_exhausted
    or below_minimum. Sells are not this function's concern.
    """
    cap_left = Decimal(str(profile.daily_deploy_fraction * profile.bot_budget_usd)) - Decimal(str(deployed_today_usd))
    cash_left = Decimal(str(settled_cash))
    accepted: list[SizedBuy] = []
    refused: list[tuple[str, str]] = []
    for buy in buys:
        if not (math.isfinite(buy.ref_price) and buy.ref_price > 0):
            raise ValueError(f"{buy.ticker}: reference price must be positive and finite")
        if not (math.isfinite(buy.quantity) and buy.quantity > 0):
            raise ValueError(f"{buy.ticker}: buy quantity must be positive and finite")
        price = Decimal(str(buy.ref_price))
        fractional = profile.fractional and buy.fractionable
        if cap_left <= 0:
            refused.append((buy.ticker, "daily_cap"))
            continue
        spend = min(cap_left, cash_left)
        qty = _floor_qty(min(Decimal(str(buy.quantity)), spend / price), fractional)
        if qty <= 0:
            refused.append((buy.ticker, "insufficient_settled_cash" if cash_left < cap_left else "budget_exhausted"))
            continue
        notional = qty * price
        if notional < Decimal(str(min_notional_usd)):
            refused.append((buy.ticker, "below_minimum"))
            continue
        accepted.append(SizedBuy(buy.ticker, float(qty), float(notional)))
        cap_left -= notional
        cash_left -= notional
    return accepted, refused


# --- U3: ownership and aggregate exposure (FR-006) ---

OWNERS = ("bot", "external")


@dataclass(frozen=True)
class Holding:
    ticker: str
    quantity: float
    owner: str

    def __post_init__(self) -> None:
        if self.owner not in OWNERS:
            raise ValueError(f"{self.ticker}: owner must be one of {OWNERS}")
        if not (math.isfinite(self.quantity) and self.quantity >= 0):
            raise ValueError(f"{self.ticker}: quantity must be finite and non-negative (long-only)")


def bot_sell_quantities(desired_bot_qty: dict[str, float], holdings: list[Holding]) -> dict[str, float]:
    """Sell quantities that move bot-owned lots down to ``desired_bot_qty``.

    Guarantees: only ``owner == "bot"`` quantity is ever sold; an external holding
    never produces a sell, whether or not it appears in the targets.
    """
    owned: dict[str, float] = {}
    for holding in holdings:
        if holding.owner == "bot":
            owned[holding.ticker] = owned.get(holding.ticker, 0.0) + holding.quantity
    sells = {}
    for ticker, quantity in owned.items():
        excess = quantity - max(0.0, float(desired_bot_qty.get(ticker, 0.0)))
        if excess > 0:
            sells[ticker] = min(excess, quantity)
    return sells


def aggregate_exposure(holdings: list[Holding], prices: dict[str, float]) -> dict[str, float]:
    """Market value per ticker across every owner, bot and external."""
    exposure: dict[str, float] = {}
    for holding in holdings:
        exposure[holding.ticker] = exposure.get(holding.ticker, 0.0) + holding.quantity * prices[holding.ticker]
    return exposure


def concentration_refusals(holdings: list[Holding], prices: dict[str, float], proposed_buy_qty: dict[str, float],
                           *, portfolio_value: float, max_position_pct: float) -> list[str]:
    """Tickers whose post-buy exposure, external holdings included, exceeds the limit."""
    exposure = aggregate_exposure(holdings, prices)
    return sorted(t for t, q in proposed_buy_qty.items()
                  if exposure.get(t, 0.0) + q * prices[t] > max_position_pct * portfolio_value)
