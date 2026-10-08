# 057 U0: dependency audit of candidate Fidelity libraries (2026-10-07)

Offline source reading only. No credentials, no Fidelity request, no account access.
Downloaded from PyPI into a scratch directory; nothing added to `requirements*.txt`.

| | `fidelity-trader-api` 0.2.2 | `fidelity-api` 0.0.17 |
|---|---|---|
| Wheel SHA-256 | `f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15` | `4d6e3cb4ab905e2ab966b7e8f139c5557bc09dbb4e68b7384e27369c2dc3f27f` |
| Source | github.com/brownjosiah/fidelity-trader-api | github.com/kennyboy106/fidelity-api |
| Mechanism | HTTP client (httpx) for Trader+ endpoints, reverse-engineered | Playwright browser automation of fidelity.com |
| Size | ~10.5k lines | ~1.6k lines |
| Runtime deps | httpx, pydantic (boto3 optional) | playwright, playwright-sm, pyotp |
| Login | `login(username, password, totp_secret)` | browser form + pyotp TOTP |
| Network destinations in source | Fidelity domains only (`*.fidelity.com`) plus Fidelity's embedded research vendors (`fidelity.apps.livevol.com`, `fidelity-widgets.financial.com`) used only by research modules | `digital.fidelity.com` only |
| Telemetry / third-party upload | none found | none found |
| Equity preview/place | yes: `preview_order` returns `confNum`; `place_order(order, conf_num)` | yes (UI flow) |
| Order status read | yes (`orders/status.py`) | positions/summary pages |

## Findings that bind the adapter (U1)

1. **Retries can duplicate orders.** `RetryTransport` replays any request, POSTs included, on
   timeouts and 5xx. Default `max_retries=0`; the adapter MUST construct clients with
   `max_retries=0` and never enable retries for preview/place/cancel (FR-006).
2. **Margin by default.** `EquityOrderRequest.acct_type_code` defaults to `"M"` (margin). The adapter
   MUST set `"C"` (cash) on every order; D-3 forbids margin.
3. **No client order id.** Fidelity orders carry a `confNum` from preview, not a caller id. The
   adapter maps the bot's deterministic client id (055) to the preview `confNum` and persists that
   mapping BEFORE `place_order`; reconciliation reads status by `confNum`.
4. **Credential repr.** The library's `Credentials` dataclass has a default `repr` that prints the
   password. The adapter never constructs or logs it; it passes values straight from secrets.
5. **CLI prints cookie counts** (`cli/_auth.py`); the adapter never imports `cli`.

## Recommendation (quant-ml-genius, D-2)
Adopt `fidelity-trader-api==0.2.2` pinned by the hash above, imported only inside
`exec/fidelity_live.py`, behind the broker interface so it can be replaced. Keep `fidelity-api`
(Playwright) as the documented fallback. Re-audit on every version bump. Risk accepted by Camden
(SCOPE-V1 §10); this audit does not make the integration authorized by Fidelity.
