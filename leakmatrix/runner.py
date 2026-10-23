"""HTTP runner — ROE-friendly: strict rate limit, custom UA, bug-bounty header.

Polite by design: rate-limited, and on 429/502/503/504 (or transient network
errors) it backs off honoring Retry-After — a lesson learned live on a
sandbox portal that throttles registration traffic.
"""

import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import requests

from .ids import random_guid
from .matrix import RequestCase

DEFAULT_UA = "LeakMatrix/0.2 (+authorized security testing)"

# transient failures worth a polite retry (429 = rate limited — be patient!)
RETRYABLE = {429, 502, 503, 504}
NO_RETRY_EXC = (requests.exceptions.InvalidURL,
                requests.exceptions.MissingSchema,
                requests.exceptions.InvalidSchema)


@dataclass
class Response:
    status: int
    body: str
    elapsed_ms: int
    attempts: int = 1


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


class Runner:
    def __init__(self, rps: float = 4.0, timeout: int = 15,
                 user_agent: str = DEFAULT_UA,
                 extra_headers: Optional[Dict[str, str]] = None,
                 retries: int = 2,
                 on_retry: Optional[Callable[[int, float, int], None]] = None):
        """on_retry(attempt, delay_s, status) — status is 0 for network errors."""
        self.min_interval = 1.0 / max(rps, 0.1)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.on_retry = on_retry
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, */*",
        })
        for k, v in (extra_headers or {}).items():
            self.session.headers[k] = v
        self._last = 0.0

    def _pace(self) -> None:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    @staticmethod
    def _backoff_delay(retry_after: Optional[str], attempt: int) -> float:
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass  # HTTP-date or garbage -> exponential below
        return min(2.0 * (2 ** (attempt - 1)), 30.0)  # 2s, 4s, 8s ... cap 30s

    def request(self, method: str, url: str, token: str = "") -> Response:
        headers = {"Authorization": token} if token else {}
        t0 = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            self._pace()
            retry_after_hdr = None
            try:
                r = self.session.request(method, url, headers=headers,
                                         timeout=self.timeout, allow_redirects=False)
                status, body = r.status_code, r.text[:20000]
                retry_after_hdr = r.headers.get("Retry-After")
            except NO_RETRY_EXC as exc:
                return Response(status=0, body=f"__EXC__:{type(exc).__name__}",
                                elapsed_ms=_ms(t0), attempts=attempt)
            except requests.RequestException as exc:
                status, body = 0, f"__EXC__:{type(exc).__name__}"

            transient = status in RETRYABLE or status == 0
            if transient and attempt <= self.retries:
                delay = self._backoff_delay(retry_after_hdr, attempt)
                if self.on_retry:
                    self.on_retry(attempt, delay, status)
                time.sleep(delay)
                continue
            return Response(status=status, body=body,
                            elapsed_ms=_ms(t0), attempts=attempt)

    def run_probe(self, case: RequestCase) -> Response:
        return self.request(case.operation.split(" ", 1)[0], case.url, case.token)

    def run_random_control(self, case: RequestCase) -> Optional[Response]:
        """Re-run the same URL with random GUIDs swapped for the victim ids.
        If the server answers identically, the endpoint ignores the id
        (static/echo path) -> kills false positives (lesson: is-impersonated)."""
        method = case.operation.split(" ", 1)[0]
        url_rand = case.url
        for original in case.substitutions.values():
            url_rand = url_rand.replace(original, random_guid())
        return self.request(method, url_rand, case.token)
