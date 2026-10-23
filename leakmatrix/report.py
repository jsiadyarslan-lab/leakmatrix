"""Reports: human console summary + machine JSON for CI."""

import json
from typing import List

from . import __version__
from .classifier import (LEAK, SUSPECT, STATIC, BLOCKED, NOT_FOUND,
                         ERROR, OTHER, Verdict)

ICONS = {LEAK: "!!", SUSPECT: " ? ", STATIC: "  -", BLOCKED: "  x",
         NOT_FOUND: "  .", ERROR: " E ", OTHER: "  "}

ORDER = [LEAK, SUSPECT, STATIC, BLOCKED, NOT_FOUND, ERROR, OTHER]


def print_summary(verdicts: List[Verdict], out=print) -> None:
    if not verdicts:
        out("No cases were tested.")
        return
    counts = {k: 0 for k in ORDER}
    for v in verdicts:
        counts[v.klass] = counts.get(v.klass, 0) + 1

    out("")
    out("=" * 64)
    out("LeakMatrix report")
    out("=" * 64)
    for k in ORDER:
        if counts[k]:
            out(f"  {k:<10} {counts[k]}")
    out("-" * 64)

    for v in verdicts:
        if v.klass in (LEAK, SUSPECT):
            out(f"[{ICONS[v.klass]}] {v.klass}  {v.case_label}")
            out(f"       url: {v.url}")
            out(f"       status: {v.status}   evidence: {v.evidence or 'body'}")
    for v in verdicts:
        if v.klass not in (LEAK, SUSPECT):
            out(f"[{ICONS[v.klass]}] {v.klass:<9} {v.case_label}  ({v.status})")
    out("=" * 64)

    leaks = counts[LEAK]
    out(f"RESULT: {'FAIL — ' + str(leaks) + ' leak(s) found' if leaks else 'PASS — no confirmed leaks'}")
    out("")


def to_json(verdicts: List[Verdict]) -> str:
    return json.dumps({
        "tool": "leakmatrix",
        "version": __version__,
        "result": "FAIL" if any(v.klass == LEAK for v in verdicts) else "PASS",
        "verdicts": [{
            "operation": v.case_label, "url": v.url, "status": v.status,
            "class": v.klass, "evidence": v.evidence, "elapsed_ms": v.elapsed_ms,
        } for v in verdicts],
    }, indent=2, ensure_ascii=False)
