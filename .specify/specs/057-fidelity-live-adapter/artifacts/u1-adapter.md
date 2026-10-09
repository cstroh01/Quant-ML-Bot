# 057 U1 evidence and fixes (exec/, Rule 7 reviewed lane)

Fakes only: no Fidelity call, credential, library import or account data. EXAMPLE — NOT A RESULT.

## Draft as pushed (128fabc)
10 contract tests on a fake broker passed (LIVE-only, arming-gated, preview→record→place,
timeout → `SubmissionUnknown`, challenge halts, one login, credentials redacted).

## Fixes (Codex coordination 2026-10-08 23:25 CT; findings listed on #102)
Red on 128fabc, 12 new cases:
```
FAILED tests/test_057_fidelity_live.py::test_every_post_place_error_is_outcome_unknown_and_redacted[error0]
FAILED tests/test_057_fidelity_live.py::test_every_post_place_error_is_outcome_unknown_and_redacted[error1]
FAILED tests/test_057_fidelity_live.py::test_every_post_place_error_is_outcome_unknown_and_redacted[error2]
FAILED tests/test_057_fidelity_live.py::test_every_post_place_error_is_outcome_unknown_and_redacted[error3]
FAILED tests/test_057_fidelity_live.py::test_every_post_place_error_is_outcome_unknown_and_redacted[error4]
FAILED tests/test_057_fidelity_live.py::test_other_broker_errors_are_redacted[preview]
FAILED tests/test_057_fidelity_live.py::test_other_broker_errors_are_redacted[status]
FAILED tests/test_057_fidelity_live.py::test_other_broker_errors_are_redacted[positions]
FAILED tests/test_057_fidelity_live.py::test_retry_of_a_known_order_returns_it_without_a_second_preview_or_place
FAILED tests/test_057_fidelity_live.py::test_retry_after_unknown_with_no_broker_record_never_places_again
FAILED tests/test_057_fidelity_live.py::test_client_id_reused_for_a_different_order_refuses_before_any_call
FAILED tests/test_057_fidelity_live.py::test_challenge_at_placement_says_the_outcome_is_unknown
12 failed, 10 passed in 0.36s
```
- Any exception once `place` is called → `SubmissionUnknown`. Before, only a timeout counted; a
  connection reset was reported as a known failure, inviting a duplicate retry. `LibraryBroker.place`
  builds the order before the send, so validation errors still mean "nothing sent".
- `_call` wraps preview, status and positions: challenge → halt; anything else → type name only,
  no chained cause. Placement errors carry only the type name.
- Same client id: a recorded id never previews or places again. Fidelity knows the order → the
  recorded confirmation number is returned. No record → `SubmissionUnknown` ("reconcile, never
  resubmit"). Different symbol/side/qty under the same id → refuse before any call.
- Challenge at placement halts and says the outcome is unknown.

## Rule 12
`python tests/mutation/run_057_u1_fix_mutants.py` → 7/7 killed. 22 tests pass.
