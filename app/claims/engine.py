"""Deterministic claim adjudication. No AI in here: the same bill and policy
always produce the same decision, and every rupee deducted carries a clause."""
from app.claims.schemas import Bill, Policy

# Charges that are scaled down when the chosen room is above the policy cap.
PROPORTIONATE_CATEGORIES = {"doctor_fees", "surgery_ot", "nursing", "diagnostics"}

# Illustrative reference prices (rupees per unit) used only to flag possible
# overbilling. They never change the payable amount.
BENCHMARKS = {
    "paracetamol": 5,
    "saline": 120,
    "syringe": 15,
    "cbc": 400,
    "complete blood count": 400,
    "x-ray": 600,
    "ecg": 500,
    "ultrasound": 1500,
    "gloves": 30,
}
OVERBILLING_FACTOR = 1.5


def _ref(ref: str) -> str:
    """The model sometimes returns "Clause 3.1" and sometimes "3.1"."""
    return ref.lower().replace("clause", "").strip(" .:-")


def _clause(policy: Policy, ref: str | None) -> dict | None:
    if not ref:
        return None
    for c in policy.clauses:
        if _ref(c.ref) == _ref(ref):
            return {"ref": _ref(c.ref), "title": c.title, "text": c.text}
    return {"ref": _ref(ref), "title": "", "text": ""}


_GENERIC = {"fee", "fees", "charge", "charges", "and", "of", "the", "item", "items", "expense", "expenses"}


def _stems(phrase: str) -> list[str]:
    words = [w.strip(".,()-/") for w in phrase.lower().split()]
    return [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words if w and w not in _GENERIC]


def _matches(text: str, keywords: list[str]) -> bool:
    """True if every meaningful word of any keyword appears in the text
    ("registration fees" matches "Registration and admission fee")."""
    text = text.lower()
    for k in keywords:
        stems = _stems(k)
        if stems and all(s in text for s in stems):
            return True
    return False


def room_rent_per_day(bill: Bill) -> float | None:
    rooms = [i for i in bill.items if i.category == "room_rent"]
    return max((i.unit_price for i in rooms), default=None)


def adjudicate(bill: Bill, policy: Policy) -> dict:
    cap = policy.room_rent_cap_per_day
    actual_room = room_rent_per_day(bill)
    ratio = 1.0
    if policy.proportionate_deduction and cap and actual_room and actual_room > cap:
        ratio = cap / actual_room

    lines = []
    for item in bill.items:
        payable = item.amount
        status = "payable"
        reason = "Covered in full."
        clause = None

        non_payable = next(
            (n for n in policy.non_payable if _matches(item.description, n.keywords)), None
        )
        if non_payable:
            payable, status = 0.0, "excluded"
            reason = "Listed in the policy as a non-payable item."
            clause = _clause(policy, non_payable.clause_ref)
        elif item.category == "room_rent" and cap and item.unit_price > cap:
            payable, status = cap * item.quantity, "capped"
            reason = (
                f"Room rent is covered up to Rs {cap:,.0f} per day; "
                f"billed at Rs {item.unit_price:,.0f} per day."
            )
            clause = _clause(policy, policy.room_rent_clause)
        elif item.category == "icu" and policy.icu_cap_per_day and item.unit_price > policy.icu_cap_per_day:
            payable, status = policy.icu_cap_per_day * item.quantity, "capped"
            reason = (
                f"ICU charges are covered up to Rs {policy.icu_cap_per_day:,.0f} per day; "
                f"billed at Rs {item.unit_price:,.0f} per day."
            )
            clause = _clause(policy, policy.icu_clause)
        elif ratio < 1 and item.category in PROPORTIONATE_CATEGORIES:
            payable, status = item.amount * ratio, "reduced"
            reason = (
                f"Reduced to {ratio:.0%} because the room chosen is above the room rent cap "
                "(proportionate deduction)."
            )
            clause = _clause(policy, policy.proportionate_clause)

        flag = None
        for name, price in BENCHMARKS.items():
            if name in item.description.lower() and item.unit_price > price * OVERBILLING_FACTOR:
                flag = (
                    f"Billed at Rs {item.unit_price:,.0f} per unit; "
                    f"a typical price is about Rs {price:,.0f}."
                )
                break

        lines.append(
            {
                "description": item.description,
                "category": item.category,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "billed": round(item.amount, 2),
                "payable": round(payable, 2),
                "deducted": round(item.amount - payable, 2),
                "status": status,
                "reason": reason,
                "clause": clause,
                "overbilling_flag": flag,
            }
        )

    billed = sum(l["billed"] for l in lines)
    admissible = sum(l["payable"] for l in lines)
    steps = []

    context = f"{bill.procedure} {bill.diagnosis}"
    sublimit = next((s for s in policy.sublimits if _matches(context, s.keywords)), None)
    if sublimit and admissible > sublimit.limit_amount:
        steps.append(
            {
                "label": "Procedure sub-limit",
                "amount": round(admissible - sublimit.limit_amount, 2),
                "reason": f"This treatment is covered up to Rs {sublimit.limit_amount:,.0f}.",
                "clause": _clause(policy, sublimit.clause_ref),
            }
        )
        admissible = sublimit.limit_amount

    if policy.deductible and admissible > 0:
        d = min(policy.deductible, admissible)
        steps.append(
            {
                "label": "Deductible",
                "amount": round(d, 2),
                "reason": f"You pay the first Rs {policy.deductible:,.0f} of each claim.",
                "clause": _clause(policy, policy.deductible_clause),
            }
        )
        admissible -= d

    if policy.copay_percent and admissible > 0:
        c = admissible * policy.copay_percent / 100
        steps.append(
            {
                "label": f"Co-payment ({policy.copay_percent:g}%)",
                "amount": round(c, 2),
                "reason": f"You share {policy.copay_percent:g}% of the admissible amount.",
                "clause": _clause(policy, policy.copay_clause),
            }
        )
        admissible -= c

    # A sum insured of 0 means "not stated in the document", not "nothing is covered".
    if policy.sum_insured > 0 and admissible > policy.sum_insured:
        steps.append(
            {
                "label": "Sum insured limit",
                "amount": round(admissible - policy.sum_insured, 2),
                "reason": f"The policy covers up to Rs {policy.sum_insured:,.0f}.",
                "clause": None,
            }
        )
        admissible = policy.sum_insured

    payable = round(admissible, 2)
    return {
        "lines": lines,
        "steps": steps,
        "totals": {
            "billed": round(billed, 2),
            "payable": payable,
            "you_pay": round(billed - payable, 2),
            "covered_percent": round(100 * payable / billed, 1) if billed else 0,
        },
        "room": {
            "billed_per_day": actual_room,
            "cap_per_day": cap,
            "ratio": round(ratio, 4),
            "proportionate": bool(policy.proportionate_deduction),
        },
        "overbilling_count": sum(1 for l in lines if l["overbilling_flag"]),
    }


def simulate_room(bill: Bill, policy: Policy, rent_per_day: float) -> dict:
    """Re-run the decision as if the patient had chosen a room at another price."""
    changed = bill.model_copy(deep=True)
    for item in changed.items:
        if item.category == "room_rent":
            item.unit_price = rent_per_day
            item.amount = rent_per_day * item.quantity
    return adjudicate(changed, policy)["totals"]
