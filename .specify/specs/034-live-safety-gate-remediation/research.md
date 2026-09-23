# Research Decisions: Live-Safety-Gate Remediation

## Order-path seam

**Decision**: `scripts/order_gateway.py` exposes one `submit_order` function.
It calls `LiveSafetyGate.evaluate_order` exactly once and invokes a caller-owned
submission callback only when `decision.outcome == ALLOW`. Every other result
raises an exception carrying the original `GateDecision`.

**Rationale**: This creates a testable mandatory sequencing boundary without
choosing a broker or introducing network/credential code.

**Alternatives considered**: A concrete broker adapter violates the spec's
non-goals. Returning a warning/boolean permits callers to ignore a denial.

## Broker-import static enforcement

**Decision**: Add an AST test that scans production Python modules for imports
from an explicit broker-client root set and requires a same-module import of
`LiveSafetyGate`. Test the guard itself against a planted missing-import module
and a passing control module.

**Rationale**: AST inspection avoids comment/string false positives and fails CI
when a recognized broker SDK enters outside the safety boundary.

**Alternatives considered**: Text grep is structurally weaker. An import hook is
runtime-only and cannot protect an unexecuted adapter.

## Pending-order exposure

**Decision**: Aggregate only positive, non-terminal pending quantities into
worst-case exposure. Negative pending quantities remain durable reservations
for duplicate/order-lifecycle control but do not reduce current position or gross
notional until the broker snapshot confirms the fill.

**Rationale**: Simultaneous pending buys and sells cannot safely net; the sell
may cancel, reject, or partially fill while the buy executes.

**Alternatives considered**: Clamping the signed aggregate to zero is unsafe
when a pending buy and pending sell offset each other before aggregation.

## Equity floor

**Decision**: Preserve the existing pre-division `equity <= 0` denial and add
separate zero and negative regression tests plus a planted mutant that removes
the guard.

**Rationale**: The current checkout already routes nonpositive equity through
`_check_freshness`; explicit cases and mutation evidence prevent a future
refactor from reintroducing divide-by-zero or sign-flipped comparisons.

**Alternatives considered**: Adding a second redundant guard beside each
division increases drift without changing behavior.

## Safety API lifecycle

**Decision**: `reports/api/routes/safety.py` receives `LiveSafetyGate` through a
FastAPI dependency. The default dependency fails closed with HTTP 503 until a
reviewed process bootstrap supplies the gate. Tests override it with a temporary
SQLite-backed gate.

**Rationale**: No numeric configuration defaults are authorized, and the router
must not open an arbitrary safety database at import time.

**Alternatives considered**: A module-global gate would invent configuration and
state paths. Passing database/config values through public requests would expose
control-plane internals and weaken the boundary.

