import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def app_data_dir(home: Path | None = None, platform: str | None = None) -> Path:
    home = home or Path.home()
    platform = platform or sys.platform
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Finviz Tracker"
    if platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Finviz Tracker"
    return home / ".local" / "share" / "finviz-tracker"


def prepare_data_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("logs", "scans", "debug"):
        (path / name).mkdir(exist_ok=True, mode=0o700)
    return path


def migrate_history(source: Path, destination: Path) -> bool:
    database = source / "finviz_history.db"
    target = destination / "finviz_history.db"
    if target.exists() or not database.is_file() or source.resolve() == destination.resolve():
        return False
    prepare_data_dir(destination)
    temporary = destination / "migration.db.tmp"
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as original:
            tables = {row[0] for row in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"runs", "filter_runs", "filter_results", "ticker_results"} <= tables:
                raise ValueError("This folder does not contain a Finviz Tracker history database.")
            with closing(sqlite3.connect(temporary)) as backup:
                original.backup(backup)
                if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("The source history database failed its integrity check.")
        for snapshot in (source / "scans").glob("*/*.json"):
            output = destination / "scans" / snapshot.parent.name / snapshot.name
            output.parent.mkdir(exist_ok=True)
            if not output.exists():
                shutil.copy2(snapshot, output)
        os.link(temporary, target)
        return True
    finally:
        temporary.unlink(missing_ok=True)
