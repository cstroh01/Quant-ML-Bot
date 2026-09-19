# Data Model: Finish the Spec 019 Migration

021 adds no persisted data, schema or artifact. Its "data" is the migration
ledger itself: what is being moved, where, by whom, and what proves it
moved. These are the entities `tasks.md` tracks, with the rules each one must
satisfy.

## Contract delta

One 019 behavior change a consumer must absorb.

| Field | Rule |
|---|---|
| `id` | `C1`–`C7`. It is fixed, and new deltas append. |
| `library_site` | A `file:line` range in a library module. It is read-only in 021. |
| `obligation` | One sentence a reviewer can check at a call site. |

The seven deltas, and what each one obliges, are listed in spec.md → The
contract deltas.

## Call site

A production line or a test that consumes one or more deltas.

| Field | Rule |
|---|---|
| `path::symbol` | A production function, or a test ID from research R-1 |
| `lane` | `A`–`G`. Exactly one lane owns each *file* (plan.md → Lanes) |
| `first_delta`, `second_delta` | From research R-1. `second_delta` may be empty |
| `change` | The migration, stated as the new property. Not "update test" |
| `gated_by` | Empty, or `D-2` |
| `status` | See the transitions below |

**State transitions.**

```text
failing ──migrate──▶ migrated ──red evidence recorded──▶ verified ──suite green in lane──▶ done
   │                                  ▲
   └──(gated_by D-2, not signed)──▶ blocked ──sign-off──┘
```

- `verified` applies only to gates, meaning the call sites listed in research
  R-10. Every other call site goes straight from `migrated` to `done` when its
  lane's focused run passes.
- A call site may not reach `done` while any hunk in its file belongs to
  another lane's open PR (FR-020, D-6).

## Residual failure

A failing test that 021 deliberately leaves failing.

| Field | Rule |
|---|---|
| `test_id` | One of the 21 in research R-1, under Residual |
| `cause` | The first error, plus the frozen or foreign file that owns the fix |
| `owner` | A follow-on spec, 018 T024, or 020 wiring |

**Invariant.** The residual set may shrink, when an owner lands first. It may
never grow. Anything failing outside it after 021 is a 021 defect (SC-001).

## Decision

| Field | Rule |
|---|---|
| `id` | `D-1`–`D-7` |
| `recommendation` | The default the tasks implement |
| `rejected` | At least one alternative, with the reason |
| `gates_tasks` | `true` only for D-2 |
| `signed_off` | Recorded in spec.md by Camden. Never inferred from chat |

## Lane

| Field | Rule |
|---|---|
| `id` | `A`–`G` |
| `files` | Exclusive. No file appears in two lanes that can run concurrently |
| `frozen_regions` | Regions inside owned files that other lanes read (research R-11). The lane must not edit them |
| `preconditions` | A landed lane or a signed decision |
| `budget` | ≤ 400 changed production + test lines per PR, measured with `diff -u` against a pre-edit snapshot (no `git`) |
