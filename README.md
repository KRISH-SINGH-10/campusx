# ClaimClear

Know what your health insurer will pay, and why, before you reach the billing desk.

Built by team CampusX for the Digital Campus on Google Cloud Hack Sprint (theme: FinTech).
Live at https://campusx-7ujz26ps6a-el.a.run.app

## The problem

Patients usually learn at discharge that part of their claim is not payable, with no
explanation they can check. Insurers verify each hospital bill against the policy by hand.

## What ClaimClear does

For the customer:

1. Register, then upload one or more hospital bills (PDF or photo) and the policy wording.
   Large photos are compressed in the browser before upload.
2. Get a line-by-line decision: payable, capped, reduced, or not payable, with the exact
   policy clause quoted for every deduction.
3. **Room choice simulator:** a chart and slider showing how the payout changes with the
   room chosen, including proportionate deduction.
4. **Explain it simply** and **dispute a deduction** (a grievance letter quoting the policy's
   own clauses), each in English, Hindi, or Marathi.
5. Possible-overbilling flags, and warnings when a document is the wrong kind, in another
   currency, or missing the sum insured.

For the insurer: a queue of pre-checked claims, an AI reviewer summary, the original
documents, and approve / raise query / reject. The customer sees the decision within seconds.

## How it works

| Part | Technology |
|---|---|
| Web app and API | Python, FastAPI, on **Cloud Run** (Mumbai) |
| Document reading | **Gemini 2.5 Flash on Vertex AI**, structured output |
| Decision engine | Deterministic Python rules, no AI |
| Data | **Firestore**: claims, registered users, cached document readings |
| Original documents | **Cloud Storage**, private bucket, one folder per document kind |
| Front end | Server-rendered HTML, Tailwind CSS, plain JavaScript |

Gemini only reads documents and writes explanations. The payable amount is always computed
by the rules engine, so the same bill and policy give the same decision every time, and
every rupee deducted is tied to a clause.

## Project structure

```
app/
  main.py              Routes: pages, sign-in, and the claims API
  auth.py              Accounts, password hashing, the two portals, access rules
  config.py            Project ID, model, bucket name
  demo_accounts.json   The three seeded demo accounts
  claims/
    schemas.py         The shapes Gemini fills in for a bill and a policy
    extract.py         The two prompts, and the calls that read each document
    engine.py          The decision rules (no AI)
    service.py         The workflow: read, validate, merge bills, decide, store
  services/
    ai.py              Gemini on Vertex AI
    db.py              Firestore helpers
    storage.py         Cloud Storage helpers
  templates/           base, login, register, index (customer home), claim, insurer
  static/              app.css, app.js, and the fictional sample PDFs
scripts/
  make_samples.py      Generates the sample policy and bills
  check_access.py      30 sign-in and access checks against a running app
  try_extract.py       Reads the samples and prints the decisions
  try_large_file.py    Builds a 16 MB bill to test the large-file path
deploy.ps1, run.ps1    Deploy to Cloud Run; run locally
```

## The decision rules, in order

Per bill line:

1. Matches the policy's non-payable list: not payable.
2. Room rent above the per-day limit: capped at the limit.
3. ICU charges above the per-day limit: capped.
4. Room above the limit and the policy applies proportionate deduction: doctor, surgery,
   nursing and diagnostic charges are reduced in the ratio limit / actual room rent.

Then on the total: procedure sub-limit, deductible, co-payment, and the sum insured.
A room limit written as a percentage of the sum insured is converted once the sum insured
is known, from the policy or entered by the customer.

## Data

| Where | What |
|---|---|
| Firestore `claims` | The read bill and policy, the decision, warnings, status, owner |
| Firestore `users` | Registered customers; passwords as salted PBKDF2 hashes |
| Firestore `extractions` | Cached document readings, keyed by file hash |
| Firestore `config` | The key that signs session cookies (keep it private) |
| Bucket `hospital-bills/`, `policy-documents/` | Original uploads |

## Run it

```powershell
.\run.ps1      # local, http://localhost:8765
.\deploy.ps1   # deploy to Cloud Run
python scripts\check_access.py   # access checks against the local app
```

## Limits

- The sample policy, bills, hospital, and insurer are fictional.
- The overbilling reference prices are illustrative, not an official rate list.
- The decision is an estimate to help a patient ask the right questions; the insurer's
  own assessment is final.
- Demo accounts are listed on the sign-in page for convenience. Customer and insurer
  sign-ins are separate, but two customers cannot be signed in to one browser at once.
- Reading real documents is not perfect: an unusual layout or an ambiguous policy list can
  be misread, which is why every decision shows the clause it relied on.

## Third-party software

| Library | Licence |
|---|---|
| FastAPI, Pydantic | MIT |
| Uvicorn, Starlette, Jinja2, itsdangerous | BSD-3-Clause |
| python-multipart, google-genai, google-cloud-firestore, google-cloud-storage | Apache-2.0 |
| Tailwind CSS (CDN) | MIT |
| Inter and Noto Sans Devanagari typefaces (Google Fonts) | SIL Open Font Licence 1.1 |
| ReportLab, Pillow (development scripts only) | BSD, HPND |
