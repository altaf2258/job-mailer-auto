import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from core.db import record_email_open, record_link_click, record_resume_view, get_sent_resume_path_by_tracking_id

# 1x1 transparent GIF in binary
TRANSPARENT_1X1_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'

class TrackingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. Email Open Pixel: /track/open?tid=<tracking_id>
        if path.startswith("/track/open"):
            tid = query.get("tid", [""])[0]
            if tid:
                record_email_open(tid)
                print(f"[Tracker] 🟢 Email opened by recruiter! Tracking ID: {tid}")

            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(TRANSPARENT_1X1_GIF)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(TRANSPARENT_1X1_GIF)
            return

        # 2. Tracked Link Redirect: /track/click?tid=<tracking_id>&url=<dest_url>
        elif path.startswith("/track/click"):
            tid = query.get("tid", [""])[0]
            dest_url = query.get("url", [""])[0]
            if tid:
                record_link_click(tid)
                print(f"[Tracker] 🔵 Portfolio/LinkedIn link clicked! Tracking ID: {tid} -> {dest_url}")

            # Redirect recruiter to real target (e.g. LinkedIn / Portfolio)
            fallback_target = dest_url if dest_url.startswith("http") else "https://linkedin.com"
            self.send_response(302)
            self.send_header("Location", fallback_target)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            return

        # 3. Resume Click & View Tracker: /track/resume?tid=<tracking_id>
        elif path.startswith("/track/resume"):
            tid = query.get("tid", [""])[0]
            if tid:
                record_resume_view(tid)
                print(f"[Tracker] 🟣 Tailored Resume viewed/downloaded by recruiter! Tracking ID: {tid}")

            pdf_path = get_sent_resume_path_by_tracking_id(tid) if tid else None
            if pdf_path and os.path.exists(pdf_path):
                import os
                filename = os.path.basename(pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f"inline; filename=\"{filename}\"")
                self.send_header("Content-Length", str(len(pdf_bytes)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(pdf_bytes)
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Resume file not found.")
                return

        # Default 404
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        # Silence routine HTTP access logging to keep terminal clean
        return

_server_instance = None
_server_thread = None

def start_tracking_server(port=8585, host="0.0.0.0"):
    global _server_instance, _server_thread
    if _server_instance is not None:
        return True

    try:
        _server_instance = HTTPServer((host, port), TrackingHandler)
        _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        print(f"[Tracking Server] Running on http://localhost:{port} (tracking opens and clicks)")
        return True
    except Exception as e:
        print(f"[Tracking Server] Could not bind port {port}: {e}")
        return False

def get_tracking_base_url():
    """
    Returns base URL for tracking links.
    Defaults to local port 8585 or custom domain if configured.
    """
    import os
    return os.getenv("TRACKING_BASE_URL", "http://localhost:8585").rstrip("/")
