"""038 T054: the real API serves definitions without an unearned readiness phase."""
import pytest
from fastapi.testclient import TestClient
from reports.api.main import app
from reports.api.routes import capital_gate

DISCLOSURE = "Verification evidence only; this historical five-gate dashboard does not establish overall capital readiness. Consult SCOPE-V1 section 11.3 for the seven-item capital checklist."

@pytest.mark.parametrize("status", ["unknown", "passed", "failed", "stale"])
def test_t054_actual_api_never_infers_overall_capital_readiness(monkeypatch, status):
    monkeypatch.setattr(capital_gate, "_gate3_status", lambda: {"status": status, "details": "EXAMPLE — NOT A RESULT", "evidence": "reports/artifacts/capital_gate/gate3/synthetic.json"})
    response = TestClient(app).get("/api/capital_gate/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_readiness"] == DISCLOSURE, "T054 UNSUPPORTED READINESS"
    assert payload["gates"][2]["status"] == status, "T054 PRESERVE GATE3 STATUS"

def test_t054_actual_api_serves_all_existing_gate_definitions(monkeypatch):
    monkeypatch.setattr(capital_gate, "_gate3_status", lambda: {"status": "unknown", "details": "EXAMPLE — NOT A RESULT"})
    payload = TestClient(app).get("/api/capital_gate/status").json()
    gates = payload["gates"]
    assert [row["gate_number"] for row in gates] == [1, 2, 3, 4, 5], "T054 SERVED DEFINITIONS"
    assert all(row["title"] and row["description"] for row in gates), "T054 NONEMPTY DEFINITIONS"
    assert all(row["status"] == "unknown" for row in gates), "T054 UNKNOWN WITHOUT EVIDENCE"
