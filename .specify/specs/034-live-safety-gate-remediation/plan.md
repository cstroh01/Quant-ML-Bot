# Implementation Plan: Live-Safety-Gate Remediation

**Branch**: `034-live-safety-gate-remediation` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `.specify/specs/034-live-safety-gate-remediation/spec.md`

## Summary

Close REQ-034-001 through REQ-034-005 without building a broker adapter. Add a
single order-submission chokepoint that fail-closes on every outcome other than
`ALLOW`, repair the two state/exposure defects in `live_safety_gate.py`, pin the
nonpositive-equity denial with explicit regression coverage, and expose the five
Gate 5 operations through a new dependency-injected FastAPI router. Tests are
written and recorded red before each production change.

## Technical Context

**Language/Version**: Python 3.13, `from __future__ import annotations`

**Primary Dependencies**: Python standard library (`ast`, `dataclasses`,
`sqlite3`, typing); existing FastAPI 0.141.1 and Pydantic installation only

**Storage**: Existing caller-supplied SQLite safety-state database; no new store

**Testing**: `pytest`; focused red/green runs followed by `python -m pytest tests`

**Target Platform**: Windows research workstation and GitHub Actions Linux

**Project Type**: Python library plus local FastAPI operational control surface

**Performance Goals**: Preserve the existing single-transaction order decision;
the order gateway performs exactly one safety evaluation before its callback

**Constraints**: No broker/network/credential code; no `exec/`; no numeric safety
defaults; no edits to `reports/api/routes/capital_gate.py`; additive schema
models only; no Git commands

**Scale/Scope**: One chokepoint, two safety-gate fixes, one already-enforced
equity invariant pinned by explicit tests, five API endpoints, and CI/static
coverage for future broker-client imports

## Constitution Check

*GATE: Passed before design and re-checked after Phase 1.*

| Rule | Plan bearing | Status |
|---|---|---|
| 1/2 | No historical feature, label, or cross-validation work | N/A |
| 3/4/13-15 | No reported strategy result, cost model, or statistical gate | N/A |
| 5 | API datetimes remain aware; equity and latch boundary tests cover exact edge cases | PASS |
| 6 | No dependency added | PASS |
| 7 | The gateway accepts a caller callback but contains no broker client, network call, credential, or `exec/` code | PASS |
| 8 | `order_gateway.py` depends only on the safety contract; the API remains a thin wrapper | PASS |
| 9 | Plan, tasks, red evidence, and handoff explain each mechanism and failure consequence | PASS |
| 10 | No Git commands | PASS |
| 11 | No performance figures are introduced | PASS |
| 12 | Each remediation has a real failing regression or planted-defect proof plus a green control | PASS |

Post-design re-check: the dependency-injected router does not invent live
configuration, the chokepoint cannot submit after a deny, and the protected
capital-gate route is outside every task. No constitutional exception is needed.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/034-live-safety-gate-remediation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── safety-api.md
├── tasks.md
└── HANDOFF.md
```

### Source Code (repository root)

```text
scripts/
├── live_safety_gate.py       # narrow latch/exposure fixes; public alias
└── order_gateway.py          # mandatory fail-closed submission seam

reports/api/
├── main.py                   # registers the new router
├── schemas.py                # additive Safety* models only
└── routes/
    └── safety.py             # new Gate 5 operational router

tests/
├── test_live_safety_gate.py  # latch, pending-sell, equity regressions
├── test_order_gateway.py     # chokepoint and AST/static enforcement
└── test_safety_router.py     # five endpoint contracts and dependency seam
```

**Structure Decision**: Keep the safety engine and order chokepoint in the flat
`scripts/` library layout and the operational API in a new route module. The
router receives a gate through FastAPI dependency injection because spec 032
forbids shipping numeric configuration defaults; production bootstrap remains a
future reviewed integration concern.

## Complexity Tracking

No constitution violations or extra architectural layers require justification.
