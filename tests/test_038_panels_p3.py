"""EXAMPLE — NOT A RESULT. 038 T032: stamp the actual synthetic input before figures."""
from datetime import datetime, timezone
import hashlib
import inspect
from pathlib import Path
import socket

import numpy as np
import pandas as pd
import pytest
import context  # noqa: F401
import scratch_aapl_correlations as single
import scratch_multiticker_collinearity as multi
from mutation_support_019 import killed

CLOCK = lambda: datetime(2026, 10, 20, 1, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("T032 real socket forbidden")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def run(module, monkeypatch, capsys, tmp_path):
    source = tmp_path / "synthetic.csv"
    n = 100
    rng = np.random.default_rng(381)
    pd.DataFrame({"Date": pd.bdate_range('2026-05-01', periods=n),
        "Ticker": ['AAPL'] * n, "Close": 100 * np.exp(np.cumsum(rng.normal(0, .01, n))),
        "Volume": rng.integers(1000, 2000, n)}).to_csv(source, index=False)
    monkeypatch.setattr(module, "CSV_PATH", source)
    main = module.main if module is single else module.run_analysis
    assert 'clock' in inspect.signature(main).parameters, "T032 INJECTED CLOCK MISSING"
    main(clock=CLOCK, root=tmp_path)
    return capsys.readouterr().out.splitlines(), source


@pytest.mark.parametrize("module", [single, multi], ids=['single', 'multi'])
def test_selected_input_hash_and_run_time_precede_metrics(module, monkeypatch, capsys, tmp_path):
    lines, source = run(module, monkeypatch, capsys, tmp_path)
    expected = "source: synthetic.csv sha256=" + hashlib.sha256(source.read_bytes()).hexdigest()
    assert lines[0] == expected, "T032 ACTUAL INPUT HASH"
    assert "run (UTC): 2026-10-20 01:30:00Z" in lines, "T032 RUN DATE"
    assert "trial: none (descriptive, not a trial)" in lines
    assert any(line.startswith("Limitations (Rule 16):") for line in lines), "T032 LIMITATIONS"
    first = next(i for i, line in enumerate(lines) if 'CORRELATION AUDIT' in line or 'INDEPENDENT VERIFICATION' in line)
    assert lines.index("run (UTC): 2026-10-20 01:30:00Z") < first, "T032 ORDER"


@pytest.mark.parametrize("module", [single, multi], ids=['single', 'multi'])
def test_changed_input_during_stamp_refuses_before_metrics(module, monkeypatch, capsys, tmp_path):
    import disclosure
    assert hasattr(module, 'provenance_stamp'), "T032 STAMP MISSING"
    def drift(source, **kwargs):
        stamp = disclosure.provenance_stamp(source, **kwargs)
        stamp[0] = 'source: other.csv sha256=' + '0' * 64
        return stamp
    monkeypatch.setattr(module, "provenance_stamp", drift)
    with pytest.raises(ValueError, match="input changed"):
        run(module, monkeypatch, capsys, tmp_path)
    assert not capsys.readouterr().out, "T032 STALE STAMP PRINTED"


@pytest.mark.parametrize("module", [single, multi], ids=['single', 'multi'])
def test_different_file_digest_mutant_is_caught(module, monkeypatch, capsys, tmp_path):
    old = 'stamp = provenance_stamp(CSV_PATH, root=root, clock=clock)'
    new = 'stamp = provenance_stamp(CSV_PATH.with_name("other.csv"), root=root, clock=clock)'
    (tmp_path / 'other.csv').write_text('different synthetic bytes', encoding='utf-8')
    def oracle():
        capsys.readouterr()
        try:
            lines, source = run(module, monkeypatch, capsys, tmp_path)
        except ValueError:
            lines, source = ['refused'], tmp_path / 'synthetic.csv'
        expected = 'source: synthetic.csv sha256=' + hashlib.sha256(source.read_bytes()).hexdigest()
        assert lines[0] == expected, "T032 ACTUAL INPUT HASH"
    killed(module, old, new, oracle)
