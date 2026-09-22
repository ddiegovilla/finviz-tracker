from pathlib import Path
import plistlib

import pytest

pytest.importorskip("macholib", reason="Bundle audit tests require optional requirements-build.txt")
from scripts.check_macos_bundle import inspect_bundle


@pytest.fixture
def incomplete_bundle(tmp_path):
    bundle = tmp_path / "Finviz Tracker.app"
    (bundle / "Contents/MacOS").mkdir(parents=True)
    (bundle / "Contents/Resources").mkdir()
    metadata = {"CFBundlePackageType": "APPL", "CFBundleIdentifier": "local.finviz.tracker",
                "LSMinimumSystemVersion": "14.0", "CFBundleExecutable": "Finviz Tracker"}
    (bundle / "Contents/Info.plist").write_bytes(plistlib.dumps(metadata))
    executable = bundle / "Contents/MacOS/Finviz Tracker"
    executable.write_bytes(b"not a native binary")
    executable.chmod(0o755)
    return bundle


def test_bundle_rejects_missing_executable(incomplete_bundle):
    (incomplete_bundle / "Contents/MacOS/Finviz Tracker").unlink()
    with pytest.raises(AssertionError, match="Missing bundle executable"):
        inspect_bundle(incomplete_bundle)


def test_bundle_rejects_lost_executable_permissions(incomplete_bundle):
    (incomplete_bundle / "Contents/MacOS/Finviz Tracker").chmod(0o644)
    with pytest.raises(AssertionError, match="Missing executable permission"):
        inspect_bundle(incomplete_bundle)


def test_bundle_rejects_external_symlink(incomplete_bundle):
    (incomplete_bundle / "Contents/Resources/external").symlink_to(Path.home())
    with pytest.raises(AssertionError, match="Broken or external symlink"):
        inspect_bundle(incomplete_bundle)


def test_bundle_rejects_broken_symlink(incomplete_bundle):
    (incomplete_bundle / "Contents/Resources/broken").symlink_to("missing")
    with pytest.raises(AssertionError, match="Broken or external symlink"):
        inspect_bundle(incomplete_bundle)


def test_bundle_rejects_non_native_executable(incomplete_bundle):
    with pytest.raises(AssertionError, match="Executable is not arm64 Mach-O"):
        inspect_bundle(incomplete_bundle)


def test_bundle_rejects_unsupported_target(incomplete_bundle):
    path = incomplete_bundle / "Contents/Info.plist"
    metadata = plistlib.loads(path.read_bytes())
    metadata["LSMinimumSystemVersion"] = "26.0"
    path.write_bytes(plistlib.dumps(metadata))
    with pytest.raises(AssertionError, match="Expected macOS 14 target"):
        inspect_bundle(incomplete_bundle)
