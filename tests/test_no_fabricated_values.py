"""No fabricated evidence reaches the terminal (spec 018: findings 45, 46, 47, 58).

Three layers: API responses from two generated panels, route source by AST
(covering branches no fixture reaches), and terminal component source.
"""

from __future__ import annotations

import ast
import re
import unittest
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from api_fixtures import FIXTURE_A, FIXTURE_B, fixture_client, synthetic_panel
from reports.api.schemas import CapitalGateItem

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_DIR = REPO_ROOT / "reports" / "api" / "routes"
WEB_SRC = REPO_ROOT / "reports" / "web" / "src"

# Text stating a value nothing computed; each generalizes deleted literals.
FABRICATED_TEXT = {
    # 47: "301 passed", "All 301 unit tests passing", "CORE: 311/311 PASS"
    "test count": re.compile(r"\b\d+(?:\s*/\s*\d+)?\s+(?:unit\s+)?(?:tests?\s+)?pass", re.IGNORECASE),
    # 45: a p-value stated in prose rather than a numeric field
    "p-value figure": re.compile(r"\bp(?:-value)?\s*[=<>]\s*0?\.\d", re.IGNORECASE),
    # 46: "P(Up) = 54.2%", "Logit Score = +0.17", rules presented as a model's output
    "forecast probability": re.compile(r"\bP\((?:Up|Down)\)\s*=\s*\d"),
    "model score": re.compile(r"\bLogit\s+Score\s*=\s*[+-]?\d", re.IGNORECASE),
    "model attribution": re.compile(
        r"\b(?:ML|machine[- ]learning)\s+model\b|\bmodel\s+(?:predicts|detects|advises|flags)\b",
        re.IGNORECASE,
    ),
}
UI_ONLY_TEXT = {
    "literal gate total": re.compile(r"\bof\s+\d+\s+Gates\b", re.IGNORECASE),  # 47
    "p-value field": re.compile(r"\b(?:p_value|passed_screening|screening_alpha)\b"),  # 45
}
# Model wording in other screens' tutoring is finding 49, not checked here.
RUNDOWN_COMPONENTS = ("components/layout/MLRundownPane.tsx", "components/layout/Header.tsx")
FABRICATED_FIELDS = {"p_value", "alpha", "screening_alpha", "passed_screening"}  # 45
EVIDENCE_STATES = {"passed", "failed", "stale"}  # 47: each needs evidence no route has yet

ENDPOINTS = (
    "/api/diagnostics/significance?ticker=AAPL",
    "/api/diagnostics/significance?ticker=NVDA",
    "/api/capital_gate/status",
    "/api/ml/rundown?ticker=AAPL",
)
# Numbers identical for any market data by construction, each with its reason.
STRUCTURAL_NUMBERS = {
    "gates[].gate_number": "a gate's ordinal position",
    "insights[].rank": "a reading's display position",
}


def leaves(value, path=""):
    """(path, scalar) for every leaf of a JSON body; list positions become `[]`."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item, f"{path}[]")
    else:
        yield path, value


def numbers(body) -> dict[str, tuple]:
    """The sorted numeric values at each leaf path, booleans excluded."""
    found = defaultdict(set)
    for path, leaf in leaves(body):
        if isinstance(leaf, (int, float)) and not isinstance(leaf, bool):
            found[path].add(leaf)
    return {path: tuple(sorted(values)) for path, values in found.items()}


def route_violations(source: str, filename: str) -> list[str]:
    """Literal fabricated values in a route module, found by walking its AST."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for name, pattern in FABRICATED_TEXT.items():
                if pattern.search(node.value):
                    found.append(f"{filename}:{node.lineno} {name}: {node.value[:60]!r}")
        elif isinstance(node, ast.keyword) and isinstance(node.value, ast.Constant):
            literal = node.value.value
            if node.arg in FABRICATED_FIELDS or (node.arg == "status" and literal in EVIDENCE_STATES):
                found.append(f"{filename}:{node.value.lineno} literal {node.arg}={literal!r}")
    return found


def ui_violations(source: str, filename: str) -> list[str]:
    """Lines of a terminal component that state a fabricated value."""
    patterns = {**FABRICATED_TEXT, **UI_ONLY_TEXT}
    del patterns["p-value figure"]  # on-screen p-value tutoring is finding 49; fields are checked
    if not filename.endswith(RUNDOWN_COMPONENTS):
        del patterns["model attribution"]
    return [
        f"{filename}:{number} {name}: {line.strip()[:60]!r}"
        for number, line in enumerate(source.splitlines(), start=1)
        for name, pattern in patterns.items()
        if pattern.search(line)
    ]


