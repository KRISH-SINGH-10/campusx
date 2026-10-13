"""Generate the fictional sample policy and hospital bills as PDFs.
Dev-only: needs `pip install reportlab`. All names and figures are invented."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
S = getSampleStyleSheet()


def doc(name):
    return SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=16 * mm, bottomMargin=16 * mm)


def policy():
    clauses = [
        ("1.1", "Sum Insured", "The maximum amount payable under this Policy in a Policy Year is Rs 5,00,000 (Rupees Five Lakh)."),
        ("3.1", "Room Rent", "Room, boarding and nursing expenses are payable up to Rs 5,000 per day for a normal room."),
        ("3.2", "ICU Charges", "Intensive Care Unit charges are payable up to Rs 10,000 per day."),
        ("3.3", "Proportionate Deduction", "If the Insured Person is admitted in a room where the room rent exceeds the limit in Clause 3.1, all associated medical expenses including doctor fees, surgery and operation theatre charges, nursing charges and diagnostics shall be payable in the same proportion as the eligible room rent bears to the actual room rent. This shall not apply to pharmacy and implants."),
        ("4.1", "Co-payment", "A co-payment of 10% shall apply to each and every admissible claim under this Policy."),
        ("5.2", "Cataract Sub-limit", "Expenses for cataract surgery are payable up to Rs 40,000 per eye."),
        ("7.4", "Non-Medical Items", "The following items are not payable: gloves, masks, toiletries, diet and food charges, attendant charges, registration fees and admission fees."),
    ]
    story = [
        Paragraph("Suraksha General Insurance Co. Ltd.", S["Title"]),
        Paragraph("Arogya Shield Gold - Health Insurance Policy Wording", S["Heading2"]),
        Paragraph("Policy No: ASG/2026/004417 &nbsp;&nbsp; Policy period: 01 Apr 2026 to 31 Mar 2027", S["Normal"]),
        Paragraph("(Fictional sample document for demonstration.)", S["Italic"]),
        Spacer(1, 8),
    ]
    for ref, title, text in clauses:
        story.append(Paragraph(f"Clause {ref} - {title}", S["Heading4"]))
        story.append(Paragraph(text, S["Normal"]))
        story.append(Spacer(1, 4))
    doc("policy-arogya-shield-gold.pdf").build(story)


def bill(name, patient, diagnosis, procedure, room_type, admit, discharge, items):
    rows = [["Particulars", "Qty", "Rate (Rs)", "Amount (Rs)"]]
    total = 0
    for desc, qty, rate in items:
        amt = qty * rate
        total += amt
        rows.append([desc, f"{qty:g}", f"{rate:,.2f}", f"{amt:,.2f}"])
    rows.append(["TOTAL", "", "", f"{total:,.2f}"])
    t = Table(rows, colWidths=[95 * mm, 15 * mm, 30 * mm, 32 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story = [
        Paragraph("Sanjeevani Multispeciality Hospital, Nagpur", S["Title"]),
        Paragraph("FINAL INPATIENT BILL", S["Heading2"]),
        Paragraph(f"Patient: {patient}", S["Normal"]),
        Paragraph(f"Diagnosis: {diagnosis}", S["Normal"]),
        Paragraph(f"Procedure: {procedure}", S["Normal"]),
        Paragraph(f"Room type: {room_type}", S["Normal"]),
        Paragraph(f"Date of admission: {admit} &nbsp;&nbsp; Date of discharge: {discharge}", S["Normal"]),
        Paragraph("(Fictional sample document for demonstration.)", S["Italic"]),
        Spacer(1, 8),
        t,
    ]
    doc(name).build(story)


policy()

bill("bill-1-appendix-within-limits.pdf", "Ananya Deshmukh", "Acute appendicitis",
     "Laparoscopic appendectomy", "Twin sharing room", "02 Oct 2026", "05 Oct 2026", [
         ("Room rent - twin sharing", 3, 4500),
         ("Surgeon fees", 1, 35000),
         ("Operation theatre charges", 1, 18000),
         ("Anaesthetist fees", 1, 9000),
         ("Nursing charges", 3, 800),
         ("Complete blood count (CBC)", 1, 380),
         ("Ultrasound abdomen", 1, 1400),
         ("Pharmacy - medicines", 1, 6200),
     ])

bill("bill-2-gallbladder-room-upgrade.pdf", "Rohan Kulkarni", "Gallstones (cholelithiasis)",
     "Laparoscopic cholecystectomy", "Deluxe single room", "06 Oct 2026", "10 Oct 2026", [
         ("Room rent - deluxe single room", 4, 8000),
         ("Surgeon fees", 1, 45000),
         ("Operation theatre charges", 1, 22000),
         ("Anaesthetist fees", 1, 11000),
         ("Nursing charges", 4, 1200),
         ("Complete blood count (CBC)", 2, 950),
         ("Ultrasound abdomen", 1, 1500),
         ("Pharmacy - medicines", 1, 9400),
         ("Paracetamol 500mg tablet", 20, 18),
         ("Surgical gloves", 12, 60),
         ("Registration and admission fee", 1, 1500),
         ("Diet and food charges", 4, 600),
     ])

bill("bill-3-cataract-sublimit.pdf", "Sunita Wankhede", "Senile cataract, right eye",
     "Cataract surgery (phacoemulsification) with lens implant", "Day care", "08 Oct 2026", "08 Oct 2026", [
         ("Room rent - day care bed", 1, 3000),
         ("Surgeon fees", 1, 28000),
         ("Operation theatre charges", 1, 12000),
         ("Intraocular lens implant", 1, 16000),
         ("Pharmacy - eye drops and medicines", 1, 2400),
         ("Registration and admission fee", 1, 600),
     ])

print("written:", *[p.name for p in sorted(OUT.glob("*.pdf"))], sep="\n  ")
