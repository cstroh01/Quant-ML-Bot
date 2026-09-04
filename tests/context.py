"""Put scripts/ on the import path so the tests can import its modules.

The scripts are written to be run directly, which means Python adds their own
directory to sys.path for them. The test runner starts from the project root
instead, so it has to arrange the same thing explicitly.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
