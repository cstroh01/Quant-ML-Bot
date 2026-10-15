"""057 D-4: load audited SDK modules without its eager research/CLI imports."""
import importlib
import hashlib
from importlib import metadata
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


AUDITED = {'_http': '51502aceca7966919a53fcbfc29fd0801a96206f6b19382f2c62feb19eeeda2b',
 'auth/security_context': 'f896800f6760dd933cd114baa066123a979d7a1c509687dd20434f6aed1e5cf0',
 'auth/session': '57f707ddbd3586e8efbc18c7a408f81ef9e506e3a33d8ed2f5f45613abf645e5',
 'exceptions': '64bfcdc0d51abb876934d7e354f66bb0d7f51efe1a8193d12350376dcee4e5d0',
 'models/_parsers': '203d18130c2880c668cdbf07c9c28cf9e2a2d61b3a3392807bb6ea9614364243',
 'models/balance': 'ecd9c828eb67415660d06059e27419bbc10cadb2e01c8da2e840f06c7cf434c3',
 'models/equity_order': 'b6d44f908681c5aec43e88efa21b87e61785a589f158a1bc33ad4d89927da171',
 'models/order': '9c274309a4725b6693152cf4e0f3feb082b98a629dee646119c84ba40d68b5a5',
 'models/position': 'c43274c61130f0212de322e189be6a159be1bc5b11a7babffaaf762e96b9941d',
 'models/security_context': '9308817aa9293923695ad48dc7c55eb9e4432d5b045b8ff6c8aab55ffeff049f',
 'orders/equity': '37d751d98c54aa2f8740fbefe4f7fa6c3b6d02f594707642799dca6f39a2618e',
 'orders/status': 'dab835b10fb6100d1acfb82760de4f7e1f537aa4d184d258b7d09cace3b8657b',
 'portfolio/balances': 'cc9222464924ff690b54efb9a271f7ad42f56e72a969007caba9b82a338c24ee',
 'portfolio/positions': 'e9cdd75a62fc0a4b866aa64fc234dcb57e3bd49824c5b9577e3ef242504830db',
 'retry': 'ec3b823e45ca089c7600721df48dfea4aaf4e36c1f661e3baa9adb4fad8cb4d8'}

def client():
    dist = metadata.distribution('fidelity-trader-api')
    if dist.version != '0.2.2':
        raise RuntimeError('audited SDK version required')
    root = Path(dist.locate_file('fidelity_trader'))
    if any(hashlib.sha256((root / (name + '.py')).read_bytes()).hexdigest() != digest
           for name, digest in AUDITED.items()):
        raise RuntimeError('audited SDK source hash mismatch')
    for name in list(sys.modules):
        if name.startswith(('fidelity_trader.research', 'fidelity_trader.streaming',
                            'fidelity_trader.cli', 'fidelity_trader.credentials')):
            raise RuntimeError('unauthorized SDK module already imported')
    for suffix in ('', '.auth', '.models', '.portfolio', '.orders'):
        name = 'fidelity_trader' + suffix
        if name in sys.modules and not getattr(sys.modules[name], '_qmb_namespace', False):
            raise RuntimeError('SDK namespace already initialized')
        package = ModuleType(name)
        package.__path__ = [str(root.joinpath(*suffix.strip('.').split('.'))) if suffix else str(root)]
        package._qmb_namespace = True
        sys.modules[name] = package
    def load(name):
        return importlib.import_module('fidelity_trader.' + name)
    http = load('_http').create_atp_session(max_retries=0)
    return SimpleNamespace(
        _http=http, login=load('auth.session').AuthSession(http, 'https://digital.fidelity.com', 'https://ecaap.fidelity.com').login,
        equity_orders=load('orders.equity').EquityOrderAPI(http, live_trading=True),
        order_status=load('orders.status').OrderStatusAPI(http),
        positions=load('portfolio.positions').PositionsAPI(http),
        balances=load('portfolio.balances').BalancesAPI(http),
        security_context=load('auth.security_context').SecurityContextAPI(http))