class FabricatedResponseTests(unittest.TestCase):
    def setUp(self):
        self.bodies = []
        for fixture in (FIXTURE_A, FIXTURE_B):
            client = fixture_client(self, synthetic_panel(**fixture))
            responses = {endpoint: client.get(endpoint) for endpoint in ENDPOINTS}
            for endpoint, response in responses.items():
                self.assertEqual(response.status_code, 200, endpoint)
            self.bodies.append({endpoint: r.json() for endpoint, r in responses.items()})

    def test_no_response_text_states_a_fabricated_value(self):
        for bodies in self.bodies:
            for endpoint, body in bodies.items():
                for path, leaf in leaves(body):
                    for name, pattern in FABRICATED_TEXT.items():
                        if isinstance(leaf, str):
                            self.assertIsNone(pattern.search(leaf), f"{endpoint} {path}: {name} in {leaf!r}")

    def test_no_number_stays_fixed_when_every_price_changes(self):
        """A number identical for two unrelated panels was not computed from them."""
        first, second = ({e: numbers(body) for e, body in bodies.items()} for bodies in self.bodies)
        for endpoint in ENDPOINTS:
            shared = (first[endpoint].keys() & second[endpoint].keys()) - STRUCTURAL_NUMBERS.keys()
            for path in sorted(shared):
                self.assertNotEqual(
                    first[endpoint][path], second[endpoint][path],
                    f"{endpoint} {path} is {first[endpoint][path]} for both panels",
                )

    def test_structural_allowlist_names_real_fields(self):
        seen = {path for bodies in self.bodies for body in bodies.values() for path, _ in leaves(body)}
        self.assertLessEqual(STRUCTURAL_NUMBERS.keys(), seen)


class GateEvidenceSchemaTests(unittest.TestCase):
    def test_only_unknown_may_stand_without_evidence(self):
        gate = {"gate_number": 1, "title": "t", "description": "d", "details": "r"}
        for status in sorted(EVIDENCE_STATES):
            with self.assertRaises(ValidationError):
                CapitalGateItem(status=status, **gate)
            CapitalGateItem(status=status, evidence="a recorded artifact", **gate)
        self.assertIsNone(CapitalGateItem(status="unknown", **gate).evidence)


class FabricatedSourceTests(unittest.TestCase):
    def test_route_modules_carry_no_fabricated_literal(self):
        found = []
        for path in sorted(ROUTES_DIR.glob("*.py")):
            found += route_violations(path.read_text(encoding="utf-8"), path.name)
        self.assertEqual(found, [])

    def test_terminal_components_carry_no_fabricated_literal(self):
        found = []
        for path in sorted(WEB_SRC.rglob("*.ts*")):
            found += ui_violations(path.read_text(encoding="utf-8"), path.relative_to(WEB_SRC).as_posix())
        self.assertEqual(found, [])

    def test_each_check_catches_a_literal_spec_018_deleted(self):
        # Verbatim from the pre-018 sources, so the patterns cannot drift from them.
        routes = {
            "ml_rundown.py": 'x = f"P(Down) = 53.8% | Logit Score = -0.15 | Forward Horizon = 1 bar"',
            "diagnostics.py": "Entry(p_value=0.084, alpha=0.10, passed_screening=True)",
            "significance.py": 's = "PASSED (p < 0.10)"',
            "capital_gate.py": 'Gate(status="passed", evidence="301 passed in pytest suite")',
            "rundown.py": 's = f"The ML model predicts a positive directional bias for {ticker}"',
        }
        for filename, source in routes.items():
            self.assertTrue(route_violations(source, filename), filename)
        components = {
            "components/layout/Header.tsx": "<span>CORE: 311/311 PASS</span>",
            "components/views/CapitalGateView.tsx": "{passedCount} of 5 Gates Passed",
            "components/views/FeatureDiagnosticsView.tsx": "{entry.p_value.toFixed(3)}",
            "components/layout/MLRundownPane.tsx": "ML Model Decision Rundown",
        }
        for filename, source in components.items():
            self.assertTrue(ui_violations(source, filename), filename)


if __name__ == "__main__":
    unittest.main()
