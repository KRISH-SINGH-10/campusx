# ClaimClear

Know what your health insurer will pay, and why, before you reach the billing desk.

Built by team CampusX for the Digital Campus on Google Cloud Hack Sprint (theme: FinTech).

## The problem

Patients usually learn at discharge that part of their claim is not payable, with no
explanation they can check. Insurers verify each hospital bill against the policy by hand.

## What ClaimClear does

1. Reads the hospital bill and the policy wording (PDF or photo).
2. Decides line by line what is payable, capped, reduced, or not payable, and quotes the
   exact policy clause behind every deduction.
3. Flags lines priced well above typical rates as possible overbilling.
4. **Room choice simulator:** shows how the payout changes with the room chosen, including
   the proportionate deduction most patients have never heard of.
5. **Explain it simply:** the decision in plain English, Hindi, or Marathi.
6. **Dispute a deduction:** drafts a grievance letter that quotes the policy's own clauses.
7. **Insurer view:** a queue of pre-checked claims with approve, query, or reject.

## How it works

| Part | Technology |
|---|---|
| Web app and API | FastAPI on **Cloud Run** (Mumbai) |
| Document reading | **Gemini on Vertex AI**, structured output |
| Decision engine | Deterministic Python rules (`app/claims/engine.py`), no AI |
| Data | **Firestore** (claims, cached document readings) |

Gemini only reads documents and writes explanations. The payable amount is always computed
by the rules engine, so the same bill and policy give the same decision every time.

## Run it

```powershell
.\run.ps1      # local, http://localhost:8765
.\deploy.ps1   # deploy to Cloud Run
```

## Limits

- The sample policy, bills, hospital, and insurer are fictional.
- The overbilling reference prices are illustrative, not an official rate list.
- The decision is an estimate to help a patient ask the right questions; the insurer's
  own assessment is final.

## Third-party software

| Library | Licence |
|---|---|
| FastAPI, Uvicorn, Jinja2, Pydantic | MIT / BSD-3-Clause |
| Tailwind CSS (CDN) | MIT |
| Inter typeface (Google Fonts) | SIL Open Font Licence 1.1 |
| google-genai, google-cloud-firestore | Apache-2.0 |
| ReportLab (sample PDF generation only) | BSD |
