"""Self-test: LeakMatrix must retry politely on 429 and still find the leak.

Also validates the spec parser against $ref + path-item-level parameters
(the get operation carries NO parameters of its own — pre-0.2.0 LeakMatrix
would find zero operations here).

Usage:  python3 scripts/test_retry_429.py [seconds_to_stay_alive]
"""
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VICTIM = "50770148-258e-4a27-ae08-79257ee70b7f"
HITS = {"n": 0}

SWAGGER = {
    "openapi": "3.0.1",
    "info": {"title": "RetryMock", "version": "1.0"},
    "servers": [{"url": "http://127.0.0.1:8793"}],
    "components": {"parameters": {
        "CustomerId": {"name": "customerId", "in": "path", "required": True,
                       "schema": {"type": "string"}}}},
    "paths": {
        "/api/customers/{customerId}": {
            "parameters": [{"$ref": "#/components/parameters/CustomerId"}],
            "get": {"summary": "leaky endpoint behind a rate limiter"},
        },
    },
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, payload):
        b = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/swagger/v1/swagger.json":
            return self._send(200, SWAGGER)
        m = re.match(r"^/api/customers/([^/]+)$", self.path)
        if m:
            HITS["n"] += 1
            if HITS["n"] <= 2:  # rate-limit the first two requests
                self.send_response(429)
                self.send_header("Retry-After", "1")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if m.group(1) == VICTIM:
                return self._send(200, {"customerId": m.group(1),
                                        "name": "Victim AB"})
            return self._send(404, {"error": "nf"})
        return self._send(404, {"error": "nf"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 8793), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    alive = float(sys.argv[1]) if len(sys.argv) > 1 else 25
    print(f"retry-mock on http://127.0.0.1:8793 (alive {alive:.0f}s)", flush=True)
    time.sleep(alive)
