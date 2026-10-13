"""Dev check: a hospital bill PDF above the inline limit is read through Cloud Storage.
Builds a ~13 MB PDF (a bill table plus an incompressible image page) and reads it."""
import io
import os
import sys
import time
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.claims import service  # noqa: E402
from app.claims.schemas import Bill  # noqa: E402

S = getSampleStyleSheet()
noise = Image.frombytes("RGB", (2100, 2100), os.urandom(2100 * 2100 * 3))
png = io.BytesIO()
noise.save(png, format="PNG")
png.seek(0)

buf = io.BytesIO()
rows = [["Particulars", "Qty", "Rate (Rs)", "Amount (Rs)"], ["Room rent - twin sharing", "2", "4,000.00", "8,000.00"],
        ["Surgeon fees", "1", "30,000.00", "30,000.00"], ["Pharmacy - medicines", "1", "5,500.00", "5,500.00"],
        ["TOTAL", "", "", "43,500.00"]]
SimpleDocTemplate(buf, pagesize=A4).build([
    Paragraph("Sanjeevani Multispeciality Hospital, Nagpur", S["Title"]),
    Paragraph("FINAL INPATIENT BILL (large-file test, fictional)", S["Heading2"]),
    Paragraph("Patient: Test Patient. Diagnosis: Hernia. Procedure: Hernia repair. Room type: Twin sharing.", S["Normal"]),
    Table(rows), PageBreak(), RLImage(png, width=400, height=400),
])
data = buf.getvalue()
print(f"test PDF: {len(data) / 1024 / 1024:.1f} MB (inline limit {service.INLINE_LIMIT_BYTES / 1024 / 1024:.0f} MB)")
if len(sys.argv) > 1:  # save a copy instead, for uploading through the site
    Path(sys.argv[1]).write_bytes(data)
    sys.exit(0)

t = time.time()
bill = Bill.model_validate(service._cached("bill", data, "application/pdf"))
print(f"read in {time.time() - t:.1f}s:", bill.is_hospital_bill, bill.patient_name, "|", len(bill.items), "lines |",
      sum(i.amount for i in bill.items))
