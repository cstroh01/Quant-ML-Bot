"""§11.3.5 replay inputs from the private 058 T008 Tiingo bodies (EXAMPLE — NOT A RESULT).

Writes `<TICKER>.csv` (Date, Open, Close) for the 8 allocation sleeves, the `--history-dir` that
`scripts/replay_runner.py` reads. Prices are Tiingo's split- and dividend-adjusted `adjOpen`/`adjClose`:
split-consistent and gap-free, which is what a code-path replay needs (the 058 D-10 B research panel
marks T009 exclusions untradable, and the PAPER loop would refuse those sessions as missing data).
Each body is found by SHA-256 against the committed T008 manifest, so the inputs are the bodies 058
T015 runs on; rows after RESEARCH_END are dropped. Prints a provenance JSON for the evidence record.

Usage: python scripts/replay_inputs_058.py --panel <058-tiingo raw folder> --out <private dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

from data_sources import RESEARCH_END
from run_058_t015 import T008_MANIFEST
from signals import ALLOCATION_SLEEVES
from trial_registry import ROOT


def build(raw_dir: Path, out: Path, *, manifest: dict) -> dict:
    """Write the sleeve CSVs; raises ValueError naming any sleeve whose body is missing or altered."""
    wanted = {r["endpoint_path"].split("/")[3]: r["sha256"] for r in manifest["requests"]
              if r["endpoint_path"].endswith("/prices")}
    found = {hashlib.sha256(p.read_bytes()).hexdigest(): p for p in sorted(Path(raw_dir).glob("*.bin"))}
    missing = [t for t in ALLOCATION_SLEEVES if wanted.get(t) not in found]
    if missing:
        raise ValueError(f"body missing or altered for: {','.join(missing)}")
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for ticker in ALLOCATION_SLEEVES:
        rows = json.loads(found[wanted[ticker]].read_bytes())
        frame = pd.DataFrame(rows)
        frame["Date"] = frame["date"].str[:10]
        frame = frame[frame["Date"] <= str(RESEARCH_END)][["Date", "adjOpen", "adjClose"]]
        frame = frame.rename(columns={"adjOpen": "Open", "adjClose": "Close"})
        if frame[["Open", "Close"]].isna().any().any():
            raise ValueError(f"{ticker}: adjusted price missing")
        path = out / f"{ticker}.csv"
        frame.to_csv(path, index=False)
        files[ticker] = {"body_sha256": wanted[ticker], "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "rows": len(frame), "first": frame["Date"].iloc[0], "last": frame["Date"].iloc[-1]}
    return {"label": "EXAMPLE — NOT A RESULT", "source": "058 T008 Tiingo bodies (private), adjOpen/adjClose",
            "manifest": T008_MANIFEST, "research_end": str(RESEARCH_END), "files": files}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--panel", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="private folder outside the repo (vendor data)")
    a = p.parse_args(argv)
    if ROOT in a.out.resolve().parents or a.out.resolve() == ROOT:
        print("refused: --out must be outside the repo (never commit market data)", file=sys.stderr)
        return 2
    manifest = json.loads((ROOT / T008_MANIFEST).read_text(encoding="utf-8"))
    try:
        provenance = build(a.panel, a.out, manifest=manifest)
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(provenance, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
