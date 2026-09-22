"""EXAMPLE — NOT A RESULT. Offline deterministic T055 runtime/memory probe.

Run from the repo root: python tests/spec033_pbo_profile.py
Writes only the labelled implementation-verification report, never Gate 3.
"""
import datetime
import hashlib
import json
from pathlib import Path
import time
import tracemalloc

import numpy as np

from context import SCRIPTS_DIR
from test_033_pbo import committed
from selection_bias import matrix_pbo


def main() -> None:
    row, column = np.arange(1250)[:, None], np.arange(16)[None, :]
    values = .001 + .01 * np.sin(row * .17 + column) + .004 * np.cos(row * .031 * (column + 1))
    matrix = committed(values, columns=tuple(f"example-{i:02d}" for i in range(16)))
    tracemalloc.start()
    started = time.perf_counter()
    result = matrix_pbo(matrix)
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert result["reason"] is None and result["valid_splits"] == 12870
    root = SCRIPTS_DIR.parent
    paths = [Path(__file__), root / "scripts/selection_bias.py", root / "tests/test_033_pbo.py",
             root / "tests/test_033_dsr.py", root / "tests/spec033_support.py"]
    report = {"label": "EXAMPLE — NOT A RESULT", "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "command": "python tests/spec033_pbo_profile.py", "rows": 1250, "columns": 16,
              "matrix_hash": matrix["matrix_hash"], "S": 16, "valid_splits": result["valid_splits"],
              "rejected_splits": result["rejected_splits"], "elapsed_seconds_with_tracemalloc": elapsed,
              "traced_current_bytes": current, "traced_peak_bytes": peak,
              "memory_scope": "tracemalloc Python/NumPy tracked allocations during matrix_pbo; not total process RSS",
              "source_sha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    destination = root / "docs/implementation/spec-033/T055-pbo-profile.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
