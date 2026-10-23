"""Identity handling: extract candidate cross-tenant IDs from JWTs or CLI args."""

import base64
import json
import re
import uuid
from typing import Dict, List

GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
NUMERIC_RE = re.compile(r"^\d{3,}$")

# claim names that are interesting as tenant/subject identifiers
PREFERRED_CLAIMS = ("customer_id", "customerid", "company_id", "companyid",
                    "employee_id", "employeeid", "account_id", "accountid",
                    "tenant_id", "tenantid", "org_id", "orgid",
                    "user_id", "userid", "sub", "oid")

IDISH_SUFFIX = ("id", "ids", "uid", "guid", "uuid", "number", "no", "ref")


def _idish_key(key: str) -> bool:
    """True for identity-ish claim names (customer_id, userId, employeeid...).
    Used to filter NUMERIC candidates — timestamps (iat/exp) must not become
    victim identifiers."""
    k = key.lower().rsplit(".", 1)[-1]
    return k in PREFERRED_CLAIMS or k.endswith(IDISH_SUFFIX)


def decode_jwt_payload(token: str) -> dict:
    """Decode a JWT payload without verifying the signature (read-only)."""
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:]
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    pad = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(pad.encode())
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return {}


def _collect_ids(obj, found: Dict[str, str], prefix: str = "") -> None:
    """GUIDs anywhere; numeric ids only under identity-ish claim names."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _collect_ids(v, found, prefix=f"{prefix}{k}.")
    elif isinstance(obj, str):
        m = GUID_RE.search(obj)
        if m:
            key = prefix.rstrip(".") or "value"
            found[key] = m.group(0)
        elif NUMERIC_RE.match(obj.strip()):
            key = prefix.rstrip(".") or "value"
            if _idish_key(key):
                found.setdefault(key, obj.strip())
    elif isinstance(obj, int) and not isinstance(obj, bool):
        s = str(obj)
        key = prefix.rstrip(".") or "value"
        if len(s) >= 4 and _idish_key(key):
            found.setdefault(key, s)


def candidate_ids_from_token(token: str) -> Dict[str, str]:
    """Return {claim_path: id} preferring tenant-ish claims, then any GUID."""
    claims = decode_jwt_payload(token)
    found: Dict[str, str] = {}
    _collect_ids(claims, found)

    ordered: Dict[str, str] = {}
    lowered = {k.lower(): (k, v) for k, v in found.items()}
    for pref in PREFERRED_CLAIMS:
        for lk, (k, v) in lowered.items():
            if lk == pref or lk.endswith("." + pref) or lk.split(".")[-1] == pref:
                if v not in ordered.values():
                    ordered[k] = v
    for k, v in found.items():
        if v not in ordered.values():
            ordered[k] = v
    return ordered


def parse_cli_ids(pairs: List[str]) -> Dict[str, str]:
    """Parse explicit IDs like ["customerId=5077...", "userId=2bd7..."]."""
    out: Dict[str, str] = {}
    for pair in pairs or []:
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            out[f"value{len(out)+1}"] = pair.strip()
    return out


def random_guid() -> str:
    return str(uuid.uuid4())
