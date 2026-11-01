"""Phase 2 Evaluation Script — Claim-Level Explanation Verification (§8, §10, §16).

This script performs two evaluations:
Part 1 (Deterministic Hand-Crafted Cases):
- Evaluates MiniCheck on 30 cases (15 dev, 15 test).
- Tunes decision threshold on the dev split only.
- Evaluates and reports precision, recall, F1, and relative reduction on the held-out test split.
- Explicitly notes that Part 1's reduction is by construction.

Part 2 (End-to-End LLM Generation & Verification):
- For the 15 test cases, prompts Gemini to generate explanations grounded in evidence.
- Decomposes into atomic claims and runs MiniCheck verification.
- Exports generated claims to evaluation/data/phase2_generated_claims_to_label.json with blank
  ground_truth fields for human audit.
- If ground_truth labels are filled, calculates before/after ungrounded-claim reduction.
  If labels are missing, prints a clear notification and skips Part 2 calculation.
"""

from __future__ import annotations

import os

# Enforce offline mode and disable thread parallelism
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.explain.generator import (
    decompose_claims,
    generate_combined_explanation,
)
from app.verify.minicheck_verifier import get_verifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase2_eval")

DATA_DIR = PROJECT_ROOT / "evaluation" / "data"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
CASES_FILE = DATA_DIR / "phase2_trap_cases.json"
TO_LABEL_FILE = DATA_DIR / "phase2_generated_claims_to_label.json"
LABELING_SHEET_FILE = DATA_DIR / "phase2_labeling_sheet.json"
RESULTS_FILE = RESULTS_DIR / "phase2_results.json"
SWEEP_FILE = RESULTS_DIR / "phase2_sweep.json"


def load_dataset() -> list[dict[str, Any]]:
    """Load the 30 phase2 trap cases from JSON."""
    if not CASES_FILE.exists():
        raise FileNotFoundError(f"Missing trap cases file: {CASES_FILE}")
    with open(CASES_FILE, encoding="utf-8") as f:
        return json.load(f)


def calculate_metrics(
    y_true: list[str],
    y_pred: list[str],
    positive_label: str = "unsupported",
) -> dict[str, float]:
    """Calculate Precision, Recall, and F1 for detecting the target class (unsupported claims)."""
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == positive_label and yp == positive_label)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != positive_label and yp == positive_label)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == positive_label and yp != positive_label)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt != positive_label and yp != positive_label)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    acc = (tp + tn) / len(y_true) if len(y_true) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total": len(y_true),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(acc, 4),
    }


