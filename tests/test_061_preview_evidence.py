"""061/057 operator evidence: synthetic records only, no broker or credentials."""
import json
from copy import deepcopy

import pytest
import context
from allocation_policy import policy_evidence
from gate_checklist import fidelity_preview


def example(day='2026-10-19'):
    return dict(session=day, profile='live_fidelity', mode='preview', clean=True,
                challenge=False, place_calls=0, account_fingerprint='a'*64,
                pin_sha='b'*40, totp_step=True, allocation=policy_evidence(),
                library={'version':'0.2.2','sha256':'f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15'},
                settled_cash={'amount':200.,'as_of':day+'T14:00:00+00:00'},
                previews=[{'qty':1.,'conf_num':'FIXTURE'}], holdings_match=True,
                csv_sha256='c'*64, actions=[{'outcome':'PREVIEW'}],
                unwanted='DO NOT COPY ARBITRARY INPUT FIELDS')


def test_five_distinct_sessions_feed_existing_typed_gate(tmp_path):
    from fidelity_preview_evidence import record_session
    gate=tmp_path/'gate.json'; gate.write_text('{"items":{}}')
    for day in range(19,24):
        source=tmp_path/'session.json'; source.write_text(json.dumps(example(f'2026-10-{day}')))
        record_session(source, root=tmp_path, gate=gate, record=True)
    entry=json.loads(gate.read_text())['items']['6']
    assert fidelity_preview(entry,tmp_path)[0], '061 EVIDENCE feeds the existing typed gate'
    assert 'DO NOT COPY' not in ''.join(p.read_text() for p in (tmp_path/'docs').rglob('*.json'))
    before=gate.read_bytes()
    record_session(source,root=tmp_path,gate=gate,record=True)
    assert gate.read_bytes()==before, '061 EVIDENCE same-day rerun is idempotent'


@pytest.mark.parametrize('update', [
    {'mode':'submit'}, {'clean':False}, {'challenge':True}, {'place_calls':1},
    {'allocation':{}}, {'session':'2026-10-18'}, {'holdings_match':False},
    {'actions':[{'outcome':'DENIED'}]}, {'settled_cash':{'amount':200.,'as_of':'2026-10-19T14:00:00'}},
    {'settled_cash':{'amount':200.,'as_of':'2026-10-20T14:00:00+00:00'}},
    {'previews':[]}, {'pin_sha':'not-a-pin'},
])
def test_refusals_never_write_evidence(tmp_path,update):
    from fidelity_preview_evidence import record_session
    source=tmp_path/'session.json'; source.write_text(json.dumps(example()|update))
    gate=tmp_path/'gate.json'; gate.write_text('{"items":{}}')
    with pytest.raises(ValueError): record_session(source,root=tmp_path,gate=gate,record=True)
    assert gate.read_text()=='{"items":{}}' and not (tmp_path/'docs').exists()


def test_preflight_no_writes_and_changed_day_refuses(tmp_path):
    from fidelity_preview_evidence import record_session
    source=tmp_path/'session.json'; source.write_text(json.dumps(example()))
    gate=tmp_path/'gate.json'; gate.write_text('{"items":{}}')
    record_session(source,root=tmp_path,gate=gate,record=False)
    assert not (tmp_path/'docs').exists()
    record_session(source,root=tmp_path,gate=gate,record=True)
    row=example(); row['totp_step']=False; source.write_text(json.dumps(row))
    with pytest.raises(ValueError,match='immutable'): record_session(source,root=tmp_path,gate=gate,record=True)
