# Gate 5 Operational API Contract

Prefix: `/api/safety`

The router has no default live configuration. Without an injected
`LiveSafetyGate`, every endpoint fails closed with HTTP 503.

## Endpoints

| Method | Path | Request | Domain call | Success response |
|---|---|---|---|---|
| POST | `/kill` | `SafetyKillRequest` | `request_kill` | `SafetyActionResponse` |
| POST | `/kill/confirm` | `SafetyKillConfirmRequest` | `confirm_kill` | `SafetyActionResponse` |
| POST | `/kill/reset` | `SafetyKillResetRequest` | `reset_kill` | `SafetyActionResponse(status="RESET")` |
| POST | `/halt/rolling/reset` | `SafetyRollingHaltResetRequest` | `reset_rolling_halt` | `SafetyActionResponse(status="RESET")` |
| GET | `/status` | none | `status` | `SafetyStatusResponse` |

Domain validation/reset refusals map to HTTP 409 with the domain message.
Malformed request bodies remain FastAPI/Pydantic HTTP 422 responses.

The route owns no broker client, database path, credential, or numeric limit.
It does not import or modify `reports/api/routes/capital_gate.py`.

