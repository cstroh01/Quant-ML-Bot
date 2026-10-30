"""057 T017 / D-5a: supervised Fidelity login probe. Rule 7: read every line before merge.

For entitlement diagnosis only, started by Camden. What this module guarantees:

- **No order path.** It never builds ``FidelityLive`` or reads an arming record. It removes the
  client's order objects before login and refuses any request whose path names an order.
- **At most two probes, ever.** The cap counts persisted files. A marker is pushed durably before
  login, so a crashed probe still counts; if that push fails, no login happens.
- **Only while already halted.** It refuses on KILL and refuses unless HALTED exists, and it never
  writes, clears or reads past HALTED. An unlatched account can therefore never meet an unlatched
  challenge here (D-6, FR-005).
- **Its record is not evidence.** It writes only ``login-probes/``, never ``attempts/`` or
  ``preview-sessions/``, with ``mode: probe`` and neither ``clean`` nor ``challenge``, so neither
  the preview evidence recorder nor the gate checklist can accept it.
- **Fixed text only.** Output is one fixed line; a record holding a credential string is blanked.
"""
import argparse
from datetime import datetime, time, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / 'scripts', ROOT / 'exec'):
    if str(directory) not in sys.path: sys.path.insert(0, str(directory))
from data import trading_days
from fidelity_live import LibraryBroker, SecurityChallenge, account_hmac
from mode_config import load_profiles
from ops_runtime import atomic_write

NY = ZoneInfo('America/New_York')
MAX_PROBES = 2
LIBRARY = {'version': '0.2.2', 'sha256': 'f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15'}
_SYMBOL = re.compile(r'[A-Z][A-Z0-9.*]{0,11}')
PASSED, REFUSED, BLANKED = 'passed', 'refused', 'sensitive output refused'


class ProbeRefused(RuntimeError):
    """Fixed-message refusal before any login."""


def probes_used(state) -> int:
    """Every persisted probe-* file counts, whatever it holds; an unreadable marker is still a login."""
    folder = Path(state) / 'login-probes'
    return sum(1 for p in folder.iterdir() if p.name.startswith(('probe-', '.probe-'))) if folder.is_dir() else 0


def preflight(*, state, profile, pin, now, environ) -> str:
    """Return the session label, or refuse with fixed text. Reads no credential beyond the fingerprint's two."""
    try:
        state = Path(state)
        local = now.astimezone(NY)
        day = local.date()
        if now.utcoffset() is None or trading_days(day, day) != [day] or not time(9, 35) <= local.time() < time(16):
            raise ValueError
        if not re.fullmatch('[0-9a-f]{40}', pin) or (state / 'KILL').exists() or not (state / 'HALTED').is_file():
            raise ValueError
        if json.loads((state / 'host-ready.json').read_text(encoding='utf-8')) != {'schema': 1, 'profile': 'live_fidelity'}:
            raise ValueError
        if profile.name != 'live_fidelity' or profile.mode != 'LIVE' or profile.broker != 'fidelity':
            raise ValueError
        if account_hmac(environ.get('FIDELITY_LIVE_ACCOUNT'), environ.get('FIDELITY_LIVE_FP_KEY')) != profile.account_fingerprint:
            raise ValueError
        if probes_used(state) >= MAX_PROBES:
            raise ValueError
    except Exception:
        raise ProbeRefused('Login probe refused before login') from None
    return str(day)


def _read_only(broker) -> None:
    """Take every order object off the client and refuse an order-shaped request at the HTTP layer."""
    client = broker._client
    client.equity_orders = None
    client.order_status = None
    def refuse_orders(request):
        path = request.url.path.lower()
        if 'order' in path or 'equity' in path:
            raise SecurityChallenge('Fidelity order path refused')
    client._http.event_hooks['request'].insert(0, refuse_orders)


def _strings(value):
    if isinstance(value, str): return [value]
    if isinstance(value, dict): return [s for k, v in value.items() for s in [k, *_strings(v)]]
    if isinstance(value, list): return [s for v in value for s in _strings(v)]
    return []


def _attempt(broker_factory, environ, now, record) -> None:
    """Fill ``record``; every failure is its stage and exception type only."""
    stage, broker = 'broker', None
    try:
        broker = broker_factory()
        _read_only(broker)
        stage = 'login'
        broker.login(environ['FIDELITY_LIVE_USERNAME'], environ['FIDELITY_LIVE_PASSWORD'], environ['FIDELITY_LIVE_TOTP'])
        record['entitlement_check'] = 'passed'
        stage = 'settled_cash'
        cash = broker.settled_cash(now)
        record['settled_cash'] = {'amount': float(cash['amount']), 'as_of': str(cash['as_of'])}
        stage = 'positions'
        held = broker.positions()
        record['positions'] = {'count': len(held), 'symbols': sorted(s if _SYMBOL.fullmatch(s) else '*' for s in held)}
        record['status'] = PASSED
    except Exception as exc:
        record['failure'] = {'stage': stage, 'kind': type(exc).__name__}
    try:
        record['login'] = broker.diagnostic() if broker is not None else None
    except Exception:
        record['login'] = None


def run(*, state, profile, pin, now, environ, persist, broker_factory=None) -> str:
    """One probe. Returns the status; raises ProbeRefused before login when no login is allowed."""
    session = preflight(state=state, profile=profile, pin=pin, now=now, environ=environ)
    state = Path(state)
    path = state / 'login-probes' / f'probe-{probes_used(state) + 1}.json'
    record = {'kind': 'fidelity_login_probe', 'mode': 'probe', 'status': 'started', 'session': session,
              'started_at': now.isoformat(), 'profile': profile.name, 'pin_sha': pin, 'library': LIBRARY,
              'place_calls': 0, 'previews': []}
    atomic_write(path, json.dumps(record, sort_keys=True, allow_nan=False))
    try:
        persist()
    except Exception:
        raise ProbeRefused('Login probe marker not durable; no login') from None
    factory = broker_factory or (lambda: LibraryBroker('FIDELITY_LIVE_ACCOUNT', environ))
    record['status'] = REFUSED
    _attempt(factory, environ, now, record)
    secrets = [environ.get(name, '') for name in profile.credential_refs]
    if any(secret and any(secret in s for s in _strings(record)) for secret in secrets):
        record = {'kind': record['kind'], 'mode': 'probe', 'status': BLANKED, 'session': session,
                  'profile': profile.name, 'pin_sha': pin, 'place_calls': 0, 'previews': []}
    atomic_write(path, json.dumps(record, sort_keys=True, allow_nan=False))
    return record['status']


def _persist(state):
    """Push the ops-state checkout; the child gets no Fidelity credential."""
    env = {k: v for k, v in os.environ.items() if not k.startswith('FIDELITY_') and k != 'QMB_FIDELITY_PROFILES_JSON'}
    def persist():
        subprocess.run(['bash', str(ROOT / 'ops/persist_state.sh'), str(Path(state).parent), 'fidelity-login-probe'],
                       cwd=ROOT, env=env, check=True, capture_output=True)
    return persist


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='057 D-5a supervised login probe')
    parser.add_argument('--pin', required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        profile = load_profiles(json.loads(args.profiles.read_text(encoding='utf-8')))['live_fidelity']
        status = run(state=args.state, profile=profile, pin=args.pin, now=datetime.now(timezone.utc),
                     environ=os.environ, persist=_persist(args.state))
    except Exception:
        print('Login probe refused before login', file=sys.stderr)
        return 2
    if status != PASSED:
        print('Login probe failed; read the persisted record', file=sys.stderr)
        return 2
    print('Login probe passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
