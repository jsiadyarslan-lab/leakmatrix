"""Mock target app for self-testing LeakMatrix.

Deliberately contains one REAL cross-tenant leak, one properly protected
endpoint, one static/echo false-positive trap, and one 404 path — so a
run demonstrates all verdict classes at once.

Usage:  python3 mock_target.py [port]
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VICTIM_CUSTOMER = "50770148-258e-4a27-ae08-79257ee70b7f"
VICTIM_EMPLOYEE = "cff135e7-a737-433b-9d07-93db9249cb64"

SWAGGER = {
    "openapi": "3.0.1",
    "info": {"title": "MockBiz API", "version": "1.0"},
    "servers": [{"url": "http://127.0.0.1:8791"}],
    "paths": {
        "/api/customers/{customerId}": {
            "get": {"summary": "Get customer (VULNERABLE in mock)",
                    "parameters": [{"name": "customerId", "in": "path",
                                    "required": True, "schema": {"type": "string"}}]}
        },
        "/api/secure/customers/{customerId}": {
            "get": {"summary": "Get customer (protected)",
                    "parameters": [{"name": "customerId", "in": "path",
                                    "required": True, "schema": {"type": "string"}}]}
        },
        "/api/employees/{employeeId}/status": {
            "get": {"summary": "Employment status (ignores the id — static trap)",
                    "parameters": [{"name": "employeeId", "in": "path",
                                    "required": True, "schema": {"type": "string"}}]}
        },
        "/api/employees/{employeeId}": {
            "get": {"summary": "Employee profile (proper tenant check -> 404 mask)",
                    "parameters": [{"name": "employeeId", "in": "path",
                                    "required": True, "schema": {"type": "string"}}]}
        },
    },
}

GUID_PATH_RE = re.compile(r"^/[0-9a-fA-F-]{36}$")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path
        if path == "/swagger/v1/swagger.json":
            return self._send(200, SWAGGER)

        m = re.match(r"^/api/customers/([^/]+)$", path)
        if m:  # VULNERABLE: no ownership check
            cid = m.group(1)
            if cid == VICTIM_CUSTOMER:
                return self._send(200, {
                    "customerId": cid, "name": "Victim AB", "email": "victim@example.com",
                    "invoices": ["INV-1", "INV-2"]})
            if GUID_PATH_RE.match("/" + cid):
                return self._send(200, {"customerId": cid, "name": "Random Co"})
            return self._send(404, {"error": "not found"})

        m = re.match(r"^/api/secure/customers/([^/]+)$", path)
        if m:  # PROTECTED: token-bound tenant check
            auth = self.headers.get("Authorization", "")
            if auth != "Bearer victim-own-token" or m.group(1) != VICTIM_CUSTOMER:
                return self._send(401, {"errorCode": "resource.access.forbidden"})
            return self._send(200, {"customerId": m.group(1), "name": "Victim AB"})

        m = re.match(r"^/api/employees/([^/]+)/status$", path)
        if m:  # STATIC TRAP: ignores the id entirely, large body -> SUSPECT bait
            filler = ("Policy terms: employment status is provided as a constant "
                      "service response. " * 12)
            return self._send(200, {"status": "active", "note": "constant answer",
                                    "terms": filler})

        m = re.match(r"^/api/employees/([^/]+)$", path)
        if m:  # masked 404 for foreign tenant
            if m.group(1) == VICTIM_EMPLOYEE:
                return self._send(200, {"employeeId": m.group(1), "name": "Emp A"})
            return self._send(404, {"error": "not found"})

        return self._send(404, {"error": "not found"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    print(f"mock target on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
