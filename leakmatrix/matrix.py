"""Matrix builder: pair attacker auth with victim identifiers across operations."""

import re
from dataclasses import dataclass, field
from typing import Dict, List

from .ids import random_guid

BRACE_RE = re.compile(r"\{([^}]+)\}")


@dataclass
class RequestCase:
    """One concrete HTTP request derived from the matrix."""
    operation: str          # label, e.g. "GET /customers/{customerId}"
    url: str                # fully substituted URL
    role: str               # "probe" | "control_random"
    substitutions: Dict[str, str] = field(default_factory=dict)
    token: str = ""         # which credential to use


def _name_affinity(param: str, claim: str) -> bool:
    """customerId matches customer_id / customerid / customerId claims."""
    norm = lambda s: s.lower().replace("_", "").replace("-", "").replace(".", "")
    p, c = norm(param), norm(claim)
    return p == c or p.endswith(c) or c.endswith(p)


def build_cases(operations, victim_ids: Dict[str, str],
                attacker_token: str,
                max_variants_per_op: int = 8) -> List[RequestCase]:
    """Build one request per (operation, id-like param) using the best-matching
    victim identifier; remaining id-params filled with the top candidate.
    Name-aware matching first (customerId -> customer_id claim), fallback order
    preserved. Random-GUID controls are NOT built here (runner adds them)."""
    cases: List[RequestCase] = []
    seen_urls = set()
    values = list(victim_ids.values())
    if not values:
        return cases
    top = values[0]

    for op in operations:
        variants = 0
        for param in op.param_names:
            if variants >= max_variants_per_op:
                break
            # choose best victim id for this param
            chosen = None
            for claim_name, val in victim_ids.items():
                if _name_affinity(param, claim_name):
                    chosen = val
                    break
            if chosen is None:
                chosen = top
            subs = {}
            for other in op.param_names:
                subs[other] = chosen if other == param else \
                    next((v for cn, v in victim_ids.items()
                          if _name_affinity(other, cn)), top)
            url = BRACE_RE.sub(lambda m: subs.get(m.group(1), m.group(1)), op.path)
            if "{" in url:
                continue  # unresolved non-id placeholders — skip safely
            key = (op.label, url)
            if key in seen_urls:
                continue  # two params resolved to the same concrete URL
            seen_urls.add(key)
            cases.append(RequestCase(operation=op.label, url=url, role="probe",
                                     substitutions={param: chosen},
                                     token=attacker_token))
            variants += 1
    return cases
