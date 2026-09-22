"""Verify the mounted release image against the signed build."""

import argparse
from pathlib import Path
import plistlib
import subprocess
import tempfile

from check_macos_bundle import inspect_bundle
from check_macos_zip import manifest


def verify_dmg(bundle: Path, image: Path) -> None:
    bundle = bundle.resolve()
    image = image.resolve()
    subprocess.run(["hdiutil", "verify", str(image)], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix="finviz-dmg-audit-") as directory:
        mount = Path(directory) / "volume"
        mount.mkdir()
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-quiet",
                        "-mountpoint", str(mount), str(image)], check=True)
        try:
            details = subprocess.run(["diskutil", "info", "-plist", str(mount)],
                                     check=True, capture_output=True)
            volume_name = plistlib.loads(details.stdout).get("VolumeName")
            assert volume_name == "Finviz Tracker", f"Wrong DMG volume name: {volume_name}"
            actual = mount / bundle.name
            visible = {path.name for path in mount.iterdir() if not path.name.startswith(".")}
            assert visible == {bundle.name, "Applications"}, f"Unexpected DMG contents: {visible}"
            assert (mount / ".DS_Store").is_file(), "Finder icon layout missing"
            assert (mount / "Applications").is_symlink(), "Missing Applications shortcut"
            assert (mount / "Applications").readlink() == Path("/Applications"), "Wrong Applications shortcut"
            assert manifest(bundle) == manifest(actual), "DMG changed app bytes, modes, or symlinks"
            inspect_bundle(actual)
            subprocess.run(["codesign", "--verify", "--deep", "--strict", str(actual)], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", str(mount)], check=True)
    print("DMG verified: volume name, Finder layout, Applications shortcut, exact app bytes/modes/symlinks, arm64, dependencies, and signature.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("image", type=Path)
    arguments = parser.parse_args()
    verify_dmg(arguments.bundle, arguments.image)
