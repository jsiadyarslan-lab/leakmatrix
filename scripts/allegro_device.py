#!/usr/bin/env python3
# Allegro Sandbox OAuth Device Flow - authorized testing only (Intigriti / sandbox).
# Usage: python allegro_device.py <client_id> [suffix]
#   suffix "victim" -> saves allegro_token_victim.txt (attacker token untouched)

import base64
import getpass
import json
import sys
import time
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CLIENT_ID_DEFAULT = "c4c3c7627ca3450f8907a4c92f5ac842"
UA = "jaber-55/1.0 (+https://github.com/jsiadyarslan-lab/leakmatrix)"
BASE = "https://allegro.pl.allegrosandbox.pl"
DEVICE = BASE + "/auth/oauth/device"
TOKEN = BASE + "/auth/oauth/token"
ME = "https://api.allegro.pl.allegrosandbox.pl/me"

SCOPES_FULL = " ".join([
    "allegro:api:sale:settings:write",
    "allegro:api:sale:settings:read",
    "allegro:api:sale:offers:write",
    "allegro:api:sale:offers:read",
    "allegro:api:profile:read",
    "allegro:api:profile:write",
    "allegro:api:ratings",
    "allegro:api:orders:read",
    "allegro:api:orders:write",
    "allegro:api:messaging",
    "allegro:api:disputes",
    "allegro:api:bids",
    "allegro:api:billing:read",
    "allegro:api:payments:read",
    "allegro:api:payments:write",
    "allegro:api:campaigns",
    "allegro:api:fulfillment:read",
    "allegro:api:fulfillment:write",
    "allegro:api:shipments:read",
    "allegro:api:shipments:write",
    "allegro:api:affiliate:read",
])
SCOPES_MIN = " ".join([
    "allegro:api:sale:settings:write",
    "allegro:api:sale:settings:read",
    "allegro:api:sale:offers:write",
    "allegro:api:sale:offers:read",
])


