"""066 FR-002: the restore-drill workflow template is dispatch-only, read-only and fails closed.

EXAMPLE — NOT A RESULT. Static contract checks of the template text; nothing runs.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_template_is_dispatch_only_and_read_only():
    text = (ROOT / "ops" / "workflows" / "restore-drill.yml").read_text(encoding="utf-8")
    body = "\n".join(line.split("#", 1)[0] for line in text.splitlines())  # comments may name what is absent
    assert "workflow_dispatch:" in body and "schedule:" not in body and "concurrency:" not in body
    assert "permissions:\n  contents: read\n  actions: read\n" in body and ": write" not in body
    for forbidden in ("secrets.", "persist_state", "git push", "issue create", "--submit", "exec/"):
        assert forbidden not in body, forbidden
    uses = [line.split("uses:", 1)[1].strip() for line in body.splitlines() if "uses:" in line]
    assert uses and all(len(u.split("@", 1)[1]) == 40 for u in uses), uses
    assert body.count("persist-credentials: false") == 2
    assert "scripts/restore_drill.py" in body
    # The writer check precedes every checkout and fails closed; ops-state is pinned and re-checked.
    assert text.index("Refuse while a state writer") < text.index("actions/checkout")
    assert "2>/dev/null" not in body and "|| echo 0" not in body and "could not find any workflows named" in body
    assert 'echo "::error::cannot check $wf: $active"; exit 1' in body
    # gh's actual not-installed text (seen 2026-10-24 for fidelity-live.yml): HTTP 404,
    # "workflow fidelity-live.yml not found on the default branch".
    assert '*"not found on the default branch"*' in body
    assert "if: ${{ always() && env.STATE_SHA != '' }}" in body  # no recheck before a snapshot exists
    assert "ref: ${{ env.STATE_SHA }}" in body and "ops-state moved; rerun the drill" in body
    for needle in ("select(.expired | not)", "sort_by(.created_at) | last",
                   '"fidelity-live-state-"', '"fidelity-state-"', '"[\\"state-$PROFILE-\\"]"'):
        assert needle in body, needle
