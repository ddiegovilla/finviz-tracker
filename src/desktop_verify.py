import json
import logging
import ctypes
import os
from pathlib import Path
import sys
import time
import threading

from .app_paths import resource_root
from .dashboard_data import DashboardData


def verify_window(window, manager, directory, scan):
    report = {"packaged": bool(getattr(sys, "frozen", False)), "resources": str(resource_root()),
              "database": str(manager.database), "real_scan_requested": scan,
              "windowed_without_terminal": not any(
                  stream is not None and stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr))}

    def wait_for(expression, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if window.run_js(expression):
                return
            time.sleep(.2)
        raise AssertionError(f"Native WebKit timed out: {expression}")

    def screenshot():
        from AppKit import NSBitmapImageRep
        from PyObjCTools import AppHelper
        from webview.platforms.cocoa import BrowserView
        finished = threading.Event()

        def capture():
            def save(image, error):
                try:
                    if image is not None:
                        bitmap = NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
                        bitmap.representationUsingType_properties_(4, {}).writeToFile_atomically_(str(directory / "logs/native-window.png"), True)
                finally:
                    finished.set()
            BrowserView.instances[window.uid].webview.takeSnapshotWithConfiguration_completionHandler_(None, save)
        AppHelper.callAfter(capture)
        finished.wait(10)

    try:
        if report["packaged"]:
            import certifi
            bundle = resource_root().parent.parent.resolve()
            report["python_paths"] = list(sys.path)
            assert all(Path(path).resolve().is_relative_to(bundle) for path in sys.path), sys.path
            report["certificates"] = certifi.where()
            assert Path(certifi.where()).resolve().is_relative_to(bundle)
            loader = ctypes.CDLL(None)
            loader._dyld_image_count.restype = ctypes.c_uint32
            loader._dyld_get_image_name.argtypes = [ctypes.c_uint32]
            loader._dyld_get_image_name.restype = ctypes.c_char_p
            images = [loader._dyld_get_image_name(index).decode() for index in range(loader._dyld_image_count())]
            external = [path for path in images if not path.startswith(("/System/", "/usr/lib/")) and not Path(path).resolve().is_relative_to(bundle)]
            assert not external, f"External native libraries: {external}"
            report["native_images_checked"] = len(images)
            report["external_native_libraries"] = external
            report["forbidden_source_directory"] = os.environ.get("FINVIZ_VERIFY_FORBID_PATH")
        assert window.events.loaded.wait(30), "Native window failed to load"
        wait_for('document.querySelector("#app") && !document.querySelector("#app").hidden')
        wait_for('!document.querySelector("#desktop-controls").hidden')
        report["native_dashboard_loaded"] = True
        screenshot()
        if scan:
            revision = manager.status()["revision"]
            window.run_js('document.querySelector("#run-scan").click()')
            deadline = time.monotonic() + 600
            while manager.status()["revision"] == revision and time.monotonic() < deadline:
                time.sleep(.5)
            assert manager.status()["outcome"] == "complete", manager.status()
            report["scan"] = manager.status()
        if manager.database.exists():
            reader = DashboardData(manager.database)
            try:
                overview = reader.overview()
                report["run_id"] = overview["snapshot"]["run"]["id"]
                report["stocks"] = len(overview["snapshot"]["stocks"])
                report["collected_dates"] = overview["dates"]
                report["run_count"] = reader.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            finally:
                reader.close()
            wait_for(f'document.querySelector("#app").dataset.runId === "{report["run_id"]}"')
            wait_for('document.querySelector("[data-ticker]") !== null')
            ticker = window.run_js('document.querySelector("[data-ticker]").dataset.ticker')
            reader = DashboardData(manager.database)
            try:
                expected_days = len(reader.ticker_detail(ticker)["observations"])
            finally:
                reader.close()
            window.run_js('document.querySelector("[data-ticker]").click()')
            wait_for(f'document.querySelectorAll(".history-table tbody tr").length === {expected_days}')
            report["history_rows"] = window.run_js('document.querySelectorAll(".history-table tbody tr").length')
            window.run_js('document.querySelector("#close-detail").click(); location.hash="screener"')
            wait_for('!document.querySelector("#screener-view").hidden')
            report["screener_loaded"] = True
        report["passed"] = True
    except Exception as error:
        logging.exception("Packaged window verification failed")
        report["passed"] = False
        report["error"] = str(error)
    finally:
        manager.shutdown()
        (directory / "logs" / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        window.destroy()
