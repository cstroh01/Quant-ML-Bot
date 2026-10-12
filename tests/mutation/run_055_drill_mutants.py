"""Rule 12 driver for spec 055 T007 drill support (queue Q102): drill-only clock and lease, per-profile kill.

Run: python tests/mutation/run_055_drill_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
control, witness-carrying-failure and byte-identity checks against `scripts/ops_runner.py`.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/ops_runner.py"
TEST = "tests/test_055_drill_support.py"
NOW_OR_LEASE = "if (args.now is not None or args.hold_lease is not None) and not args.drill:"
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("injected clock accepted on a submit run", 'if args.drill and _may_submit(args.command or ""):',
     "if False:", "055 DRILL SUBMIT"),
    ("abbreviated --submit missed", 'len(token) > 2 and "--submit".startswith(token)', "False", "055 DRILL SUBMIT"),
    ("submit inside a shell wrapper missed", '"submit" in command.lower() or', '"--submit" in shlex.split(command) or',
     "055 DRILL SUBMIT"),
    ("drill persist command accepted", "if args.drill and args.persist_command:", "if False:", "055 DRILL PERSIST"),
    ("drill on unmarked state", 'if args.drill != (args.state_dir / "DRILL").exists():',
     'if not args.drill and (args.state_dir / "DRILL").exists():', "055 DRILL MARKER"),
    ("every submit refused", 'if args.drill and _may_submit(args.command or ""):', 'if _may_submit(args.command or ""):',
     "055 REAL SUBMIT"),
    ("second kill overwrites the first", "if reset != path.exists():", "if reset and not path.exists():",
     "055 KILL TWICE"),
    ("injected clock without --drill", NOW_OR_LEASE, "if args.hold_lease is not None and not args.drill:",
     "055 DRILL ONLY"),
    ("held lease without --drill", NOW_OR_LEASE, "if args.now is not None and not args.drill:", "055 LEASE DRILL ONLY"),
    ("naive injected clock accepted", "if args.now is not None and args.now.tzinfo is None:", "if False:",
     "055 DRILL AWARE"),
    ("injected clock ignored", "now=args.now or _now()", "now=_now()", "055 DRILL CLOCK"),
    ("kill applied to the other profile", 'f"kill-{require_storage_identifier(profile)}.json"', '"kill.json"',
     "055 KILL OTHER PROFILE"),
    ("killed profile still runs", "if _kill_path(state_dir, profile).exists():", "if False:", "055 KILL"),
    ("kill without a reason", 'if not str(reason or "").strip():', "if False:", "055 KILL REASON"),
    ("reset clears a kill without the explicit flag",
     "if args.reset_kill is not None and args.confirm_reset != args.profile:", "if False:", "055 RESET CONFIRM"),
    ("reset leaves the kill in place", "        path.unlink()\n    else:", "        pass\n    else:", "055 RESET"),
    ("reset clears every profile", "        path.unlink()\n    else:",
     "        [k.unlink() for k in path.parent.glob(\"kill-*.json\")]\n    else:", "055 RESET"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, TEST
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", TEST), 7, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
