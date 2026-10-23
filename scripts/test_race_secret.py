"""Self-test for 0.3.0: cross-session race + credential-material scanning.

Reproduces BOTH public incidents ethically on a mock:

1. OpenAI/redis-py lesson (Mar 2023): under concurrency, a reused backend
   connection returns the PREVIOUS user's data. Here /api/orders/{orderId}
   bleeds the victim's customerId + a fake GitHub token on every 4th hit —
   LeakMatrix's --race 6 junk-id burst must catch it as RACE_LEAK.
2. Hugging Face lesson (May 2023): leaked bodies containing credential
   material are flagged by the secret scanner (fake token, clearly inert).

Usage:  python3 scripts/test_race_secret.py [seconds_to_stay_alive]
"""
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VICTIM_CUSTOMER = "50770148-258e-4a27-ae08-79257ee70b7f"
# FAKE token (pattern-valid, inert): used only to test the scanner.
FAKE_GH_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9"
HITS = {"n": 0}

SWAGGER = {
    "openapi": "3.0.1",
    "info": {"title": "RaceMock", "version": "1.0"},
    "servers": [{"url": "http://127.0.0.1:8794"}],
    "components": {"parameters": {
        "OrderId": {"name": "orderId", "in": "path", "required": True,
                    "schema": {"type": "string"}}}},
    "paths": {
        "/api/orders/{orderId}": {
            "parameters": [{"$ref": "#/components/parameters/OrderId"}],
            "get": {"summary": "order status with a session-reuse race"},
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
        m = re.match(r"^/api/orders/([^/]+)$", self.path)
        if m:
            HITS["n"] += 1
            if HITS["n"] % 4 == 0:
                # simulated session-reuse bleed: attacker's request gets
                # the victim's order context + credential material
                return self._send(200, {
                    "orderId": m.group(1),
                    "customerId": VICTIM_CUSTOMER,
                    "checkoutToken": FAKE_GH_TOKEN,
                    "note": "wrong-session payload (simulated)"})
            return self._send(404, {"error": "order not found"})
        return self._send(404, {"error": "nf"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 8794), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    alive = float(sys.argv[1]) if len(sys.argv) > 1 else 25
    print(f"race/secret mock on http://127.0.0.1:8794 (alive {alive:.0f}s)",
          flush=True)
    time.sleep(alive)
