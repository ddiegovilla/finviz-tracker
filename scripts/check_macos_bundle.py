import argparse
import json
from pathlib import Path
import plistlib
import stat

from macholib.MachO import MachO


MAGICS = {bytes.fromhex(value) for value in ("cffaedfe", "cefaedfe", "feedfacf", "feedface", "cafebabe", "bebafeca", "cafebabf", "bfbafeca")}
LOAD_COMMANDS = {0xc, 0x80000018, 0x8000001f, 0x80000023}


def inspect_bundle(bundle):
    bundle = Path(bundle).resolve()
    with (bundle / "Contents/Info.plist").open("rb") as source:
        metadata = plistlib.load(source)
    assert metadata["CFBundlePackageType"] == "APPL", "Invalid bundle type"
    assert metadata["CFBundleIdentifier"] == "local.finviz.tracker", "Invalid bundle identifier"
    assert metadata["LSMinimumSystemVersion"] == "14.0", "Expected macOS 14 target"
    executable = bundle / "Contents/MacOS" / metadata["CFBundleExecutable"]
    assert executable.parent == bundle / "Contents/MacOS" and executable.is_file(), "Missing bundle executable"
    assert executable.stat().st_mode & stat.S_IXUSR, "Missing executable permission"
    assert (bundle / "Contents/Resources").is_dir(), "Missing Resources"
    records = {}
    for path in (bundle / "Contents").rglob("*"):
        if path.is_symlink():
            assert path.exists() and path.resolve().is_relative_to(bundle), f"Broken or external symlink: {path}"
            continue
        if not path.is_file():
            continue
        with path.open("rb") as binary:
            magic = binary.read(4)
        if magic not in MAGICS:
            continue
        headers = [header for header in MachO(str(path)).headers
                   if header.header.cputype == 16777228 and header.header.cpusubtype & 0xffffff in (0, 1)]
        assert headers, f"No arm64 slice: {path}"
        record = {"dependencies": [], "rpaths": [], "minimums": []}
        for header in headers:
            for command, detail, payload in header.commands:
                if command.cmd in LOAD_COMMANDS:
                    record["dependencies"].append(payload.split(b"\0", 1)[0].decode())
                if command.cmd == 0x8000001c:
                    record["rpaths"].append(payload.split(b"\0", 1)[0].decode())
                if command.cmd == 0x32:
                    assert detail.platform == 1, f"Not a macOS binary: {path}"
                version = detail.minos if command.cmd == 0x32 else detail.version if command.cmd == 0x24 else None
                if version is not None:
                    record["minimums"].append((version >> 16, version >> 8 & 255, version & 255))
        records[path] = record
    assert executable in records, "Executable is not arm64 Mach-O"

    def expand(value, owner):
        return Path(value.replace("@loader_path", str(owner.parent)).replace("@executable_path", str(executable.parent))).resolve()

    for path, record in records.items():
        rpaths = [expand(value, path) for value in record["rpaths"]]
        rpaths += [expand(value, executable) for value in records[executable]["rpaths"]]
        for directory in rpaths:
            assert directory.is_relative_to(bundle), f"External RPATH: {path}: {directory}"
        for dependency in record["dependencies"]:
            if dependency.startswith(("/usr/lib/", "/System/Library/")):
                continue
            candidates = [directory / dependency.removeprefix("@rpath/") for directory in rpaths] if dependency.startswith("@rpath/") else [expand(dependency, path)]
            assert any(candidate.exists() and candidate.resolve().is_relative_to(bundle) for candidate in candidates), f"Missing/external dependency: {path}: {dependency}"
    minimum = max(version for record in records.values() for version in record["minimums"])
    assert minimum <= (14, 0, 0), f"Native minimum {minimum} exceeds macOS 14; use portable python.org Python"
    for resource in ("frontend/index.html", "frontend/app.js", "frontend/desktop.js", "config/filters.json", "certifi/cacert.pem", "tzdata/zoneinfo/UTC", "collect_macos_diagnostics.sh"):
        assert (bundle / "Contents/Resources" / resource).is_file(), f"Missing resource: {resource}"
    return {"version": metadata["CFBundleShortVersionString"], "native_binaries": len(records), "architecture": "arm64", "executable_mode": oct(stat.S_IMODE(executable.stat().st_mode)), "newest_native_minimum": ".".join(map(str, minimum)), "target": "macOS 14+", "dependencies": "All non-system load commands resolve inside the bundle"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    print(json.dumps(inspect_bundle(parser.parse_args().bundle), indent=2))