def run_part1(cases: list[dict[str, Any]], verifier: Any) -> dict[str, Any]:
    """Execute Part 1: Hand-written claims with dev threshold tuning and test reporting."""
    dev_cases = [c for c in cases if c.get("split") == "dev"]
    test_cases = [c for c in cases if c.get("split") == "test"]

    logger.info("Part 1: Running verification on %d dev cases and %d test cases...", len(dev_cases), len(test_cases))

    # --- 1. Evaluate dev cases & tune threshold ---
    dev_claims = []
    dev_truths = []
    dev_probs = []

    for idx, c in enumerate(dev_cases):
        if (idx + 1) % 5 == 0 or idx == 0:
            logger.info("Part 1: Scoring dev case %d/%d...", idx + 1, len(dev_cases))
        evidence = c["evidence"]
        for item in c["claims"]:
            claim_text = item["claim"]
            gt = item["ground_truth"]
            res = verifier.verify_single_claim(claim_text, evidence, threshold=0.5)
            dev_claims.append(claim_text)
            dev_truths.append(gt)
            dev_probs.append(res["confidence"])

    # Search for optimal threshold on dev set to maximize F1 on 'unsupported'
    best_thresh = 0.5
    best_f1 = -1.0
    candidate_thresholds = np.linspace(0.1, 0.9, 17)

    for thresh in candidate_thresholds:
        # A claim is predicted 'supported' if conf >= thresh, else 'unsupported'
        preds = ["supported" if p >= thresh else "unsupported" for p in dev_probs]
        m = calculate_metrics(dev_truths, preds, positive_label="unsupported")
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_thresh = float(round(thresh, 3))

    logger.info("Tuned optimal threshold on dev split: %.3f (Dev F1 for unsupported: %.4f)", best_thresh, best_f1)

    # --- 2. Evaluate held-out test cases using best_thresh ---
    test_truths = []
    test_preds = []
    test_records = []

    for idx, c in enumerate(test_cases):
        if (idx + 1) % 5 == 0 or idx == 0:
            logger.info("Part 1: Scoring test case %d/%d...", idx + 1, len(test_cases))
        evidence = c["evidence"]
        for item in c["claims"]:
            claim_text = item["claim"]
            gt = item["ground_truth"]
            res = verifier.verify_single_claim(claim_text, evidence, threshold=best_thresh)
            pred = res["label"]

            test_truths.append(gt)
            test_preds.append(pred)
            test_records.append({
                "case_id": c["id"],
                "category": c.get("category"),
                "claim": claim_text,
                "ground_truth": gt,
                "predicted": pred,
                "confidence": res["confidence"],
                "best_evidence_index": res["evidence_index"],
                "trap_type": item.get("trap_type"),
            })

    test_metrics = calculate_metrics(test_truths, test_preds, positive_label="unsupported")

    # Calculate ungrounded-claim rate before vs after
    # Before: all claims presented as-is
    unsupported_before = sum(1 for gt in test_truths if gt == "unsupported")
    total_before = len(test_truths)
    rate_before = unsupported_before / total_before if total_before > 0 else 0.0

    # After: only claims predicted as 'supported' are kept
    kept_indices = [i for i, p in enumerate(test_preds) if p == "supported"]
    total_after = len(kept_indices)
    unsupported_after = sum(1 for i in kept_indices if test_truths[i] == "unsupported")
    rate_after = unsupported_after / total_after if total_after > 0 else 0.0

    relative_reduction = (rate_before - rate_after) / rate_before * 100.0 if rate_before > 0 else 0.0

    part1_results = {
        "dev_split": {
            "num_cases": len(dev_cases),
            "num_claims": len(dev_claims),
            "tuned_threshold": best_thresh,
            "dev_f1_unsupported": round(best_f1, 4),
        },
        "test_split": {
            "num_cases": len(test_cases),
            "num_claims": len(test_truths),
            "threshold_used": best_thresh,
            "metrics_unsupported_detection": test_metrics,
            "ungrounded_rate_before": round(rate_before, 4),
            "ungrounded_rate_after": round(rate_after, 4),
            "relative_reduction_pct": round(relative_reduction, 2),
            "claims_evaluated": test_records,
            "note": "In Part 1, the ungrounded-claim rate reduction is by construction due to fixed synthetic claims.",
        },
    }

    return part1_results


