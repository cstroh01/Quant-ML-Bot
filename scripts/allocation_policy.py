"""061 adoption identity; the frozen research implementation remains unchanged."""

POLICY_ID = "061-b7-ew-v1"
TRIAL_ID = "8d4dfeda-10ef-4951-bf0e-147090ea9731"
DECLARATION_HASH = "4a154bfb27bd89dc484b466066b83e01baca20dc98f577c7beb4f4ca24f3b55f"
LABEL = "ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED"
DISCLOSURE = ("Monthly equal-weight allocation with 7% pre-cost target cash, selected after 059 T004; "
              "fresh costed trial under spec 061, in-sample and post-hoc, not an edge claim. "
              "Daily bars, survivor ETF basket, free corporate actions, modeled costs; "
              "rounding, deployment caps and deferred buys can differ from the research backtest. "
              + LABEL)


def policy_evidence() -> dict:
    """Nonsecret identities carried with every new allocation record and state."""
    return {"policy_id": POLICY_ID, "trial_id": TRIAL_ID, "declaration_hash": DECLARATION_HASH}
