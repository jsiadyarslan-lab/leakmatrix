# LeakMatrix

**Continuous cross-tenant authorization testing — from any OpenAPI/Swagger spec.**

Finds IDOR/BOLA leaks (OWASP API #1) automatically, before attackers do.
The idea is simple: log in as account B, then try to read account A's data
through every endpoint in the spec. Anything that answers `200` with A's
identifiers inside is a leak.

Built from real bug-bounty fieldwork (Intigriti), not theory.

## Install

```bash
pip install .            # or: run directly with python3 -m leakmatrix
```

Requires Python 3.8+ and `requests`.

## Quickstart

```bash
leakmatrix run \
  --spec https://api.example.com/swagger/v1/swagger.json \
  --attacker-token "Bearer eyJ..." \
  --victim-token  "Bearer eyJ..." \
  --header "X-Bug-Bounty: your-handle" \
  --rps 4 \
  --json report.json
```

- `--attacker-token` — the credential you will send (account B).
- `--victim-token` — account A's JWT; its claims are decoded read-only and
  every GUID **and numeric identity id** in them becomes a victim identifier
  (`customer_id`, `sub`, ...). Explicit ids also work:
  `--victim-ids customerId=5077...`.
- `--retries N` — polite retries on 429/502/503/504 honoring `Retry-After`
  (default 2). The tool backs off instead of hammering a throttling target.
- `--strict` — CI mode: exit `1` also when only `SUSPECT` findings exist.
- `--json report.json` — machine report; CI should treat exit code `1` as FAIL.

## What it does

1. Loads any Swagger 2 / OpenAPI 3 spec — JSON, or YAML when PyYAML is
   installed. `$ref` parameter objects and path-item-level parameters are
   resolved (both extremely common in real specs).
2. Picks every operation with an id-like path parameter
   (`{customerId}`, `{employeeId}`, ...).
3. Name-matches those parameters to the victim's token claims
   (`customerId` ↔ `customer_id`) and builds the request matrix.
4. Sends it **only with safe methods (GET by default)**, rate-limited
   (default 4 req/s), with your custom headers (ROE-friendly).
5. Classifies each answer:

| Class     | Meaning                                                      |
|-----------|--------------------------------------------------------------|
| `LEAK`    | 2xx **and** a victim identifier appears in the body          |
| `SUSPECT` | 2xx with a large body — needs human eyes                     |
| `STATIC`  | same body for a random GUID — endpoint ignores the id (safe) |
| `BLOCKED` | 401/403 — properly rejected                                  |
| `NOT_FOUND` | 404 — masked or absent                                     |
| `ERROR`   | 5xx / network                                                |

Short victim ids (e.g. numeric `1`) are only matched inside JSON value
context — a body merely *containing* the digit `1` is not a leak.

6. The **random-GUID differential control** re-runs every LEAK/SUSPECT with
   fake ids: if the body is identical, the endpoint never used the id — the
   false positive is killed automatically (a lesson learned the hard way on
   a real program).
7. **429 is expected, not an error**: the runner backs off (honoring
   `Retry-After`), retries politely, and reports the final verdict with the
   number of attempts used.

## Self-test demo

```bash
python3 examples/mock_target.py 8791 &
python3 -m leakmatrix run \
  --spec http://127.0.0.1:8791/swagger/v1/swagger.json \
  --attacker-token "Bearer attacker-token" \
  --victim-token  "Bearer eyJhbGciOiAibm9uZSIsICJ0eXAiOiAiSldUIn0.eyJzdWIiOiAiMmJkN2U4MzItYWJkZi00NTMxLWI3MWItYTZlMjk0NDA3YjA5IiwgImN1c3RvbWVyX2lkIjogIjUwNzcwMTQ4LTI1OGUtNGEyNy1hZTA4LTc5MjU3ZWU3MGI3ZiIsICJlbXBsb3llZV9pZCI6ICJjZmYxMzVlNy1hNzM3LTQzM2ItOWQwNy05M2RiOTI0OWNiNjQifQ.sig"
```

Expected: `2 LEAK`, `1 BLOCKED`, `1 STATIC`, exit code `1`.

### Retry / 429 self-test

```bash
python3 scripts/test_retry_429.py 25 &   # mock that rate-limits first, then leaks
python3 -m leakmatrix run \
  --spec http://127.0.0.1:8793/swagger/v1/swagger.json \
  --attacker-token "Bearer attacker-token" \
  --victim-ids customerId=50770148-258e-4a27-ae08-79257ee70b7f
```

Expected: retry lines, then `1 LEAK (after 3 tries)`, exit code `1`.
This spec uses `$ref` + path-item-level parameters, so it also proves the
spec parser handles them.

## Roadmap

- [ ] GitHub Action packaging (`uses: leakmatrix/run@v1`)
- [ ] HTML report with request/response evidence
- [ ] Replay mode from HAR captures
- [ ] POST-body id substitution (opt-in, unsafe methods behind a flag)
- [ ] Self-learning positive controls from the attacker's own account

## Ethics

Only test systems you are authorized to test. Keep the rate limits. Set
your bug-bounty headers. Bug bounty is a privilege — act like a guest.
