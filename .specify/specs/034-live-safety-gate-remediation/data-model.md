# Data Model: Live-Safety-Gate Remediation

## Existing domain entities

- `SafetyConfig`: mandatory limit configuration and version; unchanged.
- `BrokerSnapshot`: aware timestamp, broker status, equity, external cash flow,
  positions, and conservative prices.
- `OrderIntent`: unique client order ID, instrument, and signed quantity.
- `GateDecision`: `ALLOW`/`DENY`, reason, action, checks, and optional reservation.
- `BrokerKillQuery`: broker-reported terminal-order and disable status.

## New order-gateway entity

`OrderDeniedError`

- `decision: GateDecision`
- Raised for every result whose outcome is not exactly `ALLOW`.
- The submission callback is never invoked on this transition.

State transition:

`candidate -> evaluate_order -> ALLOW -> submit callback`

`candidate -> evaluate_order -> non-ALLOW -> OrderDeniedError -> stopped`

## New API request/response models

- `SafetyBrokerSnapshot`: JSON representation of `BrokerSnapshot`.
- `SafetyBrokerKillQuery`: optional broker confirmation payload.
- `SafetyKillRequest`: operator, reason, aware `now`.
- `SafetyKillConfirmRequest`: optional query and aware `now`.
- `SafetyKillResetRequest`: operator, reason, independent-verification flag,
  aware `now`.
- `SafetyRollingHaltResetRequest`: snapshot, operator, reason, aware `now`.
- `SafetyActionResponse`: method result/status string.
- `SafetyStatusResponse`: durable state mapping returned by `status()`.

Validation rules:

- Operator and reason strings are non-empty.
- Request and snapshot datetimes are timezone-aware.
- Snapshot numeric/mapping validation is completed by the domain dataclass.
- No API model supplies safety-limit defaults or credentials.

## Durable pending-order interpretation

The existing `pending_orders.quantity` remains signed and unchanged. For
worst-case exposure only, positive non-terminal quantities add to position;
negative quantities contribute zero until broker-confirmed positions change.

