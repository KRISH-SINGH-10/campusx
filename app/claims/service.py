"""Claim workflow: read documents (cached), decide, store, and the AI extras."""
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

from app.claims import engine, extract
from app.claims.schemas import Bill, Policy
from app.services import ai, db

log = logging.getLogger("claimclear")

CLAIMS = "claims"
EXTRACTIONS = "extractions"


def _cached(kind: str, data: bytes, mime_type: str) -> dict:
    """Reading a document takes several seconds, so remember each file by its hash."""
    key = f"{kind}-{hashlib.sha256(data).hexdigest()[:32]}"
    hit = db.get(EXTRACTIONS, key)
    if hit:
        return hit["data"]
    reader = extract.read_bill if kind == "bill" else extract.read_policy
    try:
        parsed = reader(data, mime_type).model_dump()
    except Exception as e:
        # One retry: an occasional reply fails to parse or times out.
        log.warning("reading %s failed, retrying: %s", kind, e)
        parsed = reader(data, mime_type).model_dump()
    db.put(EXTRACTIONS, key, {"data": parsed})
    return parsed


def _room_curve(bill: Bill, policy: Policy) -> list[dict]:
    """Payout at a range of room prices, for the room-choice simulator."""
    actual = engine.room_rent_per_day(bill)
    if not actual:
        return []
    cap = policy.room_rent_cap_per_day or actual
    top = int(max(actual, cap) * 1.5 // 500 * 500) + 500
    points = sorted(set(range(1000, top + 1, 500)) | {int(actual), int(cap)})
    return [{"rent": r, **engine.simulate_room(bill, policy, r)} for r in points]


def create_claim(bill_bytes: bytes, bill_mime: str, policy_bytes: bytes, policy_mime: str) -> dict:
    with ThreadPoolExecutor(max_workers=2) as pool:
        bill_job = pool.submit(_cached, "bill", bill_bytes, bill_mime)
        policy_job = pool.submit(_cached, "policy", policy_bytes, policy_mime)
        bill = Bill.model_validate(bill_job.result())
        policy = Policy.model_validate(policy_job.result())
    return db.add(
        CLAIMS,
        {
            "bill": bill.model_dump(),
            "policy": policy.model_dump(),
            "result": engine.adjudicate(bill, policy),
            "room_curve": _room_curve(bill, policy),
            "status": "submitted",
            "insurer_note": "",
        },
    )


def _deduction_summary(claim: dict) -> str:
    r = claim["result"]
    out = []
    for l in r["lines"]:
        if l["deducted"] > 0:
            ref = f" (Clause {l['clause']['ref']})" if l["clause"] else ""
            out.append(f"- {l['description']}: billed Rs {l['billed']:,.0f}, payable Rs {l['payable']:,.0f}. {l['reason']}{ref}")
    for s in r["steps"]:
        ref = f" (Clause {s['clause']['ref']})" if s["clause"] else ""
        out.append(f"- {s['label']}: Rs {s['amount']:,.0f}. {s['reason']}{ref}")
    for l in r["lines"]:
        if l["overbilling_flag"]:
            out.append(f"- Possible overbilling on {l['description']}: {l['overbilling_flag']}")
    return "\n".join(out) or "- No deductions."


def _facts(claim: dict) -> str:
    b, p, t = claim["bill"], claim["policy"], claim["result"]["totals"]
    return (
        f"Patient: {b['patient_name']}. Hospital: {b['hospital_name']}. Treatment: {b['procedure']}.\n"
        f"Insurer: {p['insurer']}. Policy: {p['policy_name']}.\n"
        f"Total billed: Rs {t['billed']:,.0f}. Payable by insurer: Rs {t['payable']:,.0f}. "
        f"Patient pays: Rs {t['you_pay']:,.0f}.\nDeductions:\n{_deduction_summary(claim)}"
    )


def _plain(prompt: str, temperature: float) -> str:
    """Generate text and drop any markdown emphasis the model adds anyway."""
    return ai.generate_text(prompt, temperature=temperature).replace("*", "")


def explain(claim: dict, language: str) -> str:
    return _plain(
        f"Explain this health insurance claim decision to the patient's family in simple {language}. "
        "Use short sentences and everyday words. Start with how much the insurer pays and how much "
        "the family pays, then give the main reasons, largest first. Keep rupee amounts as numbers. "
        "Use only the facts given. No greeting, no sign-off, under 150 words.\n\n" + _facts(claim),
        temperature=0.3,
    )


def appeal_letter(claim: dict) -> str:
    return _plain(
        "Draft a formal grievance letter from the patient to the insurer's grievance officer about this "
        "claim. Ask for a written, clause-by-clause justification of each deduction and for review of any "
        "deduction not clearly supported by the cited clause. Raise the possible overbilling items as a "
        "request for the hospital's itemised rates. Quote clause numbers exactly as given and use only the "
        "facts given; do not invent regulations, dates or policy numbers. Plain text, under 280 words, "
        "ending with the patient's name.\n\n" + _facts(claim),
        temperature=0.3,
    )