def post_form(url, data, auth=None):
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if auth:
        headers["Authorization"] = auth
    req = Request(url, data=urlencode(data).encode("utf-8"), headers=headers, method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def basic_header(client_id, secret):
    raw = "%s:%s" % (client_id, secret)
    return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def request_device_code(client_id, auth, scopes):
    return post_form(DEVICE, {"client_id": client_id, "scope": scopes}, auth=auth)


def main():
    client_id = sys.argv[1].strip() if len(sys.argv) > 1 else CLIENT_ID_DEFAULT
    suffix = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    token_file = "allegro_token%s.txt" % (("_" + suffix) if suffix else "")
    refresh_file = "allegro_refresh%s.txt" % (("_" + suffix) if suffix else "")
    print("=== LeakMatrix | Allegro Sandbox - Device Flow (with write scopes) ===")
    if suffix:
        print("Suffix mode: %s -> token goes to %s (other account token untouched)" % (suffix, token_file))
    print("Client ID: %s" % client_id)
    secret = getpass.getpass("Paste client_secret then Enter (hidden): ").strip()
    if not secret:
        print("client_secret is required - copy it from your app page in the portal")
        sys.exit(1)
    auth = basic_header(client_id, secret)

    print("[1/3] Requesting device code from:", DEVICE)
    d = None
    try:
        d = request_device_code(client_id, auth, SCOPES_FULL)
        print("      Scope: FULL list requested (%d scopes)" % len(SCOPES_FULL.split()))
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        print("      HTTP %s with full scope list. Body: %s" % (e.code, body))
        print("      Retrying with the essential 4 scopes only...")
        try:
            d = request_device_code(client_id, auth, SCOPES_MIN)
            print("      Scope: MIN list accepted")
        except HTTPError as e2:
            body2 = ""
            try:
                body2 = e2.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            print("Failed HTTP %s" % e2.code)
            if body2:
                print("Response: %s" % body2)
            www = e2.headers.get("WWW-Authenticate") if e2.headers else None
            if www:
                print("WWW-Authenticate: %s" % www)
            print("Hints:")
            print("  1) Re-copy client_secret from your app page in the portal")
            print("  2) App type must be 'without browser/keyboard' for device flow")
            print("  3) Try again later or from phone hotspot if a JS page appears")
            sys.exit(1)
        except (URLError, json.JSONDecodeError) as e2:
            print("Non-JSON response (DataDome?): %s" % e2)
            print("Hint: try again later or from phone hotspot.")
            sys.exit(1)
    except (URLError, json.JSONDecodeError) as e:
        print("Non-JSON response (redirect to login or DataDome protection): %s" % e)
        print("Hint: try again later or from phone hotspot.")
        sys.exit(1)

    user_code = d.get("user_code", "?")
    vurl = d.get("verification_uri_complete") or d.get("verification_uri")
    print("    Device code valid for %s seconds" % d.get("expires_in", 600))
    print("[2/3] Opening the browser on the consent page:")
    print("      %s" % vurl)
    print("      Confirmation code: %s" % user_code)
    print("      IMPORTANT: log in with the CORRECT sandbox account for this token:")
    print("        - victim suffix  -> alsayadij@gmail.com (private window)")
    print("        - attacker token -> jaber.alsayadi1@gmail.com (normal window)")
    print("      The consent page will list MANY permissions - approve all of them.")
    try:
        if vurl:
            webbrowser.open(vurl)
    except Exception:
        print("      Could not open the browser automatically - copy the link above.")

    interval = int(d.get("interval", 5) or 5)
    deadline = time.time() + int(d.get("expires_in", 600) or 600)
    print("[3/3] Waiting for your approval (every %s seconds)... Ctrl+C to cancel" % interval)

    token = None
    while time.time() < deadline:
        time.sleep(interval)
        try:
            t = post_form(
                TOKEN,
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": d["device_code"],
                    "client_id": client_id,
                },
                auth=auth,
            )
        except HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8"))
            except Exception:
                err = {}
            ec = err.get("error", "")
            if ec == "authorization_pending":
                print("    ... still waiting for your approval in the browser", flush=True)
                continue
            if ec == "slow_down":
                interval += 5
                continue
            print("Server error: %s" % err)
            sys.exit(1)
        except (URLError, TimeoutError) as e:
            print("    transient network error, retrying: %s" % e, flush=True)
            continue
        except json.JSONDecodeError:
            print("    non-JSON response (DataDome?) - retrying...", flush=True)
            continue

        token = t.get("access_token")
        if not token:
            print("Unexpected response: %s" % t)
            sys.exit(1)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write("Bearer " + token + "\n")
        if t.get("refresh_token"):
            with open(refresh_file, "w", encoding="utf-8") as f:
                f.write(t["refresh_token"] + "\n")
        print("")
        print("Token saved to %s (never share this file)" % token_file)
        if t.get("refresh_token"):
            print("refresh_token saved to %s" % refresh_file)
        break
    else:
        print("Timed out without approval - run the script again.")
        sys.exit(1)

    print("--- Verifying GET /me ---")
    req = Request(
        ME,
        headers={
            "User-Agent": UA,
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.allegro.public.v1+json",
            "Accept-Language": "pl-PL",
        },
    )
    try:
        with urlopen(req, timeout=30) as r:
            me = json.loads(r.read().decode("utf-8"))
            print(json.dumps(me, indent=2, ensure_ascii=False))
            print("")
            print(">>> Verified account id above. If you used suffix 'victim', expect id=111627974.")
            print(">>> Next step: python scripts/allegro_seed_offer.py")
    except HTTPError as e:
        print("/me returned HTTP %s - check the registered User-Agent header" % e.code)
    except (URLError, json.JSONDecodeError) as e:
        print("/me failed to read response: %s" % e)


if __name__ == "__main__":
    main()