# Quant-ML-Bot evidence dashboard

React/TypeScript interface for the research framework's API. Displays recorded
research, diagnostics and verification status. A rendered panel, green test or
configured account is not trading permission. Consult [STATE](../../docs/STATE.md)
and [SCOPE §11.3](../../docs/SCOPE-V1.md) for the actual completion/capital gates.
The historical five-gate dashboard does not replace the seven-item checklist.

## Local development

From this directory, use the committed lockfile:

```text
npm ci
npm run dev
```

Follow the [root README](../../README.md) for backend setup and evidence
reproduction. These commands do not authorize market-data requests, research
trials or broker access. The frontend does not establish that fresh broker data,
reconciliation, notification or unattended operation has been accepted.

## Verification

```text
npm run test
npm run lint
npm run build
```

Render contracts use the existing Vitest runner. Mutation drivers run separately
and serially where they modify views; a source scan or successful build alone
does not prove that a provenance banner renders. Keep unknown/missing evidence
visible and preserve the recorded source, trial, date and limitations.

## Limitations

Full register from [SCOPE §6](../../docs/SCOPE-V1.md), mirrored by
`scripts/disclosure.py::LIMITATIONS` and checked by the static guard:

- Survivorship bias. Research uses a fixed 25-ETF universe chosen as of 2026 (spec 058). ETFs that have closed are absent. The 5-ticker mega-cap panel (AAPL/MSFT/GOOGL/NVDA/AMZN) remains a machinery smoke test, not evidence of generalizable alpha. No delisted names in either.
- Corporate-action data is free-tier and only partially reconciled. yfinance has documented split/dividend/100× pricing defects, and the only free second source covers one year of history, so older actions are unreconciled by construction and labelled as such.
- Dividend payment dates are a declared conservative bound, not observed data. No free source provides them historically. Dividend cash is credited no earlier than it could have arrived, so the ledger is never optimistic.
- No point-in-time fundamentals. Nothing knowable-on-date beyond price and volume.
- Daily bars only. No intraday, no microstructure, no order-book data.
- Costs are modeled, not calibrated. Rule 13's half-spread plus square-root impact is an estimate from daily OHLC, never validated against real fills.
- No real capital has ever been deployed, and none will be before the §11.3 capital gate passes (docs/SCOPE-V1.md §11.3 supersedes §5).
