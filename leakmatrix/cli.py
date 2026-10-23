"""LeakMatrix CLI."""

import argparse
import sys

from . import __version__
from .spec import load_spec, base_url_of, iter_operations
from .ids import candidate_ids_from_token, parse_cli_ids
from .matrix import build_cases
from .runner import Runner
from .classifier import classify, refine_with_control, Verdict, RACE_LEAK
from .secrets import scan_for_secrets
from .report import print_summary, to_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="leakmatrix",
        description="Cross-tenant authorization testing from any OpenAPI/Swagger spec.")
    p.add_argument("--version", action="version",
                   version=f"leakmatrix {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a cross-tenant matrix against a target")
    r.add_argument("--spec", required=True,
                   help="URL or file path of swagger/openapi JSON")
    r.add_argument("--attacker-token", required=True,
                   help="credential of account B (attacker), e.g. 'Bearer eyJ...'")
    r.add_argument("--victim-token", default="",
                   help="credential/JWT of account A (victim) — IDs auto-extracted from claims")
    r.add_argument("--victim-ids", action="append", default=[],
                   help="explicit victim id, repeatable: --victim-ids customerId=5077...")
    r.add_argument("--base-url", default="",
                   help="override base URL from the spec")
    r.add_argument("--header", action="append", default=[],
                   help="extra header, repeatable: --header 'X-Bug-Bounty: handle'")
    r.add_argument("--methods", default="get",
                   help="comma-separated safe methods to test (default: get)")
    r.add_argument("--rps", type=float, default=4.0,
                   help="max requests per second (default 4 — be polite)")
    r.add_argument("--retries", type=int, default=2,
                   help="polite retries on 429/502/503/504 honoring Retry-After (default 2)")
    r.add_argument("--strict", action="store_true",
                   help="exit 1 also when only SUSPECT findings exist (CI paranoia)")
    r.add_argument("--race", type=int, default=0, metavar="N",
                   help="cross-session race probes (OpenAI/redis-py lesson): "
                        "N concurrent junk-id requests on up to 5 endpoints; 0=off")
    r.add_argument("--timeout", type=int, default=15)
    r.add_argument("--user-agent", default=None,
                   help="override default User-Agent")
    r.add_argument("--no-controls", action="store_true",
                   help="skip random-GUID differential controls")
    r.add_argument("--json", dest="json_out", default="",
                   help="write machine report to file (CI-friendly)")
    r.add_argument("--max-variants-per-op", type=int, default=8)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    extra_headers = {}
    for h in args.header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            extra_headers[k.strip()] = v.strip()

    print(f"[*] loading spec: {args.spec}")
    try:
        spec = load_spec(args.spec, timeout=args.timeout)
    except Exception as exc:
        print(f"[!] cannot load spec: {exc}")
        return 2

    base = base_url_of(spec, args.base_url or None)
    methods = tuple(m.strip().lower() for m in args.methods.split(",") if m.strip())
    operations = list(iter_operations(spec, base, only_methods=methods))
    print(f"[*] base URL: {base}")
    print(f"[*] operations with id-like path params ({'+'.join(m.upper() for m in methods)}): "
          f"{len(operations)}")

    victim_ids = parse_cli_ids(args.victim_ids)
    if args.victim_token:
        claims_ids = candidate_ids_from_token(args.victim_token)
        for k, v in claims_ids.items():
            victim_ids.setdefault(k, v)
    if not victim_ids:
        print("[!] no victim identifiers (pass --victim-token or --victim-ids)")
        return 2
    print(f"[*] victim identifiers: {len(victim_ids)}")
    for k, v in list(victim_ids.items())[:6]:
        print(f"      {k} = {v}")

    cases = build_cases(operations, victim_ids, args.attacker_token,
                        max_variants_per_op=args.max_variants_per_op)
    print(f"[*] matrix size: {len(cases)} request(s)"
          f"{' + random-GUID controls' if not args.no_controls else ''}")
    if not cases:
        print("[!] nothing to test — no operations matched")
        return 2

    def _on_retry(attempt: int, delay: float, status: int) -> None:
        reason = "rate-limited/transient" if status else "network error"
        print(f"      retry {attempt}: {reason} (status {status}) "
              f"-> backing off {delay:.0f}s")

    runner = Runner(rps=args.rps, timeout=args.timeout,
                    user_agent=args.user_agent, extra_headers=extra_headers,
                    retries=args.retries, on_retry=_on_retry)

    verdicts = []
    for i, case in enumerate(cases, 1):
        resp = runner.run_probe(case)
        klass = classify(resp.status, resp.body, victim_ids)
        evidence = ""
        if klass in ("LEAK", "SUSPECT") and not args.no_controls:
            ctrl = runner.run_random_control(case)
            new_klass = refine_with_control(klass, resp.body, ctrl)
            if new_klass == "STATIC":
                evidence = "same body for random GUID (endpoint ignores id)"
            klass = new_klass
        secrets_found = scan_for_secrets(resp.body) if 200 <= resp.status < 300 else []
        verdicts.append(Verdict(case_label=case.operation, url=case.url,
                                status=resp.status, klass=klass,
                                evidence=evidence, elapsed_ms=resp.elapsed_ms,
                                secrets=len(secrets_found),
                                secret_kinds=",".join(sorted({s.kind for s in secrets_found}))))
        tried = f" (after {resp.attempts} tries)" if resp.attempts > 1 else ""
        print(f"  [{i}/{len(cases)}] {case.operation} -> {resp.status} {klass}{tried}")

    # Cross-session race probing — opt-in, bounded (OpenAI/redis-py lesson)
    if args.race:
        sample = cases[:5]
        print(f"\n[*] race probes: {len(sample)} endpoint(s) x {args.race} "
              f"concurrent junk-id requests (attacker token only)")
        for case in sample:
            for resp in runner.race_probe(case, args.race):
                klass = classify(resp.status, resp.body, victim_ids)
                if klass == "LEAK":
                    klass = RACE_LEAK  # victim data WITHOUT aiming at their id
                secrets_found = scan_for_secrets(resp.body) if 200 <= resp.status < 300 else []
                verdicts.append(Verdict(case_label=case.operation + " [race]",
                                        url=case.url, status=resp.status,
                                        klass=klass, evidence="concurrent burst",
                                        elapsed_ms=resp.elapsed_ms,
                                        secrets=len(secrets_found),
                                        secret_kinds=",".join(sorted({s.kind for s in secrets_found}))))
            print(f"  [race] {case.operation} -> {args.race} copies sent")

    print_summary(verdicts)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(to_json(verdicts))
        print(f"[*] JSON report written: {args.json_out}")

    failed = any(v.klass in ("LEAK", RACE_LEAK) for v in verdicts)
    if args.strict:
        failed = failed or any(v.klass == "SUSPECT" for v in verdicts)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
