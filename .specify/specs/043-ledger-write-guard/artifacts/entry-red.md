# T011 observed red, 2026-09-30

EXAMPLE — NOT A RESULT: labelled synthetic bundles; no real-data result.
E1: 44 records / 22 sidecars. E2: 46 / 22. E3: 230 / 110. E4: 16 / 0.
All four real mains completed and copy ledger verification passed.
E4 used two spawned workers and eight real research_attempt contexts.
E2 model evaluation/signal and E3/E4 feature/model computation are stubs;
main, research_attempt, accounting, TrialLedger and all write paths remain real.
E5: two HTTP 200 requests, each 44 records / 22 sidecars; N rose 87 → 89.
Exact changed paths and before/after hashes: entry-red-events.jsonl, e5-red-events.jsonl.
Initial E5 setup failed on Windows asyncio's internal socket pair; that run is retained.
Allowing loopback IPC fixed setup; non-loopback connections remain blocked.
Accepted E5 red proof is e5-red.txt: the assertion fails on ledger changes.
Every real ledger tripwire stayed silent; corresponding *-ledger.json files prove equality.
