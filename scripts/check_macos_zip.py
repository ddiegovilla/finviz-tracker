import argparse
import hashlib
from pathlib import Path
import stat
import subprocess
import tempfile

from check_macos_bundle import inspect_bundle


def manifest(bundle):
    entries = {}
    for path in bundle.rglob("*"):
        name = str(path.relative_to(bundle))
        if path.is_symlink():
            entries[name] = ("symlink", str(path.readlink()))
        elif path.is_file():
            entries[name] = ("file", stat.S_IMODE(path.stat().st_mode), hashlib.sha256(path.read_bytes()).hexdigest())
    return entries


def verify_zip(bundle, archive):
    with tempfile.TemporaryDirectory(prefix="finviz-zip-audit-") as directory:
        subprocess.run(["ditto", "-x", "-k", str(archive), directory], check=True)
        extracted = Path(directory) / bundle.name
        assert manifest(bundle) == manifest(extracted), "ZIP changed file content, permissions or symlinks"
        inspect_bundle(extracted)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(extracted)], check=True)
        print("ZIP extraction verified: file bytes, executable permissions, symlinks, architecture, dependencies and signature match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    verify_zip(args.bundle, args.archive)
