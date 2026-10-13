"""Claim workflow: read documents (cached), decide, store, and the AI extras."""
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

from app import config
from app.claims import engine, extract
from app.claims.schemas import Bill, Policy
from app.services import ai, db, storage

log = logging.getLogger("claimclear")

CLAIMS = "claims"
EXTRACTIONS = "extractions"
INLINE_LIMIT_BYTES = 7 * 1024 * 1024


class ClaimInputError(Exception):
    """The documents were read, but they are not what the check needs. The message is shown to the user."""


def _cached(kind: str, data: bytes, mime_type: str) -> dict:
    """Reading a document takes several seconds, so remember each file by its hash."""
    key = f"{kind}-v3-{hashlib.sha256(data).hexdigest()[:32]}"
    hit = db.get(EXTRACTIONS, key)
    if hit:
        return hit["data"]
    reader = extract.read_bill if kind == "bill" else extract.read_policy
    # Big files go to Gemini by Cloud Storage reference; inline requests have a size ceiling.
    uri = None
    if len(data) > INLINE_LIMIT_BYTES:
        name = _store(kind, data, mime_type)
        uri = f"gs://{config.DOCS_BUCKET}/{name}" if name else None
    try:
        parsed = reader(data, mime_type, uri).model_dump()
    except Exception as e:
        # One retry: an occasional reply fails to parse or times out.
        log.warning("reading %s failed, retrying: %s", kind, e)
        parsed = reader(data, mime_type, uri).model_dump()
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


# Each kind of document has its own folder in the bucket.
_FOLDER = {"bill": "hospital-bills", "policy": "policy-documents"}
_EXT = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _store(kind: str, data: bytes, mime: str) -> str | None:
    """Keep an original so the insurer can open it. A storage failure must not block the decision."""
    name = f"{_FOLDER[kind]}/{hashlib.sha256(data).hexdigest()[:32]}.{_EXT.get(mime, 'bin')}"
    try:
        return storage.save(name, data, mime)
    except Exception as e:
        log.warning("storing %s failed: %s", kind, e)
        return None


def _merge_bills(bills: list[Bill]) -> tuple[Bill, list[int]]:
    """One hospital stay can come as several bills (interim, pharmacy, final). Combine
    their lines into one bill, remembering which document each line came from."""
    merged = bills[0].model_copy(deep=True)
    sources = [1] * len(merged.items)
    for n, extra in enumerate(bills[1:], start=2):
        merged.items.extend(extra.items)
        sources.extend([n] * len(extra.items))
        for field in ("patient_name", "hospital_name", "diagnosis", "procedure", "room_type",
                      "admission_date", "discharge_date"):
            if not getattr(merged, field):
                setattr(merged, field, getattr(extra, field))
    return merged, sources


def reviewer_summary(claim: dict) -> str:
    return _plain(
        "You are assisting a health insurance claims reviewer. From the facts below, write exactly three "
        "short bullet points starting with '- ': (1) the single largest driver of the deduction, with its "
        "amount; (2) anything the reviewer should verify with the hospital, such as possible overbilling; "
        "(3) whether the recommended payable amount follows from the cited clauses. Use only the facts "
        "given. Under 80 words in total.\n\n" + _facts(claim),
        temperature=0.2,
    )


def _apply_sum_insured(policy: Policy, sum_insured: float | None) -> None:
    """The sum insured usually sits in the policy schedule, not the wording, so the customer
    can supply it. Limits written as a percentage of it are then turned into rupees."""
    if sum_insured:
        policy.sum_insured = sum_insured
    if policy.sum_insured > 0:
        if not policy.room_rent_cap_per_day and policy.room_rent_cap_percent_of_si:
            policy.room_rent_cap_per_day = policy.sum_insured * policy.room_rent_cap_percent_of_si / 100
        if not policy.icu_cap_per_day and policy.icu_cap_percent_of_si:
            policy.icu_cap_per_day = policy.sum_insured * policy.icu_cap_percent_of_si / 100


