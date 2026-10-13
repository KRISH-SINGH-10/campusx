"""Read the two documents with Gemini into the structured shapes the engine needs."""
from app.claims.schemas import Bill, Policy
from app.services import ai

BILL_PROMPT = """You are reading a hospital inpatient bill. Extract it exactly as printed.
- One entry in `items` per billed line. Do not include the total row.
- `quantity` is the number of days or units, `unit_price` the rate, `amount` the line total.
- Choose `category` from the allowed values: room_rent for any room, bed or boarding charge;
  icu for intensive care; doctor_fees for surgeon, anaesthetist or consultant fees;
  surgery_ot for operation theatre charges; implants for lenses, stents and similar;
  consumables for gloves, masks, syringes and disposables; admin_other for registration,
  admission, food, attendant and other non-medical charges.
- Do not invent lines or change any number."""

POLICY_PROMPT = """You are reading a health insurance policy wording. Extract the terms that decide
how much of a hospital bill is payable.
- Amounts are in rupees as plain numbers (5,00,000 becomes 500000).
- For every limit, give the clause number it comes from in the matching *_clause field.
- `non_payable`: one entry per group of excluded items, with short lowercase `keywords`
  that would appear on a bill line (for example "gloves", "registration", "admission", "diet", "food").
- `sublimits`: per-treatment limits, with lowercase `keywords` naming the treatment.
- `clauses`: every clause you relied on, with its number, title and exact wording.
- If a term is not in the document, leave it at its default. Do not guess."""


def read_bill(data: bytes, mime_type: str) -> Bill:
    return Bill.model_validate(ai.analyze_file(BILL_PROMPT, data, mime_type, schema=Bill, temperature=0))


def read_policy(data: bytes, mime_type: str) -> Policy:
    return Policy.model_validate(ai.analyze_file(POLICY_PROMPT, data, mime_type, schema=Policy, temperature=0))
