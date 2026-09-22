"""Local-only HTTP server for the dashboard; never starts or alters scans."""

import argparse
import json
import logging
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .config import ROOT
from .dashboard_data import DashboardData


ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/logic.js": ("logic.js", "text/javascript; charset=utf-8"),
    "/desktop.js": ("desktop.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}


def make_handler(database: Path):
    class DashboardHandler(BaseHTTPRequestHandler):
        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status: int, value: dict) -> None:
            self.respond(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            host = self.headers.get("Host", "").split(":", 1)[0]
            if host not in ("127.0.0.1", "localhost"):
                self.send_json(403, {"error": "This dashboard is available on localhost only."})
                return
            parsed = urlsplit(self.path)
            if parsed.path in ASSETS:
                filename, content_type = ASSETS[parsed.path]
                self.respond(200, (ROOT / "frontend" / filename).read_bytes(), content_type)
                return
            if parsed.path not in ("/api/overview", "/api/ticker"):
                self.send_json(404, {"error": "Not found"})
                return
            query = parse_qs(parsed.query)
            selected_date = query.get("date", [None])[0]
            reader = None
            try:
                if not database.exists():
                    self.send_json(200, {"empty": True, "message": "No scans yet. Run your first scan to begin."})
                    return
                reader = DashboardData(database)
                if parsed.path == "/api/ticker":
                    ticker = query.get("ticker", [""])[0]
                    if not ticker or len(ticker) > 32:
                        raise ValueError("A valid ticker is required")
                    result = reader.ticker_detail(ticker, selected_date)
                else:
                    result = reader.overview(selected_date)
                self.send_json(200, result)
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except LookupError as error:
                self.send_json(404, {"error": str(error)})
            except sqlite3.Error:
                logging.exception("Dashboard could not read scan database")
                self.send_json(503, {"error": "Scan data is temporarily unavailable. Try refreshing again."})
            finally:
                if reader:
                    reader.close()

    return DashboardHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the local Finviz dashboard using the existing scan database.")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "finviz_history.db")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.db)) as server:
        logging.info("Dashboard: http://127.0.0.1:%s · reading %s · scans remain manual", args.port, args.db)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.info("Dashboard stopped")


if __name__ == "__main__":
    main()