def _warnings(bill: Bill, policy: Policy) -> list[str]:
    """Things the reader should know before trusting the numbers."""
    out = []
    if policy.sum_insured <= 0:
        pending = policy.room_rent_cap_percent_of_si or policy.icu_cap_percent_of_si
        out.append(
            "The policy document does not state your sum insured (it is usually in the policy schedule)"
            + (
                ", and this policy limits room rent as a percentage of it, so the room limit could "
                "not be applied. "
                if pending
                else ". "
            )
            + "Check again with your sum insured filled in for an accurate result."
        )
    no_terms = not (
        policy.room_rent_cap_per_day
        or policy.room_rent_cap_percent_of_si
        or policy.icu_cap_per_day
        or policy.copay_percent
        or policy.deductible
        or policy.non_payable
        or policy.sublimits
    )
    if no_terms:
        out.append(
            "No limits, co-payment or exclusions were found in the policy document, so nothing was "
            "deducted. Upload the full policy wording (not the summary or schedule) for a real check."
        )
    if bill.currency and bill.currency.upper() != "INR":
        out.append(
            f"The bill appears to be in {bill.currency.upper()}, not Indian rupees. "
            "Amounts are shown as printed and may not be comparable with the policy limits."
        )
    printed = sum(i.amount for i in bill.items)
    computed = sum(i.quantity * i.unit_price for i in bill.items)
    if printed and abs(printed - computed) / printed > 0.02:
        out.append(
            "Some line totals on the bill do not equal quantity times rate. "
            "Check the highlighted amounts against the original bill."
        )
    return out


def create_claim(
    bill_docs: list[tuple[bytes, str]],
    policy_doc: tuple[bytes, str],
    owner: str,
    submitted_by: str,
    sample_title: str | None = None,
    sum_insured: float | None = None,
) -> dict:
    """bill_docs: one or more (bytes, mime type) hospital bills for the same stay."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        bill_jobs = [pool.submit(_cached, "bill", data, mime) for data, mime in bill_docs]
        policy_job = pool.submit(_cached, "policy", *policy_doc)
        bill_store = [pool.submit(_store, "bill", data, mime) for data, mime in bill_docs]
        policy_store = pool.submit(_store, "policy", *policy_doc)
        bills = [Bill.model_validate(j.result()) for j in bill_jobs]
        policy = Policy.model_validate(policy_job.result())
        documents = {
            "bills": [name for name in (j.result() for j in bill_store) if name],
            "policy": policy_store.result(),
        }
    for n, b in enumerate(bills, start=1):
        if not b.is_hospital_bill or not b.items:
            which = f"Bill file {n}" if len(bills) > 1 else "The bill file"
            kind = f" It looks like: {b.document_kind}." if b.document_kind else ""
            raise ClaimInputError(f"{which} does not look like a hospital bill.{kind}")
    if not policy.is_health_policy:
        kind = f" It looks like: {policy.document_kind}." if policy.document_kind else ""
        raise ClaimInputError(
            f"The policy file is not a health insurance policy.{kind} Upload your health policy wording."
        )
    bill, sources = _merge_bills(bills)
    _apply_sum_insured(policy, sum_insured)
    extra_warnings = []
    patients = {b.patient_name.strip().lower() for b in bills if b.patient_name.strip()}
    if len(patients) > 1:
        extra_warnings.append(
            "The bills name different patients. A claim should cover one patient's hospital stay; "
            "check that every bill belongs to this claim."
        )
    if sample_title:
        # A sample bill is a worked example, so it is filed under the signed-in customer's own name.
        bill.patient_name = submitted_by
    return db.add(
        CLAIMS,
        {
            "title": sample_title or bill.procedure or bill.diagnosis or "Hospital claim",
            "sample": bool(sample_title),
            "submitted_by": submitted_by,
            "warnings": extra_warnings + _warnings(bill, policy),
            "notes": policy.conditional_notes[:5],
            "documents": documents,
            "bill_count": len(bills),
            "line_sources": sources,
            "bill": bill.model_dump(),
            "policy": policy.model_dump(),
            "result": engine.adjudicate(bill, policy),
            "room_curve": _room_curve(bill, policy),
            "owner": owner,
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


def appeal_letter(claim: dict, language: str = "English") -> str:
    return _plain(
        f"Write the whole letter in {language}; keep names, clause numbers and rupee amounts as they are. "
        "Draft a formal grievance letter from the patient to the insurer's grievance officer about this "
        "claim. Ask for a written, clause-by-clause justification of each deduction and for review of any "
        "deduction not clearly supported by the cited clause. Raise the possible overbilling items as a "
        "request for the hospital's itemised rates. Quote clause numbers exactly as given and use only the "
        "facts given; do not invent regulations, dates or policy numbers. Plain text, under 280 words, "
        "ending with the patient's name.\n\n" + _facts(claim),
        temperature=0.3,
    )
