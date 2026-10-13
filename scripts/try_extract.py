"""Dev check: extract each sample with Gemini, adjudicate, and print the totals."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.claims import engine, extract  # noqa: E402

samples = ROOT / "app" / "static" / "samples"
t = time.time()
policy = extract.read_policy((samples / "policy-arogya-shield-gold.pdf").read_bytes(), "application/pdf")
print(f"policy read in {time.time() - t:.1f}s")
print(json.dumps(policy.model_dump(exclude={"clauses"}), indent=1))
print("clauses:", [c.ref for c in policy.clauses])

for pdf in sorted(samples.glob("bill-*.pdf")):
    t = time.time()
    bill = extract.read_bill(pdf.read_bytes(), "application/pdf")
    result = engine.adjudicate(bill, policy)
    print(f"\n{pdf.name} ({time.time() - t:.1f}s) {len(bill.items)} items -> {result['totals']}")
    for l in result["lines"]:
        if l["status"] != "payable" or l["overbilling_flag"]:
            ref = l["clause"]["ref"] if l["clause"] else "-"
            print(f"   {l['status']:9} {l['description'][:38]:38} {l['billed']:>9} -> {l['payable']:>9}  cl.{ref}  {l['overbilling_flag'] or ''}")
    for s in result["steps"]:
        print(f"   step: {s['label']} -{s['amount']}")
