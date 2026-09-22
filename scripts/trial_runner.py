"""Record research intent outside accounting; never infer missing OOS provenance."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import inspect
import math
import os
import uuid
from pathlib import Path
import numpy as np
import pandas as pd
from trial_registry import CONFIG_FIELDS, ROOT, TrialLedger, relative_path

_injected = ContextVar("trial_ledger", default=None)

def current_ledger() -> TrialLedger:
    """Use production unless an explicitly labelled test root was injected."""
    if _injected.get() is not None:
        return _injected.get()
    fixture_root = os.environ.get("SPEC033_SYNTHETIC_ROOT")
    if fixture_root:
        root = Path(fixture_root)
        if (root / "synthetic-context.json").read_text(encoding="utf-8") != "EXAMPLE — NOT A RESULT":
            raise ValueError("unlabelled synthetic context")
        # Unrelated mechanical fixtures do not constitute a lifetime history.
        # Each implicit attempt owns a temporary ledger; its context manager
        # retains that instance across start/terminal. Explicit injections still
        # share one ledger for lifecycle, concurrency, and lifetime-count tests.
        return TrialLedger(root / "attempts" / uuid.uuid4().hex, synthetic=True)
    return TrialLedger()

@contextmanager
def injected_ledger(ledger: TrialLedger):
    if not ledger.synthetic:
        raise ValueError("test injection requires synthetic ledger")
    token = _injected.set(ledger)
    try:
        yield ledger
    finally:
        _injected.reset(token)

def run_trial(callback, config: dict, *, family: str, runner: str, metadata: dict,
              role: str = "candidate", ledger: TrialLedger | None = None,
              source: dict | None = None):
    """Append/fsync intent before invoking an opaque return-series callback."""
    ledger = ledger or current_ledger()
    trial = ledger.start(config, role=role, family=family, runner=runner, source=source)
    try:
        result = callback()
        receipt = ledger.finish(trial, "completed", returns=result, metadata=metadata)
    except BaseException as exc:
        ledger.finish(trial, "abandoned" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "errored", reason=type(exc).__name__)
        raise
    return result, receipt

def _snapshot(value):
    if isinstance(value, pd.DataFrame):
        hashes = value.to_json(orient="split", date_format="iso", double_precision=15).encode()
        return {"type": "dataframe", "sha256": hashlib.sha256(hashes).hexdigest(),
                "columns": list(value.columns), "rows": len(value), "attrs": _snapshot(value.attrs)}
    if isinstance(value, (pd.Series, pd.Index, np.ndarray)):
        return {"type": type(value).__name__, "sha256": hashlib.sha256(pd.util.hash_pandas_object(pd.Series(value), index=True).values.tobytes()).hexdigest(), "rows": len(value)}
    if isinstance(value, dict): return {str(k): _snapshot(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)): return [_snapshot(v) for v in value]
    if isinstance(value, Path):
        try:
            return relative_path(ROOT, value)
        except ValueError:
            if current_ledger().synthetic:
                return {"synthetic_path": value.name}
            raise
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, float) and not math.isfinite(value): return {"nonfinite_input": str(value)}
    if value is None or isinstance(value, (str, int, bool, float)): return value
    if hasattr(value, "get_params"): return {"type": type(value).__name__, "params": _snapshot(value.get_params(deep=False))}
    if hasattr(value, "__dataclass_fields__"):
        return {k: _snapshot(getattr(value, k)) for k in value.__dataclass_fields__ if k != "factory"}
    if callable(value): return {"callable": getattr(value, "__qualname__", type(value).__name__)}
    return {"type": type(value).__name__, "unresolved": True}

def research_config(runner: str, values: dict, defaults: dict | None = None) -> dict:
    """Capture runner choices; absent contracts remain explicit and ineligible."""
    frame = inspect.currentframe().f_back
    constants = {k: _snapshot(v) for k, v in frame.f_globals.items() if k.isupper() and not k.startswith("_")}
    arguments = {k: _snapshot(v) for k, v in values.items() if k not in {"receipt", "attempt"} and not k.startswith("_")}
    result = {name: None for name in CONFIG_FIELDS}
    result.update(defaults or {})
    result.update(runner=runner, resolved_arguments=arguments, module_defaults=constants,
                  evidence_status="legacy runner: OOS/cost/action provenance not established")
    return result

class Attempt:
    def __init__(self, ledger, trial):
        self.ledger, self.trial, self.receipt = ledger, trial, None

    def returns(self, rows: list[dict], metadata: dict) -> None:
        self.receipt = self.ledger.finish(self.trial, "completed", returns=rows, metadata=metadata)

    def account(self, trade_log: pd.DataFrame) -> None:
        """Preserve every funded daily row without falsely claiming walk-forward OOS."""
        events = trade_log.attrs.get("ledger")
        if events is None or events.empty:
            return
        closes = events[events.Phase == "close"].groupby("Date", sort=True).tail(1)
        equity = closes.Equity.to_numpy(dtype=float)
        previous = np.r_[trade_log.attrs["capital_base"], equity[:-1]]
        rows = [{"session": pd.Timestamp(d).strftime("%Y-%m-%d"), "log_return": float(r)} for d, r in zip(closes.Date, np.log(equity / previous))]
        self.returns(rows, {"frequency": "daily", "return_convention": "funded_account_log", "net_costs": True, "oos": False,
                           "cv": None, "costs": {"commission": trade_log.attrs["commission_per_trade"], "slippage": {"model": "flat_bps", "bps": trade_log.attrs["slippage_bps"]}},
                           "ineligible_reason": "legacy_oos_and_realistic_cost_provenance_missing"})

@contextmanager
def research_attempt(config: dict, *, role: str = "candidate", family: str = "legacy-research"):
    """Record before fitting/evaluation, including failed diagnostic searches."""
    ledger = current_ledger()
    actual_role = "synthetic_test" if ledger.synthetic else role
    trial = ledger.start(config, role=actual_role, family=family, runner=config["runner"])
    attempt = Attempt(ledger, trial)
    try:
        yield attempt
    except BaseException as exc:
        if attempt.receipt is None:
            attempt.receipt = ledger.finish(trial, "abandoned" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "errored", reason=type(exc).__name__)
        raise
    else:
        if attempt.receipt is None:
            attempt.receipt = ledger.finish(trial, "rejected", reason="no_complete_funded_daily_returns; diagnostic selection attempt retained")
