"""Response classification — conservative: only confident leaks are LEAK."""

import json
from dataclasses import dataclass
from typing import Dict, Optional

# classes
LEAK = "LEAK"            # 2xx + victim-specific identifier present in body
SUSPECT = "SUSPECT"      # 2xx + large body (manual review needed)
STATIC = "STATIC"        # same answer for random GUID -> endpoint ignores id
BLOCKED = "BLOCKED"      # 401/403
NOT_FOUND = "NOT_FOUND"
ERROR = "ERROR"          # 5xx / network
OTHER = "OTHER"


@dataclass
class Verdict:
    case_label: str
    url: str
    status: int
    klass: str
    evidence: str = ""
    elapsed_ms: int = 0


def classify(status: int, body: str, victim_ids: Dict[str, str],
             body_bytes: Optional[int] = None) -> str:
    if status == 0:
        return ERROR
    if status in (401, 403):
        return BLOCKED
    if status == 404 or 300 <= status < 400:
        return NOT_FOUND if status == 404 else OTHER
    if status >= 500:
        return ERROR
    if 200 <= status < 300:
        low = body.lower()
        for val in victim_ids.values():
            if val and _contains(low, val.lower()):
                return LEAK
        n = body_bytes if body_bytes is not None else len(body)
        if n > 500:
            return SUSPECT
        return OTHER
    return OTHER


def _contains(body_low: str, val_low: str) -> bool:
    """Long ids: plain substring is safe. Short ids (victim id '1', '42')
    require JSON value context — otherwise every body containing that digit
    would fire a fake LEAK."""
    if len(val_low) >= 6:
        return val_low in body_low
    return (f'"{val_low}"' in body_low
            or f":{val_low}," in body_low
            or f":{val_low}}}" in body_low)


def refine_with_control(base_klass: str, probe_body: str,
                        control) -> str:
    """Differential control: identical body for a random GUID means the
    endpoint never used the victim id -> STATIC, not a leak."""
    if base_klass in (LEAK, SUSPECT) and control is not None:
        same = control.status == 200 and \
            _normalized(control.body) == _normalized(probe_body)
        if same:
            return STATIC
    return base_klass


def _normalized(body: str) -> str:
    try:
        return json.dumps(json.loads(body), sort_keys=True)
    except Exception:
        return body.strip()
