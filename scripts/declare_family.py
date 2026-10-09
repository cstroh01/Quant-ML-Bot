"""Spec 058 T006 (Camden runs this once): write a preregistered family declaration.

Usage: python scripts/declare_family.py 058-edge --record

Writes docs/trials/families/<family>.json exactly once. It refuses without
--record, refuses a second time, and refuses if that family already has trials.
"""
from __future__ import annotations

import argparse
import json
import sys

from trial_registry import DECLARED_FAMILIES, declare_family, production_recording


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("family", choices=sorted(DECLARED_FAMILIES))
    parser.add_argument("--record", action="store_true", help="deliberately write to docs/trials (required)")
    args = parser.parse_args(argv)
    if not args.record:
        print("Refused: pass --record to write the declaration to docs/trials.", file=sys.stderr)
        return 2
    with production_recording(reason=f"spec 058 T006 declaration of {args.family}"):
        record = declare_family(args.family)
    print(json.dumps({"family": record["family"], "record_hash": record["record_hash"],
                      "declaration_hash": record["declaration_hash"],
                      "ledger_head_at_declaration": record["ledger_head_at_declaration"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
