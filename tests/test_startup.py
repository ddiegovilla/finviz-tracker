import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent


def run_startup(home, code, extra_env=None, arguments=()):
    environment = {**os.environ, "HOME": str(home), **(extra_env or {})}
    return subprocess.run([sys.executable, "-c", "from src.startup import initialize_startup_log; initialize_startup_log(); " + code, *arguments],
                          cwd=ROOT, env=environment, capture_output=True, text=True)


def test_early_import_failure_is_logged(tmp_path):
    result = run_startup(tmp_path, "import finviz_intentionally_missing_module")
    assert result.returncode != 0
    log = tmp_path / "Library/Application Support/Finviz Tracker/logs/startup.log"
    assert "ModuleNotFoundError" in log.read_text()
    assert "architecture=" in log.read_text()
    assert log.stat().st_mode & 0o777 == 0o600


def test_startup_log_rotates(tmp_path):
    log = tmp_path / "Library/Application Support/Finviz Tracker/logs/startup.log"
    log.parent.mkdir(parents=True)
    log.write_text("x" * 2_000_001)
    assert run_startup(tmp_path, "print('ready')").returncode == 0
    assert log.with_name("startup.previous.log").stat().st_size == 2_000_001
    assert log.stat().st_size < 2000


def test_verification_rejects_source_repository_access(tmp_path):
    result = run_startup(tmp_path, "open('README.md')", {"FINVIZ_VERIFY_FORBID_PATH": str(ROOT)}, ("--verify",))
    assert result.returncode != 0
    log = tmp_path / "Library/Application Support/Finviz Tracker/logs/startup.log"
    assert "Verification forbids source access" in log.read_text()


def test_normal_launch_ignores_verification_guard(tmp_path):
    assert run_startup(tmp_path, "open('README.md').close()", {"FINVIZ_VERIFY_FORBID_PATH": str(ROOT)}).returncode == 0
