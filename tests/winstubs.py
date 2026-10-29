"""Allow the HA config checker to import on Windows (HA does not run there)."""

import sys
import types

if sys.platform == "win32":
    if "fcntl" not in sys.modules:
        fcntl = types.ModuleType("fcntl")
        fcntl.LOCK_EX = 2
        fcntl.LOCK_NB = 4
        fcntl.LOCK_UN = 8
        fcntl.LOCK_SH = 1
        fcntl.flock = lambda *args, **kwargs: None
        fcntl.fcntl = lambda *args, **kwargs: 0
        sys.modules["fcntl"] = fcntl
    if "resource" not in sys.modules:
        resource = types.ModuleType("resource")
        resource.RLIMIT_NOFILE = 7
        resource.getrlimit = lambda *args: (1024, 4096)
        resource.setrlimit = lambda *args: None
        sys.modules["resource"] = resource
