"""Calibration script for BERT phishing model across real emails."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Email
from app.db.session import SessionLocal
from app.phishing.detector import detect_phishing_for_email
from app.phishing.providers.bert_phishing import evaluate_bert_phishing

# Force utf-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

db = SessionLocal()
emails = db.query(Email).filter(Email.is_demo == False).all()
print(f"Total real emails: {len(emails)}")

scores = []
latencies = []

for e in emails:
    t0 = time.perf_counter()
    res = evaluate_bert_phishing(e)
    lat = (time.perf_counter() - t0) * 1000.0
    scores.append((e, res.score, lat))
    latencies.append(lat)

scores.sort(key=lambda x: x[1], reverse=True)
avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

print(f"\nAverage BERT latency: {avg_lat:.2f} ms per email")
print("\nScore thresholds breakdown across 75 real emails:")
for thresh in [0.90, 0.85, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30]:
    cnt = sum(1 for _, s, _ in scores if s >= thresh)
    print(f"  BERT score >= {thresh:.2f}: {cnt}/{len(emails)} ({cnt/len(emails):.1%})")

print("\nTop 10 highest BERT scores on real emails:")
for e, s, l in scores[:10]:
    subj = (e.subject or "")[:45].encode("ascii", "replace").decode("ascii")
    sndr = (e.sender or "")[:35].encode("ascii", "replace").decode("ascii")
    print(f"  Score: {s:.4f} ({l:.1f}ms) | Subj: {subj:<45} | From: {sndr}")

print("\n" + "="*70)
print("USER SELF-SENT EMAILS EVALUATION (IDs 46 & 47):")
print("="*70)
self_sent = [e for e in emails if e.id in (46, 47)]
for e in self_sent:
    print(f"\n--- Email ID: {e.id} ---")
    print(f"Subject: {e.subject}")
    print(f"Sender: {e.sender}")
    print(f"Body: {e.body_text!r}")
    
    # Run full phishing detection pipeline
    fusion = detect_phishing_for_email(e, db=db, force_refresh=True)
    print(f"Final Fused Score: {fusion.fraud_score:.1%} | Label: {fusion.fraud_label}")
    print(f"Reason: {fusion.fraud_reason}")
    print("Layer Breakdown:")
    for lyr in fusion.layers_data:
        avail_str = "Available" if lyr.get("available") else "Unavailable"
        print(f"  - {lyr.get('name')}: score={lyr.get('score', 0.0):.1%} ({avail_str}) | reason={lyr.get('reason')}")
    print("Evidence:")
    for ev in fusion.fraud_evidence:
        print(f"  * {ev}")

db.close()
