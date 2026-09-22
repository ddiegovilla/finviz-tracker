import fcntl
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import secrets
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from .app_paths import app_data_dir, migrate_history, prepare_data_dir, resource_root
from .desktop_scan import ScanManager
from .desktop_server import desktop_handler


def show_error(message):
    from AppKit import NSAlert, NSApplication
    NSApplication.sharedApplication()
    alert = NSAlert.alloc().init()
    alert.setMessageText_("Finviz Tracker")
    alert.setInformativeText_(message)
    alert.addButtonWithTitle_("Close")
    alert.runModal()


def main():
    import webview
    from tzlocal import get_localzone_name
    from webview.menu import Menu, MenuAction

    parser = argparse.ArgumentParser(description="Finviz Tracker desktop application")
    parser.add_argument("--verify", action="store_true", help="Run packaged window checks and exit")
    parser.add_argument("--verify-scan", action="store_true", help="Include a real scan in verification")
    parser.add_argument("--import-history", type=Path, help="Import a data folder only if desktop history does not exist")
    args = parser.parse_args()

    directory = prepare_data_dir(app_data_dir())
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        directory / "logs" / "app.log", maxBytes=2_000_000, backupCount=3)],
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    lock = (directory / "app.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        show_error("Finviz Tracker is already running. Use its existing window or Dock icon.")
        lock.close()
        return
    manager = server = None
    endpoint = directory / "session.json"
    try:
        if args.import_history:
            migrate_history(args.import_history, directory)
        elif not getattr(sys, "frozen", False):
            migrate_history(resource_root() / "data", directory)
        manager = ScanManager(directory, get_localzone_name())
        token = secrets.token_urlsafe(32)
        server = ThreadingHTTPServer(("127.0.0.1", 0), desktop_handler(manager, token))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, name="dashboard-server", daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/?session={token}"
        for attempt in range(50):
            try:
                from urllib.error import HTTPError
                try:
                    urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=1).close()
                except HTTPError as response:
                    if response.code != 403:
                        raise
                break
            except OSError:
                if attempt == 49:
                    raise RuntimeError("The local dashboard could not start.")
                time.sleep(.1)
        with endpoint.open("w") as output:
            endpoint.chmod(0o600)
            json.dump({"url": url, "database": str(manager.database)}, output)
        logging.info("Desktop ready on port %s; data: %s; resources: %s", server.server_port, directory, resource_root())
        window = webview.create_window("Finviz Tracker", url, width=1280, height=850, min_size=(820, 600))

        def import_history():
            selected = window.create_file_dialog(webview.FileDialog.FOLDER)
            if not selected:
                return
            try:
                with manager.guard:
                    if manager.running:
                        message = "Wait for the scan to finish before importing history."
                    elif migrate_history(Path(selected[0]), directory):
                        message = "History imported. The original files are unchanged."
                    else:
                        message = "Nothing imported. History already exists here, or the selected folder has no finviz_history.db. Existing history is never overwritten."
                window.run_js(f"window.desktopMessage({json.dumps(message)})")
            except Exception:
                logging.exception("History import failed")
                window.run_js('window.desktopMessage("Import failed. The original history is unchanged. See application logs.")')

        def close_window():
            if manager.running:
                from AppKit import NSAlert, NSAlertFirstButtonReturn
                alert = NSAlert.alloc().init()
                alert.setMessageText_("Stop scan and quit?")
                alert.setInformativeText_("Completed filters are saved. The current request may take a few seconds to stop.")
                alert.addButtonWithTitle_("Stop Scan and Quit")
                alert.addButtonWithTitle_("Keep Open")
                if alert.runModal() != NSAlertFirstButtonReturn:
                    return False
            manager.shutdown()
            server.shutdown()
            endpoint.unlink(missing_ok=True)
            logging.info("Desktop shut down cleanly")
            return True

        window.events.closing += close_window
        menu = [Menu("File", [MenuAction("Run Scan", lambda: window.run_js("window.runDesktopScan()")),
                              MenuAction("Import History…", import_history)]),
                Menu("View", [MenuAction("Dashboard", lambda: window.run_js('location.hash="dashboard"')),
                              MenuAction("Screener", lambda: window.run_js('location.hash="screener"')),
                              MenuAction("Refresh Saved Data", lambda: window.run_js('document.querySelector("#refresh").click()'))])]
        verification = None
        if args.verify or args.verify_scan:
            from .desktop_verify import verify_window
            verification = lambda: verify_window(window, manager, directory, args.verify_scan)
        webview.start(func=verification, menu=menu, private_mode=True)
    except Exception:
        logging.exception("Desktop startup failed")
        show_error(f"The app could not start. Your history is safe. Details are in {directory / 'logs' / 'app.log'}.")
    finally:
        if manager:
            manager.shutdown()
        if server:
            server.shutdown()
            server.server_close()
        endpoint.unlink(missing_ok=True)
        logging.info("Desktop resources released")
        lock.close()


if __name__ == "__main__":
    main()
