"""Rule 12 driver for spec 033 T062 (queue Q33): the offline Gate 3 evidence generator.

Run: python tests/mutation/run_033_t062_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
control, witness-carrying-failure and byte-identity checks against `scripts/generate_gate3_evidence.py`.
The T056-T058 tests carry bare asserts, so their witness is the reason code or status their
assertion message prints.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/generate_gate3_evidence.py"
TEST = "tests/test_033_gate3.py"
DECLARATION = ".specify/specs/058-edge-research-program/declaration.json"
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("DSR threshold exclusive", "dsr_value < DSR_THRESHOLD", "dsr_value <= DSR_THRESHOLD", "'failed' != 'passed'"),
    ("t threshold exclusive", "t_value < T_THRESHOLD", "t_value <= T_THRESHOLD", "'failed' != 'passed'"),
    ("family N never gates", 'if family is not None and family.get("within_cap"):', "if False:", "'passed'"),
    ("PBO at any S", ' or pbo.get("S") != PBO_S', "", "pbo_undefined"),
    ("statistics from another matrix accepted",
     'if isinstance(stat, dict) and stat.get("matrix_hash") not in (None, matrix_hash):', "if False:", "unknown"),
    ("artifact id derived from content", "uuid.uuid4().hex",
     "hashlib.sha256(json.dumps(e, sort_keys=True, default=str).encode()).hexdigest()[:32]", "FR-039"),
    ("lifetime DSR unchecked under family N",
     'if dsr is not None and not (isinstance(lifetime, dict) and _finite(lifetime.get("value"))):', "if False:",
     "Q33 LIFETIME"),
    ("non-finite values kept", "    return _json_safe(artifact)", "    return artifact", "Q33 STRICT JSON"),
    ("ledger head not checked", "CURRENT = ((\"ledger_head_hash\", \"ledger_changed\"), ", "CURRENT = (", "stale"),
    ("unknown evidence re-assessed", 'if artifact.get("status") not in ("passed", "failed"):', "if False:",
     "Q33 UNKNOWN STAYS"),
    ("undeterminable input treated as current", "if any(current.get(key) is None for key, _ in CURRENT):", "if False:",
     "Q33 MATRIX UNKNOWN"),
    ("gate3 policy unchecked", "if not isinstance(policy, dict) or not needed <= policy.keys():", "if False:",
     "Q33 POLICY"),
    ("command exits zero when not current",
     'return 0 if verdict["status"] in ("passed", "failed") else 1', "return 0", "is False"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, DECLARATION
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "reports", "tests/context.py", "tests/spec033_support.py",
                                                  DECLARATION, TEST), 63, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
