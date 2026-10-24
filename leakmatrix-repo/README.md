# LeakMatrix

LeakMatrix is a lightweight authorization scanner for HTTP APIs. It verifies
Broken Access Control findings (BOLA / BAC, OWASP API1:2023 and API3:2023)
with an evidence-first methodology instead of trusting status codes alone.

Status: **alpha** - first supported target: [VAmPI](https://github.com/erev0s/VAmPI),
a deliberately vulnerable training API. The tool was born from weeks of manual
access-control testing, and this repo is its first automated release.

## The idea

Most naive scanners treat an HTTP status code as a verdict. Real access control
testing does not work that way:

- A 200 on another user's object is not automatically a leak (some endpoints
  return empty template bodies for any ID).
- A 204 on a password change is not automatically a success (the server may
  silently change something else, or nothing at all).

LeakMatrix follows three rules:

1. **Triple test**: every probe compares three requests:

   - baseline -> victim's own token on the victim's object (must be 200)
   - attack   -> attacker's token on the same object (the actual test)
   - control  -> attacker's token on a random or nonexistent object (must be 404)

   A finding is CONFIRMED only when baseline and attack responses match at the
   **body level** and the control stays blocked.

2. **Writes are proven by effect, not by status code**: after a password-change
   attempt, LeakMatrix logs in with the old and the new password. Only a real
   change counts as CONFIRMED.

3. **Honest reporting**: when preconditions fail, the probe is reported as
   NOT REPRODUCED - never guessed. Zero false positives is a design goal.

## Probes (v2 alpha, VAmPI target)

| # | Probe | OWASP API Top 10 (2023) |
|---|-------|-------------------------|
| 1 | User directory readable without any token | API8:2023 |
| 2 | Debug endpoint dumps passwords in plain text (no auth) | API8:2023 |
| 3 | User PII readable without any token + existence oracle | API3:2023 |
| 4 | READ BOLA: attacker reads a victim's private object and its secret | API1:2023 |
| 5 | WRITE BOLA: attacker changes a victim's password | API1:2023 |
| 6 | Mass assignment: self-promotion to admin at registration | API3:2023 |

## Validation

The same scan was run twice against the same lab, once vulnerable and once
hardened (VAmPI started with the environment variable `vulnerable` set to `0`):

| Lab mode  | Result | Meaning |
|-----------|--------|---------|
| vulnerable | 6/6 CONFIRMED | all six probes reproduce |
| protected  | 3/6 (probes 1-3 only) | probes 4-6 correctly report NOT REPRODUCED |

The protected-mode run is the important one: a scanner that keeps reporting
findings against hardened code is noise. LeakMatrix distinguished vulnerable
from hardened code with zero false positives.

Evidence JSON files from both runs are included under `evidence/`.

## Quick start

Requirements: Python 3.8+ and `requests` (`pip install requests`).

1. Start the lab (VAmPI) locally:

```
git clone https://github.com/erev0s/VAmPI
cd VAmPI
pip install -r requirements.txt
python app.py
```

VAmPI now serves http://127.0.0.1:5000

2. Run the scanner (second terminal):

```
python leakmatrix_v2_alpha.py
```

The scanner prints a step-by-step log and a final VERDICT SUMMARY, and writes
every request and response to `leakmatrix_v2_alpha_evidence.json`.

Troubleshooting: on Python 3.13, VAmPI's old dependency pins may crash with a
SQLAlchemy `TypingOnly` assertion. Fix:

```
pip install "sqlalchemy>=2.0.36,<2.1"
```

## Roadmap

- Config-driven targets (per-target base URL, headers, auth scheme)
- More probes: login-message user enumeration, SQL injection detection
- More lab integrations: crAPI, OWASP Juice Shop
- Report export (HTML)

## Disclaimer

LeakMatrix is for authorized security testing and education only. Run it only
against systems you own or have explicit written permission to test.