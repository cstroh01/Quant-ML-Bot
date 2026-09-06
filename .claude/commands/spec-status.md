\---

description: Audit all specs — what's done, what's unchecked, what's untested

\---



For every folder under `.specify/specs/`, read `tasks.md` and report:

1\. Total tasks vs. checked `\[x]` tasks.

2\. For unchecked tasks, grep the referenced files/functions in `scripts/`

&#x20;  and `tests/` to see if the work actually landed anyway (spec files lag

&#x20;  behind real commits sometimes).

3\. Flag any spec whose tasks.md is 100% unchecked but whose named files

&#x20;  already exist in scripts/ — that's a stale spec, not a stalled one.

Output as a short table: spec # | status | next unblocked task.

