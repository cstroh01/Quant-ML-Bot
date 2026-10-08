"""Synthetic spec 051 profile fixtures. EXAMPLE — NOT A RESULT."""
import hashlib


def fp(account: str) -> str:
    return hashlib.sha256(account.encode()).hexdigest()


def raw(name="paper_small", mode="PAPER", broker="alpaca_paper", account="PA-1", **extra):
    base = dict(
        name=name, mode=mode, broker=broker, account_fingerprint=fp(account),
        credential_refs=[f"{name.upper()}_KEY_ID", f"{name.upper()}_SECRET"],
        state_dir=f"state/{name}", log_namespace=name, bot_budget_usd=5000.0,
        daily_deploy_fraction=0.2, instruments=["us_equity", "etf"], fractional=True,
        safety_config_version="2026-09-29-v1",
    )
    base.update(extra)
    return base
