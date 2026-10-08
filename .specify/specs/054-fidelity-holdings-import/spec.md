# Feature Specification: Fidelity holdings as read-only exposure input

**Spec number**: 054
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. Offline units authorized.
**Depends on**: 051 (ownership/exposure boundary). Related: 057 (LIVE adapter can also read positions).

## 1. Purpose
Bring Camden's Fidelity holdings and cash into total-portfolio exposure. Holdings are inputs, never
bot-owned, never sell targets.

## 2. Requirements
- **FR-001 Inputs.** Fidelity CSV exports (Positions, Activity/History) dropped privately, or a
  positions snapshot read by the 057 adapter. Parser handles Fidelity's preamble/footer lines,
  quoted numbers, `--` blanks and cash rows (e.g. `SPAXX**`, "Cash").
- **FR-002 Normalized snapshot.** symbol, quantity, price, market value, currency (USD only),
  account pseudonym (hash), `as_of` instant (export timestamp, e.g. "Date downloaded"), source,
  SHA-256 of the raw file. Stored privately; never in the public repo.
- **FR-003 Ownership.** Every imported position is `owner=external`. Only lots the bot itself
  opened (051 FR-006) are `owner=bot`.
- **FR-004 Staleness.** A snapshot older than 1 business day is `stale`; stale exposure is never
  replaced by zero. New LIVE buys that could breach limits under stale data are refused.
- **FR-005 Capability labels.** Each source declares read_holdings / read_activity / submit_orders.
  A read capability never satisfies an order requirement.

## 3. Decisions (2026-10-07)
- **D-1 (Camden)** Individual brokerage account; CSV export now (sample: History export, $100 cash on 2026-09-25).
- **D-2 (quant-ml-genius)** CSV first; adapter positions (057) second; aggregator APIs not used.
- **D-3 (quant-ml-genius)** Stale after 1 business day (NYSE calendar).
- **D-4 (quant-ml-genius)** USD only; non-USD rows excluded with a reason; money-market sweep counts as cash.

## 4. Rule 12 mutants
Missing as_of accepted; stale snapshot treated as fresh; missing holdings read as zero; external
position marked bot-owned (must create no sell intent); read capability accepted for order submit;
footer/disclaimer text parsed as a position.

## 5. Acceptance
Synthetic Positions and History fixtures (mirroring Fidelity's real layout) parse exactly; mutants
killed; Camden's own export parses privately with no account data committed.
