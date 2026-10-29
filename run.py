"""Offline configuration check and tests for the two HA packages.

    python run.py check       # HA config check: count alone, then count + control
    python run.py test        # all tests in tests/ (extra pytest args are passed on)

Use a Python 3.14 environment set up from tests/requirements-test.txt.
No live Home Assistant call and no climate service call is made here.
"""

import shutil
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))
import winstubs  # noqa: E402,F401


def check():
    from homeassistant.scripts import check_config

    failed = 0
    for files in (("adaptive_cooling_lt2.yaml",),
                  ("adaptive_cooling_lt2.yaml", "adaptive_cooling_lt2_control.yaml")):
        print("== " + " + ".join(files), flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "homeassistant"
            packages = cfg / "packages"
            packages.mkdir(parents=True)
            shutil.copy(HERE / "tests" / "fixtures" / "configuration.yaml", cfg / "configuration.yaml")
            for name in files:
                shutil.copy(HERE / "packages" / name, packages / name)
            sys.argv = [sys.argv[0], "--config", str(cfg)]
            failed |= check_config.run([])
    return failed


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "check":
        sys.exit(check())
    if command == "test":
        import pytest

        if sys.platform == "win32":
            import pytest_socket

            pytest_socket.disable_socket = lambda *args, **kwargs: None
            pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None
        sys.exit(pytest.main(["-p", "no:cacheprovider", str(HERE / "tests"), *sys.argv[2:]]))
    print(__doc__)
    sys.exit(2)
