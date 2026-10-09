# 055 F02a: crash-safe leases, intents and runner state

Codex coordination 2026-10-08 23:25 CT ("crash-safe leases/intents"). Synthetic, fake commands only.
EXAMPLE — NOT A RESULT. Stacked on #101 → #97.

## Red: base `5410b3f` (#101 head), direct calls
```
base: torn lease -> JSONDecodeError (not LeaseHeld)
base: torn intent log -> JSONDecodeError (not IntentLogCorrupt)
base: stale lease -> LeaseHeld raised; no incident recorded: True
```

## Fixes
- `ops_runtime.atomic_write`: temp file in the same directory, fsync, `os.replace`, fsync of the
  directory. Used for lease completion, `first_seen.json` and `sent.json`.
- `acquire_lease` fsyncs the directory after the exclusive create. A lease torn before its JSON
  was written still blocks (`LeaseHeld`), and `complete_lease` refuses it as unreadable.
- `open_intents` raises `IntentLogCorrupt` on a torn final line (including one cut exactly at
  the newline) or an unparseable record; `record_intent` therefore refuses to append after damage.
- `runs.jsonl` / `incidents.jsonl` appends fsync.
- `run_once`: a lease with no completed run record (a crashed earlier run) becomes a `lease_held`
  incident with "reconcile before any rerun" and exit 1. It never reruns and never crashes.

## Rule 12
`python tests/mutation/run_055_durability_mutants.py` → 6/6 killed.