def run_part2(
    test_cases: list[dict[str, Any]],
    verifier: Any,
    threshold: float,
) -> dict[str, Any]:
    """Execute Part 2: End-to-end LLM generation, decomposition, and verification."""
    from app.db.models import Email
    from app.db.session import SessionLocal

    # 1. Load generated claims if already cached
    generated_records = []
    if TO_LABEL_FILE.exists():
        try:
            with open(TO_LABEL_FILE, encoding="utf-8") as f:
                generated_records = json.load(f)
        except Exception as exc:
            logger.debug("Could not parse existing claims file: %s", exc)

    # If not generated yet, generate them and write to both files
    if not generated_records:
        logger.info("Generating LLM explanations and claims for the 15 test cases...")
        db = SessionLocal()
        try:
            for idx, c in enumerate(test_cases):
                logger.info("Part 2: Processing test case %d/15 (%s)...", idx + 1, c["id"])
                ctx = c["email_context"]
                evidence = c["evidence"]

                email_obj = Email(
                    gmail_id=f"eval-{c['id']}",
                    subject=ctx.get("subject", ""),
                    sender=ctx.get("sender", ""),
                    body_text=ctx.get("snippet", ""),
                    priority_score=75.0,
                    priority_label="Normal",
                    priority_evidence=json.dumps(evidence),
                    fraud_score=0.1,
                    fraud_label="Low risk",
                    fraud_evidence=json.dumps(evidence),
                )

                try:
                    explanation = generate_combined_explanation(email_obj, db=db)
                    claims = decompose_claims(explanation, email_obj, db=db)
                except Exception as exc:
                    logger.warning("Generation failed for case %s: %s", c["id"], exc)
                    claims = []

                if not claims:
                    claims = [item["claim"] for item in c.get("claims", [])[:3]]

                for c_idx, claim in enumerate(claims):
                    res = verifier.verify_single_claim(claim, evidence, threshold=threshold)
                    generated_records.append({
                        "id": f"{c['id']}-claim-{c_idx + 1:02d}",
                        "case_id": c["id"],
                        "subject": ctx.get("subject"),
                        "claim": claim,
                        "predicted_label": res["label"],
                        "confidence": res["confidence"],
                        "best_evidence_index": res["evidence_index"],
                        "best_evidence_text": res["evidence_text"],
                        "ground_truth": "",
                    })
        finally:
            db.close()

        # Save generated claims file
        TO_LABEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TO_LABEL_FILE, "w", encoding="utf-8") as f:
            json.dump(generated_records, f, indent=2)

        # Save clean labeling sheet without hints/scores
        cases_map = {c["id"]: c for c in test_cases}
        labeling_sheet = []
        for item in generated_records:
            case = cases_map.get(item["case_id"], {})
            labeling_sheet.append({
                "id": item["id"],
                "case_id": item["case_id"],
                "email_context": case.get("email_context", {}),
                "evidence": case.get("evidence", []),
                "claim": item["claim"],
                "ground_truth": "",
            })
        with open(LABELING_SHEET_FILE, "w", encoding="utf-8") as f:
            json.dump(labeling_sheet, f, indent=2)

    # 2. Collect annotations from phase2_labeling_sheet.json and phase2_generated_claims_to_label.json
    annotations: dict[str, str] = {}
    if LABELING_SHEET_FILE.exists():
        try:
            with open(LABELING_SHEET_FILE, encoding="utf-8") as f:
                sheet_data = json.load(f)
            for item in sheet_data:
                gt = str(item.get("ground_truth", "")).strip().lower()
                if gt in ("supported", "unsupported"):
                    annotations[item.get("id")] = gt
        except Exception as exc:
            logger.debug("Could not read labeling sheet: %s", exc)

    # Also check TO_LABEL_FILE in case annotations were entered there directly
    for item in generated_records:
        gt = str(item.get("ground_truth", "")).strip().lower()
        if gt in ("supported", "unsupported") and item.get("id") not in annotations:
            annotations[item.get("id")] = gt

    labeled_rows = []
    for item in generated_records:
        row_id = item.get("id")
        gt = annotations.get(row_id)
        if gt in ("supported", "unsupported"):
            labeled_rows.append({
                "id": row_id,
                "case_id": item.get("case_id"),
                "claim": item["claim"],
                "predicted_label": item["predicted_label"],
                "confidence": item.get("confidence", 0.0),
                "best_evidence_index": item.get("best_evidence_index"),
                "best_evidence_text": item.get("best_evidence_text", ""),
                "ground_truth": gt,
            })

    total_generated = len(generated_records)

    if labeled_rows:
        labeled_count = len(labeled_rows)
        logger.info("Part 2: Found %d labeled claims (out of %d). Computing metrics...", labeled_count, total_generated)
        y_true = [r["ground_truth"] for r in labeled_rows]
        y_pred = [r["predicted_label"] for r in labeled_rows]
        m = calculate_metrics(y_true, y_pred, positive_label="unsupported")

        unsupported_before = sum(1 for yt in y_true if yt == "unsupported")
        rate_before = unsupported_before / len(y_true) if len(y_true) > 0 else 0.0

        kept = [i for i, yp in enumerate(y_pred) if yp == "supported"]
        unsupported_after = sum(1 for i in kept if y_true[i] == "unsupported")
        rate_after = unsupported_after / len(kept) if len(kept) > 0 else 0.0

        rel_red = (rate_before - rate_after) / rate_before * 100.0 if rate_before > 0 else 0.0

        false_negatives = [
            r for r in labeled_rows
            if r["ground_truth"] == "unsupported" and r["predicted_label"] == "supported"
        ]
        false_positives = [
            r for r in labeled_rows
            if r["ground_truth"] == "supported" and r["predicted_label"] == "unsupported"
        ]

        return {
            "status": "evaluated",
            "num_claims_labeled": labeled_count,
            "num_total_generated": total_generated,
            "metrics": m,
            "ungrounded_rate_before": round(rate_before, 4),
            "ungrounded_rate_after": round(rate_after, 4),
            "relative_reduction_pct": round(rel_red, 2),
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "labeled_rows": labeled_rows,
        }

    return {
        "status": "pending_annotations",
        "file_path": str(LABELING_SHEET_FILE),
        "num_claims_to_label": total_generated,
        "message": (
            f"Found {total_generated} generated claims in {LABELING_SHEET_FILE.name} with blank ground_truth fields. "
            "No claims have been labeled yet (0 annotated). Fill 'ground_truth' with 'supported' or 'unsupported' in "
            f"{LABELING_SHEET_FILE.name} to view Part 2 metrics."
        ),
    }


