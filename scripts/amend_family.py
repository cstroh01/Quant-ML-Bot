"""Spec 058 T006a (Camden runs this): record an additions-only family declaration amendment.

Usage: python scripts/amend_family.py 058-edge --record

Writes docs/trials/families/<family>.amend-<k>.json. It refuses without --record, when the
committed source changes or removes a frozen value, when nothing was added, and once that
family has any trial.
"""
from __future__ import annotations

import argparse
import json
import sys

from trial_registry import DECLARED_FAMILIES, amend_family, production_recording


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("family", choices=sorted(DECLARED_FAMILIES))
    parser.add_argument("--record", action="store_true", help="deliberately write to docs/trials (required)")
    args = parser.parse_args(argv)
    if not args.record:
        print("Refused: pass --record to write the amendment to docs/trials.", file=sys.stderr)
        return 2
    with production_recording(reason=f"spec 058 T006a amendment of {args.family}"):
        record = amend_family(args.family)
    print(json.dumps({"family": record["family"], "amendment_index": record["amendment_index"],
                      "added": sorted(record["added"]), "record_hash": record["record_hash"],
                      "previous_record_hash": record["previous_record_hash"],
                      "ledger_head_at_amendment": record["ledger_head_at_amendment"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
