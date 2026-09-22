import faulthandler
import os
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


_crash_log = None


def initialize_startup_log():
    global _crash_log
    directory = Path.home() / "Library/Application Support/Finviz Tracker/logs"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "startup.log"
    if path.exists() and path.stat().st_size > 2_000_000:
        path.replace(directory / "startup.previous.log")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    _crash_log = os.fdopen(descriptor, "a", buffering=1)
    os.dup2(_crash_log.fileno(), 2)
    sys.stderr = _crash_log
    if sys.stdout is None:
        sys.stdout = _crash_log
    faulthandler.enable(file=_crash_log, all_threads=True)
    previous_hook = sys.excepthook

    def exception_hook(exception_type, exception, trace):
        traceback.print_exception(exception_type, exception, trace, file=_crash_log)
        _crash_log.flush()
        previous_hook(exception_type, exception, trace)

    sys.excepthook = exception_hook
    startup_message(f"\n{datetime.now(timezone.utc).isoformat()} PID={os.getpid()} "
                    f"architecture={platform.machine()} macOS={platform.mac_ver()[0]} "
                    f"Python={sys.version.split()[0]} executable={sys.executable} "
                    f"resources={getattr(sys, '_MEIPASS', '')}")
    forbidden = os.environ.get("FINVIZ_VERIFY_FORBID_PATH")
    if forbidden and "--verify" in sys.argv:
        forbidden = Path(forbidden).resolve()

        def audit(event, arguments):
            if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(arguments[0])).resolve()
                if path.is_relative_to(forbidden):
                    startup_message(f"Forbidden source access: {path}")
                    raise PermissionError(f"Verification forbids source access: {path}")

        sys.addaudithook(audit)
        startup_message(f"Source access guard enabled: {forbidden}")


def startup_message(message):
    if _crash_log is not None:
        _crash_log.write(message + "\n")
