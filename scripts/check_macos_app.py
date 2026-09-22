"""Verify packaged launch, ZIP relocation, DMG installation, and retained history."""

import json
import argparse
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
DATA = Path.home() / "Library/Application Support/Finviz Tracker"
SESSION = DATA / "session.json"
REPORT = DATA / "logs/verification.json"
OUTPUT = ROOT / "data/packaging-test"


def saved_runs():
    connection = sqlite3.connect((DATA / "finviz_history.db").as_uri() + "?mode=ro", uri=True)
    try:
        return [tuple(row) for row in connection.execute("SELECT id, run_date, status FROM runs ORDER BY id")]
    finally:
        connection.close()


def verify(bundle, scan, forbid_source=False):
    previous_report = REPORT.stat().st_mtime_ns if REPORT.exists() else 0
    arguments = ["open", "-n"]
    if forbid_source:
        arguments += ["--env", f"FINVIZ_VERIFY_FORBID_PATH={ROOT}"]
    arguments += [str(bundle), "--args", "--verify-scan" if scan else "--verify"]
    subprocess.run(arguments, check=True, cwd="/")
    deadline = time.monotonic() + 660
    port = None
    while time.monotonic() < deadline:
        if SESSION.exists():
            try:
                port = urlsplit(json.loads(SESSION.read_text())["url"]).port
            except (ValueError, KeyError):
                pass
        if REPORT.exists() and REPORT.stat().st_mtime_ns != previous_report and not SESSION.exists():
            report = json.loads(REPORT.read_text())
            assert report["passed"], report
            assert report["packaged"] and report["windowed_without_terminal"], report
            assert port is not None, "Did not observe backend startup"
            with socket.socket() as connection:
                connection.settimeout(1)
                assert connection.connect_ex(("127.0.0.1", port)) != 0, "Backend port remains open after exit"
            report["backend_port_closed_after_exit"] = True
            subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
            return report
        time.sleep(.1)
    raise TimeoutError("Packaged app did not finish verification; inspect Application Support logs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-scan", action="store_true", help="Check launch/relocation without adding a live scan")
    args = parser.parse_args()
    if SESSION.exists():
        raise SystemExit("Close Finviz Tracker before running this check.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = saved_runs() if (DATA / "finviz_history.db").exists() else []
    first = verify(ROOT / "dist/Finviz Tracker.app", not args.no_scan)
    after = saved_runs()
    assert after[:len(before)] == before, "Existing history changed"
    assert len(after) == len(before) + (0 if args.no_scan else 1), "Unexpected scan count"
    if not args.no_scan:
        assert first["scan"]["outcome"] == "complete"
    with tempfile.TemporaryDirectory(prefix="finviz-distribution-") as folder:
        subprocess.run(["ditto", "-x", "-k", str(ROOT / "dist/Finviz Tracker-macOS-arm64.zip"), folder], check=True)
        reopened = verify(Path(folder) / "Finviz Tracker.app", False, forbid_source=True)
        assert Path(reopened["resources"]).is_relative_to(Path(folder).resolve())
        assert saved_runs() == after, "Reopening changed saved history"
        assert reopened["run_id"] == first["run_id"]
        assert reopened["stocks"] == first["stocks"]
    with tempfile.TemporaryDirectory(prefix="finviz-dmg-install-") as folder:
        root = Path(folder)
        mount = root / "mounted"
        install = root / "Applications"
        mount.mkdir()
        install.mkdir()
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-quiet",
                        "-mountpoint", str(mount), str(ROOT / "dist/Finviz Tracker-macOS-arm64.dmg")], check=True)
        try:
            installed_app = install / "Finviz Tracker.app"
            subprocess.run(["ditto", str(mount / "Finviz Tracker.app"), str(installed_app)], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", str(mount)], check=True)
        installed = verify(installed_app, False, forbid_source=True)
        assert Path(installed["resources"]).is_relative_to(install.resolve())
        assert saved_runs() == after, "DMG installation changed saved history"
        assert installed["run_id"] == first["run_id"]
        assert installed["stocks"] == first["stocks"]
    result = {"passed": True, "existing_runs_preserved": len(before), "scan": first,
              "reopened_from_zip": reopened, "installed_from_dmg": installed}
    (OUTPUT / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
