"""055 T004 workflow KILL: fake command; no broker, credentials or orders."""
import json
from pathlib import Path
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
import context
from ops_runner import run_once, preview_once


@pytest.mark.parametrize('runner',[run_once,preview_once])
def test_file_kill_stops_command_queues_one_profile_incident_and_keeps_marker(tmp_path,runner):
    (tmp_path/'KILL').write_text('operator review required')
    marker=tmp_path/'child-ran'
    args=dict(profile='paper_small', command=[sys.executable,'-c',f'from pathlib import Path; Path({str(marker)!r}).touch()'],
              now=datetime(2026,10,19,8,tzinfo=ZoneInfo('America/New_York')),strategy_version='fake@abc')
    first=runner(tmp_path,**args)
    assert first['status']=='killed', '055 FILE KILL must refuse the command'
    assert first['new_incidents']==1 and not marker.exists()
    again=runner(tmp_path,**args)
    assert again['new_incidents']==0, '055 FILE KILL duplicate incident suppressed'
    incident=json.loads((tmp_path/'ops/incidents.jsonl').read_text())
    assert incident['kind']=='halt' and incident['profile']=='paper_small'
    outbox=list((tmp_path/'ops/outbox').glob('*.json'))
    assert len(outbox)==1 and json.loads(outbox[0].read_text())['kind']=='incident'
    assert (tmp_path/'KILL').read_text()=='operator review required'
    assert not (tmp_path/'leases').exists()
    assert not (tmp_path/'ops/runs.jsonl').exists() and not (tmp_path/'ops/previews.jsonl').exists()
