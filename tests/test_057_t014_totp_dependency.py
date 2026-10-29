"""057 T014 / D-4a: the hash-locked Fidelity host must carry pyotp for the SDK's 1201 TOTP step.

Offline only: reads the lock, the audited SDK source digest and the workflow templates.
"""
from pathlib import Path
import re
import sys
import pytest
import context  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'exec'))
import fidelity_sdk  # noqa: E402
LOCK = ROOT / 'requirements-fidelity-host.txt'
PYOTP = 'pyotp==2.10.0 --hash=sha256:1df2f6a1bcc3bb0716172a5215ddc2f8c7c7fd26a13df9927d52e1746934836c'
# auth/session.py of fidelity-trader-api 0.2.2: on status 1201 _resolve_totp_code does `import pyotp`.
SESSION_NEEDING_PYOTP = '57f707ddbd3586e8efbc18c7a408f81ef9e506e3a33d8ed2f5f45613abf645e5'
INSTALL = 'pip install --require-hashes --only-binary=:all: -r qmb/requirements-fidelity-host.txt'
LINE = re.compile(r'([A-Za-z0-9_.-]+)==([0-9][0-9A-Za-z.]*) --hash=sha256:[0-9a-f]{64}')


def requirements():
    return [line.strip() for line in LOCK.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def test_lock_pins_pyotp_by_exact_wheel_hash():
    assert requirements().count(PYOTP) == 1


def test_no_other_pyotp_line():
    assert [r for r in requirements() if r.lower().replace('_', '-').startswith('pyotp')] == [PYOTP]


def test_audited_session_is_the_one_that_imports_pyotp():
    # If the audited auth/session ever changes, this coupling must be re-read, not silently kept.
    assert fidelity_sdk.AUDITED['auth/session'] == SESSION_NEEDING_PYOTP
    assert PYOTP in requirements()


@pytest.mark.parametrize('line', requirements())
def test_every_lock_line_is_one_exact_pin_with_one_hash_and_no_marker(line):
    assert LINE.fullmatch(line), line


def test_lock_names_are_unique():
    names = [LINE.fullmatch(r).group(1).lower().replace('_', '-') for r in requirements()]
    assert len(names) == len(set(names))


@pytest.mark.parametrize('workflow', ['fidelity-preview.yml', 'fidelity-live.yml'])
def test_workflows_install_the_host_lock_hash_checked(workflow):
    text = (ROOT / 'ops' / 'workflows' / workflow).read_text(encoding='utf-8')
    assert [line.strip() for line in text.splitlines() if 'requirements-fidelity-host' in line] == [INSTALL]
