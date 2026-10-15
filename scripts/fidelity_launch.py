"""057 Q140: credentials only in a child environment; no broker/session logic."""
import hashlib
import hmac
import re
import os
import subprocess
import sys

CREDENTIAL_NAMES = ('FIDELITY_LIVE_USERNAME', 'FIDELITY_LIVE_PASSWORD',
                    'FIDELITY_LIVE_TOTP', 'FIDELITY_LIVE_ACCOUNT', 'FIDELITY_LIVE_FP_KEY')
SERVICE = 'qmb-fidelity-live'


class LaunchRefused(RuntimeError):
    """Fixed-message refusal; never carry a backend exception or credential."""


def credentials_for(*, platform=None, environ=None, get_password=None):
    """Read exactly five names, with native vault only on Windows."""
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    try:
        if platform == 'win32':
            if get_password is None:
                # Select the native vault explicitly; never load third-party/plaintext backends.
                from keyring.backends.Windows import WinVaultKeyring
                get_password = WinVaultKeyring().get_password
            credentials = {name: get_password(SERVICE, name) for name in CREDENTIAL_NAMES}
        elif platform == 'linux':
            credentials = {name: environ.get(name) for name in CREDENTIAL_NAMES}
        else:
            raise LaunchRefused('Unsupported host')
    except Exception:
        raise LaunchRefused('Credential launch refused') from None
    missing = next((name for name, value in credentials.items()
                    if not isinstance(value, str) or not value.strip()), None)
    if missing is not None:
        raise LaunchRefused('Missing credential: ' + missing)
    if not re.fullmatch('[0-9a-f]{64}',credentials['FIDELITY_LIVE_FP_KEY']):
        raise LaunchRefused('Invalid credential: FIDELITY_LIVE_FP_KEY')
    return credentials


def fingerprint(**kwargs):
    credentials=credentials_for(**kwargs)
    return hmac.new(bytes.fromhex(credentials['FIDELITY_LIVE_FP_KEY']),credentials['FIDELITY_LIVE_ACCOUNT'].encode(),hashlib.sha256).hexdigest()


def launch(command, *, platform=None, environ=None, get_password=None, spawn=None):
    """Return child status; values travel only through the child's env."""
    if not command or any(not isinstance(arg,str) for arg in command): raise LaunchRefused('Command required')
    environ=os.environ if environ is None else environ
    spawn=subprocess.run if spawn is None else spawn
    credentials=credentials_for(platform=platform,environ=environ,get_password=get_password)
    try:
        child_env = dict(environ)
        child_env.update(credentials)
        result = spawn(list(command), env=child_env, check=False)
        return result.returncode
    except Exception:
        raise LaunchRefused('Credential launch refused') from None


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args==['--fingerprint']:
        try:
            print(fingerprint()); return 0
        except LaunchRefused as exc:
            print(str(exc),file=sys.stderr); return 2
    if len(args) < 2 or args[0] != '--':
        print('Usage: fidelity_launch.py -- <command...>', file=sys.stderr)
        return 2
    try:
        return launch(args[1:])
    except LaunchRefused as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
