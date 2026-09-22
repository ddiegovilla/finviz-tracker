import hmac
import json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

from .web import make_handler


def desktop_handler(manager, token):
    class DesktopHandler(make_handler(manager.database)):
        def log_message(self, format, *args):
            return

        def authorized(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
                value = cookie.get("finviz_session")
                return value is not None and hmac.compare_digest(value.value, token)
            except Exception:
                return False

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.valid_host():
                self.send_json(403, {"error": "Local application requests only."})
                return
            parsed = urlsplit(self.path)
            supplied = parse_qs(parsed.query).get("session", [""])[0]
            if parsed.path == "/" and supplied and hmac.compare_digest(supplied, token):
                self.send_response(303)
                self.send_header("Set-Cookie", f"finviz_session={token}; HttpOnly; SameSite=Strict; Path=/")
                self.send_header("Location", "/")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                return
            if not self.authorized():
                self.send_json(403, {"error": "Open the dashboard from Finviz Tracker."})
                return
            if parsed.path == "/api/desktop":
                try:
                    self.send_json(200, {**manager.status(), "csrf": token})
                except Exception:
                    self.send_json(503, {"error": "Unable to read history. Check application logs."})
                return
            super().do_GET()

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if (not self.valid_host() or not self.authorized()
                    or self.headers.get("Origin") != origin
                    or not hmac.compare_digest(self.headers.get("X-Finviz-Token", ""), token)):
                self.send_json(403, {"error": "Invalid application request."})
                return
            if self.path != "/api/scan":
                self.send_json(404, {"error": "Not found"})
                return
            started = manager.start()
            self.send_json(202 if started else 409, {"started": started})

    return DesktopHandler
