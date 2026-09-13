"""Isolated in-memory source mutants: semantic failure, never import failure."""
import hashlib
from pathlib import Path
from unittest.mock import patch


def killed(module, old, new, oracle):
    path = Path(module.__file__)
    source = path.read_text()
    digest = hashlib.sha256(path.read_bytes()).digest()
    assert source.count(old) == 1, 'mutation must hit exactly one location'
    oracle()  # unmutated control must pass
    caught = False
    with patch.dict(module.__dict__):
        exec(compile(source.replace(old, new), str(path), 'exec'), module.__dict__)
        try:
            oracle()
        except AssertionError:
            caught = True
    assert hashlib.sha256(path.read_bytes()).digest() == digest
    assert caught, 'semantic mutant survived'