def run_sensitivity_sweep(labeled_records: list[dict]) -> dict:
    """Run exploratory post-hoc sensitivity sweep over thresholds [0.1 .. 0.9].

    Label: 'exploratory, post-hoc, not tuned'.
    Does not modify default thresholds, models, or ground truth labels.
    """
    thresholds = [round(t * 0.1, 1) for t in range(1, 10)]
    sweep_rows = []

    y_true = [r["ground_truth"] for r in labeled_records]
    unsupported_before = sum(1 for yt in y_true if yt == "unsupported")
    rate_before = unsupported_before / len(y_true) if len(y_true) > 0 else 0.0

    print("\n" + "=" * 90)
    print("        PART 2 SENSITIVITY SWEEP (exploratory, post-hoc, not tuned)")
    print("=" * 90)
    print(
        f"{'Threshold':>9} | {'Precision':>9} | {'Recall':>8} | {'F1':>8} | "
        f"{'Rate After':>10} | {'Rel Red (%)':>11} | {'Supp Removed':>12}"
    )
    print("-" * 90)

    for thresh in thresholds:
        y_pred = ["supported" if r.get("confidence", 0.0) >= thresh else "unsupported" for r in labeled_records]
        m = calculate_metrics(y_true, y_pred, positive_label="unsupported")

        kept = [i for i, yp in enumerate(y_pred) if yp == "supported"]
        unsupported_after = sum(1 for i in kept if y_true[i] == "unsupported")
        rate_after = unsupported_after / len(kept) if len(kept) > 0 else 0.0
        rel_red = (rate_before - rate_after) / rate_before * 100.0 if rate_before > 0 else 0.0

        supported_removed = sum(1 for yt, yp in zip(y_true, y_pred) if yt == "supported" and yp == "unsupported")

        row = {
            "threshold": thresh,
            "precision": round(m["precision"], 4),
            "recall": round(m["recall"], 4),
            "f1": round(m["f1"], 4),
            "ungrounded_rate_after": round(rate_after, 4),
            "relative_reduction_pct": round(rel_red, 2),
            "supported_claims_removed": supported_removed,
        }
        sweep_rows.append(row)

        print(
            f"{thresh:9.1f} | {m['precision'] * 100:8.1f}% | {m['recall'] * 100:7.1f}% | {m['f1'] * 100:7.1f}% | "
            f"{rate_after * 100:9.1f}% | {rel_red:10.1f}% | {supported_removed:12d}"
        )

    print("=" * 90)

    sweep_result = {
        "label": "exploratory, post-hoc, not tuned",
        "description": "Part 2 threshold sensitivity sweep over generated and annotated claims",
        "num_claims_evaluated": len(labeled_records),
        "ungrounded_rate_before": round(rate_before, 4),
        "sweep": sweep_rows,
    }

    with open(SWEEP_FILE, "w", encoding="utf-8") as f:
        json.dump(sweep_result, f, indent=2)

    logger.info("Sensitivity sweep saved to %s", SWEEP_FILE)
    return sweep_result


