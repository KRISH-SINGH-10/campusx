"""Read the two documents with Gemini into the structured shapes the engine needs."""
from app.claims.schemas import Bill, Policy
from app.services import ai

BILL_PROMPT = """You are reading a document that should be a hospital bill. Extract it exactly as printed.
- First decide what the document is: set `is_hospital_bill` and describe it in `document_kind`.
  If it is not a hospital or medical bill, return an empty `items` list.
- Set `currency` to the ISO code of the amounts (INR for Indian rupees).
- One entry in `items` per billed line. Do not include the total row.
- `quantity` is the number of days or units, `unit_price` the rate, `amount` the line total.
- Choose `category` from the allowed values: room_rent for any room, bed or boarding charge;
  icu for intensive care; doctor_fees for surgeon, anaesthetist or consultant fees;
  surgery_ot for operation theatre charges; implants for lenses, stents and similar;
  consumables for gloves, masks, syringes and disposables; admin_other for registration,
  admission, food, attendant and other non-medical charges.
- Do not invent lines or change any number."""

POLICY_PROMPT = """You are reading a document that should be a health insurance policy wording. Extract
the terms that decide how much of a hospital bill is payable.
- First decide what the document is: set `is_health_policy` and describe it in `document_kind`.
  A life, term, motor or travel policy is not a health policy.
- Policy wordings often leave the sum insured to a separate schedule. If it is not stated, set
  `sum_insured` to 0; never guess it.
- A room rent or ICU limit given as a percentage of the sum insured goes in the matching
  `*_percent_of_si` field as a number (1 for 1%). Use `*_cap_per_day` only for a limit in rupees.
- `copay_percent` and `deductible` are only for amounts that apply to every claim. A co-payment or
  limit that depends on age, zone, or a named illness goes in `conditional_notes` instead.
- Quote clause wording briefly: at most two sentences per clause, and only clauses that set a limit,
  a co-payment, a deductible, a sub-limit or an exclusion of billed items.
- Amounts are in rupees as plain numbers (5,00,000 becomes 500000).
- For every limit, give the clause number it comes from in the matching *_clause field.
- `non_payable`: one entry per group of excluded items, with short lowercase `keywords`
  that would appear on a bill line (for example "gloves", "registration", "admission", "diet", "food").
- `sublimits`: per-treatment limits, with lowercase `keywords` naming the treatment.
- `clauses`: every clause you relied on, with its number, title and exact wording.
- If a term is not in the document, leave it at its default. Do not guess."""


def read_bill(data: bytes, mime_type: str, uri: str | None = None) -> Bill:
    return Bill.model_validate(
        ai.analyze_file(BILL_PROMPT, data, mime_type, schema=Bill, temperature=0, uri=uri)
    )


def read_policy(data: bytes, mime_type: str, uri: str | None = None) -> Policy:
    return Policy.model_validate(
        ai.analyze_file(POLICY_PROMPT, data, mime_type, schema=Policy, temperature=0, uri=uri)
    )
