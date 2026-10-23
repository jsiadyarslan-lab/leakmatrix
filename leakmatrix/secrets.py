"""Credential-material detection — the Hugging Face lesson (May 2023).

A cross-tenant leak that leaks *secrets* is Critical, not Medium. Every 2xx
body is scanned for recognizable token formats. Conservative by design:
only well-known shapes, no generic entropy guessing — fewer false positives
keeps the findings trustworthy.

Findings are always redacted: the tool never stores a full secret.
"""

import re
from dataclasses import dataclass
from typing import List

# Well-known token shapes only (formats, matched conservatively)
SECRET_PATTERNS = [
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ("github_pat", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ("aws_key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("google_api_key", r"\bAIza[0-9A-Za-z_\-]{30,}\b"),
    ("slack_token", r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    ("openai_style_key", r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}\b"),
    ("private_key_block", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


@dataclass
class SecretFinding:
    kind: str
    redacted: str  # never store the full secret


def _redact(text: str) -> str:
    if len(text) <= 10:
        return text[:2] + "***"
    return text[:6] + "..." + text[-4:]


def scan_for_secrets(body: str) -> List[SecretFinding]:
    """Return redacted findings of credential-like material in a body."""
    findings: List[SecretFinding] = []
    for kind, pattern in SECRET_PATTERNS:
        for m in re.finditer(pattern, body):
            findings.append(SecretFinding(kind=kind, redacted=_redact(m.group(0))))
    return findings