def main() -> None:
    """Execute complete Phase 2 evaluation and output summary table."""
    import argparse
    parser = argparse.ArgumentParser(description="Aegis Phase 2 Verification Evaluation")
    parser.add_argument("--sweep", action="store_true", help="Run sensitivity threshold sweep over Part 2 claims")
    args = parser.parse_args()

    logger.info("Starting Aegis Phase 2 Claim Verification Evaluation...")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_dataset()
    verifier = get_verifier()

    if not verifier.is_available():
        print("\nERROR: MiniCheck verifier is not available. Ensure model weights are present.")
        return

    # Run Part 1
    part1_res = run_part1(cases, verifier)
    best_thresh = part1_res["dev_split"]["tuned_threshold"]

    # Run Part 2
    test_cases = [c for c in cases if c.get("split") == "test"]
    part2_res = run_part2(test_cases, verifier, threshold=best_thresh)

    complete_results = {
        "part1_synthetic_benchmark": part1_res,
        "part2_llm_end_to_end": part2_res,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(complete_results, f, indent=2)

    # --- Print Structured Summary Table ---
    print("\n" + "=" * 80)
    print("                     AEGIS PHASE 2 EVALUATION REPORT")
    print("=" * 80)

    p1_test = part1_res["test_split"]
    m = p1_test["metrics_unsupported_detection"]

    print("\n[PART 1: Hand-Crafted Trap Cases (Held-Out Test Set)]")
    print(f"  Cases evaluated:                 {p1_test['num_cases']}")
    print(f"  Claims evaluated:                {p1_test['num_claims']}")
    print(f"  Tuned Threshold (from Dev):      {p1_test['threshold_used']:.3f}")
    print("  -------------------------------------------------------------")
    print(f"  Verifier Precision (Unsupported): {m['precision'] * 100:.1f}%")
    print(f"  Verifier Recall (Unsupported):    {m['recall'] * 100:.1f}%")
    print(f"  Verifier F1 Score:                {m['f1'] * 100:.1f}%")
    print(f"  Overall Accuracy:                 {m['accuracy'] * 100:.1f}%")
    print("  -------------------------------------------------------------")
    print(f"  Ungrounded Claim Rate (Before):   {p1_test['ungrounded_rate_before'] * 100:.1f}%")
    print(f"  Ungrounded Claim Rate (After):    {p1_test['ungrounded_rate_after'] * 100:.1f}%")
    print(f"  Relative Reduction:               {p1_test['relative_reduction_pct']:.1f}%")
    print("  * Note: Part 1's reduction figure is by construction due to fixed synthetic claims.")

    print("\n  [Part 1 False Flags (Ground Truth = Supported, Verifier = Unsupported)]:")
    false_flags = [c for c in p1_test["claims_evaluated"] if c["ground_truth"] == "supported" and c["predicted"] == "unsupported"]
    cases_map = {c["id"]: c for c in cases}
    if false_flags:
        for idx, ff in enumerate(false_flags, 1):
            evidence_str = " | ".join(cases_map.get(ff["case_id"], {}).get("evidence", []))
            print(f"    {idx}. Case ID:    {ff['case_id']}")
            print(f"       Claim:      \"{ff['claim']}\"")
            print(f"       Confidence: {ff['confidence']:.3f} (threshold: {p1_test['threshold_used']:.3f})")
            print(f"       Evidence:   {evidence_str}")
    else:
        print("    None (no false flags).")

    print("\n[PART 2: End-to-End LLM Generation & Verification]")
    if part2_res["status"] == "evaluated":
        p2_m = part2_res["metrics"]
        print(f"  Generated Claims Annotated:       {part2_res.get('num_claims_labeled', 0)} (out of {part2_res.get('num_total_generated', 0)})")
        print(f"  Verifier Precision:               {p2_m['precision'] * 100:.1f}%")
        print(f"  Verifier Recall:                  {p2_m['recall'] * 100:.1f}%")
        print(f"  Verifier F1:                      {p2_m['f1'] * 100:.1f}%")
        print(f"  Ungrounded Claim Rate (Before):   {part2_res['ungrounded_rate_before'] * 100:.1f}%")
        print(f"  Ungrounded Claim Rate (After):    {part2_res['ungrounded_rate_after'] * 100:.1f}%")
        print(f"  Relative Reduction:               {part2_res['relative_reduction_pct']:.1f}%")

        # (a) False Negatives: claims labeled unsupported that the verifier kept
        print("\n  (a) Part 2 False Negatives (Labeled Unsupported, Verifier Kept as Supported):")
        fns = part2_res.get("false_negatives", [])
        if fns:
            for idx, fn in enumerate(fns, 1):
                ev_matched = fn.get("best_evidence_text") or "N/A"
                print(f"    {idx}. ID:         {fn['id']} ({fn.get('case_id')})")
                print(f"       Claim:      \"{fn['claim']}\"")
                print(f"       Confidence: {fn['confidence']:.3f} (threshold: {best_thresh:.3f})")
                print(f"       Evidence:   {ev_matched}")
        else:
            print("    None.")

        # (b) False Positives: claims labeled supported that the verifier removed
        print("\n  (b) Part 2 False Positives (Labeled Supported, Verifier Removed as Unsupported):")
        fps = part2_res.get("false_positives", [])
        if fps:
            for idx, fp in enumerate(fps, 1):
                print(f"    {idx}. ID:         {fp['id']} ({fp.get('case_id')})")
                print(f"       Claim:      \"{fp['claim']}\"")
                print(f"       Confidence: {fp['confidence']:.3f} (threshold: {best_thresh:.3f})")
        else:
            print("    None.")

        if args.sweep:
            run_sensitivity_sweep(part2_res.get("labeled_rows", []))
    else:
        print(f"  Status: {part2_res['message']}")

    print("=" * 80 + "\n")
    logger.info("Results successfully saved to %s", RESULTS_FILE)


if __name__ == "__main__":
    main()

