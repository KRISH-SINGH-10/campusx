"""Dev check of sign-in and access rules against a running app.
Usage: python scripts/check_access.py [base_url]"""
import json
import sys
from pathlib import Path

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
ACCOUNTS = json.loads((Path(__file__).resolve().parent.parent / "app" / "demo_accounts.json").read_text())
by_name = {a["name"].split()[0].lower(): a for a in ACCOUNTS}


def login(key):
    s = requests.Session()
    a = by_name[key]
    r = s.post(f"{BASE}/api/login", json={"email": a["email"], "password": a["password"]})
    assert r.status_code == 200, r.text
    return s


def expect(label, got, want):
    print(f"{'ok  ' if got == want else 'FAIL'} {label}: {got}" + ("" if got == want else f" (wanted {want})"))


anon = requests.Session()
expect("anon home redirects to login", anon.get(f"{BASE}/", allow_redirects=False).headers.get("location"), "/login")
expect("anon insurer page redirects", anon.get(f"{BASE}/insurer", allow_redirects=False).headers.get("location"), "/login")
expect("anon claims api", anon.get(f"{BASE}/api/claims").status_code, 401)
expect("wrong password", anon.post(f"{BASE}/api/login", json={"email": ACCOUNTS[0]["email"], "password": "x"}).status_code, 401)

rohan, ananya, insurer = login("rohan"), login("ananya"), login("suraksha")
r = rohan.post(f"{BASE}/api/claims", data={"sample": "gallbladder"})
expect("customer creates claim", r.status_code, 201)
cid = r.json()["id"]
claim = rohan.get(f"{BASE}/api/claims/{cid}").json()
print("     stored documents:", claim.get("documents"))

expect("owner sees claim", rohan.get(f"{BASE}/api/claims/{cid}").status_code, 200)
expect("other customer cannot see claim", ananya.get(f"{BASE}/api/claims/{cid}").status_code, 404)
expect("other customer cannot open document", ananya.get(f"{BASE}/api/claims/{cid}/documents/bill").status_code, 404)
expect("other customer's list excludes it", cid in [c["id"] for c in ananya.get(f"{BASE}/api/claims").json()], False)
expect("owner opens document", rohan.get(f"{BASE}/api/claims/{cid}/documents/bill").status_code, 200)
expect("customer cannot decide", rohan.post(f"{BASE}/api/claims/{cid}/decision", json={"status": "approved"}).status_code, 403)
expect("customer cannot get reviewer summary", rohan.post(f"{BASE}/api/claims/{cid}/review").status_code, 403)
expect("customer insurer page redirects home", rohan.get(f"{BASE}/insurer", allow_redirects=False).headers.get("location"), "/")
expect("insurer sees claim", insurer.get(f"{BASE}/api/claims/{cid}").status_code, 200)
expect("insurer list includes it", cid in [c["id"] for c in insurer.get(f"{BASE}/api/claims").json()], True)
expect("insurer cannot create claim", insurer.post(f"{BASE}/api/claims", data={"sample": "appendix"}).status_code, 403)
expect("insurer customer page redirects", insurer.get(f"{BASE}/", allow_redirects=False).headers.get("location"), "/insurer")
expect("insurer decides", insurer.post(f"{BASE}/api/claims/{cid}/decision", json={"status": "approved", "note": "ok"}).status_code, 200)
expect("owner sees decision", rohan.get(f"{BASE}/api/claims/{cid}").json()["status"], "approved")
rohan.post(f"{BASE}/api/logout")
expect("after sign-out", rohan.get(f"{BASE}/api/claims").status_code, 401)

# One browser, two tabs: a customer and an insurer signed in at the same time.
both = requests.Session()
for key in ("ananya", "suraksha"):
    a = by_name[key]
    both.post(f"{BASE}/api/login", json={"email": a["email"], "password": a["password"]})
C, I = {"X-Portal": "customer"}, {"X-Portal": "insurer"}
expect("both: customer tab still shows customer", "Ananya Deshmukh" in both.get(f"{BASE}/").text, True)
expect("both: insurer tab shows insurer", "Suraksha Claims Desk" in both.get(f"{BASE}/insurer").text, True)
expect("both: customer tab lists only own claims", cid in [c["id"] for c in both.get(f"{BASE}/api/claims", headers=C).json()], False)
expect("both: insurer tab lists all claims", cid in [c["id"] for c in both.get(f"{BASE}/api/claims", headers=I).json()], True)
expect("both: customer tab cannot open another's claim", both.get(f"{BASE}/api/claims/{cid}", headers=C).status_code, 404)
expect("both: insurer document link works", both.get(f"{BASE}/api/claims/{cid}/documents/bill?portal=insurer&n=1").status_code, 200)
both.post(f"{BASE}/api/logout", headers=C)
expect("both: customer signed out", both.get(f"{BASE}/api/claims", headers=C).status_code, 401)
expect("both: insurer still signed in", both.get(f"{BASE}/api/claims", headers=I).status_code, 200)
expect("both: customer page now goes to insurer side", both.get(f"{BASE}/", allow_redirects=False).headers.get("location"), "/insurer")
expect("both: sign-in page still available", both.get(f"{BASE}/login", allow_redirects=False).status_code, 200)
