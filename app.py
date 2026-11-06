#!/usr/bin/env python3
"""Local web app for the demo: serves dashboard.html and runs the simulation on request.

    python3 app.py                      # then open http://localhost:8000
    python3 app.py --ns3 ~/ns-3.49 --port 8000

Standard library only. Binds to 127.0.0.1, so only this machine can reach it.
(From Windows, a browser reaches a server running inside WSL2 at http://localhost:8000.)
"""
import argparse
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simlib

HERE = os.path.dirname(os.path.abspath(__file__))
SLOTS = threading.Semaphore(max(2, os.cpu_count() or 2))


class Handler(BaseHTTPRequestHandler):
    ns3 = None

    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path in ("/", "/index.html", "/dashboard.html"):
            with open(os.path.join(HERE, "dashboard.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if url.path == "/api/ping":
            return self._send(200, json.dumps({"ok": True, "ns3": self.ns3}), "application/json")
        if url.path == "/api/run":
            try:
                n = int(q.get("n", 20))
                sim = float(q.get("sim", 3))
                if not (2 <= n <= 60 and 1.2 <= sim <= 6):
                    raise ValueError("n must be 2-60 and sim 1.2-6")
                with SLOTS:
                    out = simlib.run_one(self.ns3, q.get("config", ""), n, q.get("topology", "single"), sim)
                return self._send(200, json.dumps(out), "application/json")
            except Exception as e:  # report to the page instead of a blank 500
                return self._send(400, json.dumps({"error": str(e)}), "application/json")
        self._send(404, "not found", "text/plain")

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns3", default=simlib.default_ns3())
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 only if you want other devices on your network to reach it")
    a = ap.parse_args()
    try:
        simlib.find_binary(a.ns3)
    except FileNotFoundError as e:
        raise SystemExit(str(e))
    Handler.ns3 = a.ns3
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("Dashboard running. Open  http://localhost:%d  in your browser. Ctrl+C to stop." % a.port, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
