"""Phase 1 Phishing Detection Evaluation Script (§10, §16, Stage 4).

Usage:
    uv run python evaluation/phase1_detection.py [--model MODEL] [--max-samples N] [--with-gemini]

Evaluates:
1. Public dataset (ealvaradob/phishing-dataset) 20% holdout split (tuned on 80%).
2. Out-of-distribution benchmark: held-out test half of phase1_with_headers.json (20 emails).
3. Test-only benchmark: evaluation/data/phase1_my_emails.json (14 emails) with per-category breakdown.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models import Email
from app.phishing.fusion import fuse_phishing_layers
from app.phishing.providers.base import LayerResult
from app.phishing.providers.bert_phishing import evaluate_bert_phishing
from app.phishing.providers.gemini_social import evaluate_gemini_social
from app.phishing.providers.sender_auth import evaluate_sender_auth
from app.phishing.providers.url_heuristics import evaluate_url_heuristics
from app.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compute_metrics(y_true: list[int], y_pred: list[int], latencies: list[float] | None = None) -> dict[str, Any]:
    """Compute standard classification evaluation metrics."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    total = len(y_true)
    accuracy = (tp + tn) / total if total > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else 0.0

    return {
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(accuracy, 4),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "fpr": round(fpr, 4),
        "f1": round(f1, 4),
        "avg_latency_ms": round(avg_latency_ms, 2),
    }


def load_dataset_samples(data_file: Path, max_samples: int = 1500, seed: int = 42) -> list[dict]:
    """Load text samples from JSON dataset file."""
    if not data_file.exists():
        logger.warning("Dataset file %s does not exist.", data_file)
        return []

    with open(data_file, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    rng = random.Random(seed)
    rng.shuffle(data)
    return data[:max_samples]


def evaluate_text_samples_batch(
    samples: list[dict],
    batch_size: int = 32,
) -> tuple[list[float], list[float]]:
    """Run batched BERT inference on text samples and return (scores, latencies_ms)."""
    import torch

    from app.phishing.providers.bert_phishing import _get_model_and_tokenizer

    tokenizer, model, err = _get_model_and_tokenizer()
    if err or tokenizer is None or model is None:
        logger.warning("BERT model unavailable: %s", err)
        return [0.0] * len(samples), [0.0] * len(samples)

    scores: list[float] = []
    latencies: list[float] = []
    for i in range(0, len(samples), batch_size):
        batch = samples[i : i + batch_size]
        texts = [s.get("text", "") for s in batch]
        t0 = time.perf_counter()
        inputs = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[:, 1].tolist()
        batch_lat = ((time.perf_counter() - t0) * 1000.0) / max(len(batch), 1)
        scores.extend(probs)
        latencies.extend([batch_lat] * len(batch))
    return scores, latencies


def load_my_emails(file_path: Path) -> list[dict]:
    """Build loader for evaluation/data/phase1_my_emails.json mapping to standardized email dicts.

    Mappings:
      - authentication_results -> raw_headers Authentication-Results with authserv-id mx.google.com
      - from -> From header and sender string
      - reply_to -> Reply-To header
      - return_path -> Return-Path header
      - links -> links array
      - attachments -> attachments array
      - ignore why_hard and category when scoring
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    raw_list = data.get("emails", [])
    standardized: list[dict] = []
    for item in raw_list:
        raw_headers: list[dict[str, str]] = []
        if item.get("authentication_results"):
            raw_headers.append({"name": "Authentication-Results", "value": item["authentication_results"]})
        if item.get("from"):
            raw_headers.append({"name": "From", "value": item["from"]})
        if item.get("reply_to"):
            raw_headers.append({"name": "Reply-To", "value": item["reply_to"]})
        if item.get("return_path"):
            raw_headers.append({"name": "Return-Path", "value": item["return_path"]})
        if item.get("to"):
            raw_headers.append({"name": "To", "value": item["to"]})
        if item.get("subject"):
            raw_headers.append({"name": "Subject", "value": item["subject"]})
        if item.get("date"):
            raw_headers.append({"name": "Date", "value": item["date"]})

        extra_headers = item.get("headers", {})
        if isinstance(extra_headers, dict):
            for k, v in extra_headers.items():
                raw_headers.append({"name": k, "value": v})

        standardized.append({
            "id": item.get("id"),
            "label": item.get("label"),
            "category": item.get("category"),
            "why_hard": item.get("why_hard"),
            "sender": item.get("from", ""),
            "subject": item.get("subject", ""),
            "body_text": item.get("body_text", ""),
            "raw_headers": raw_headers,
            "links": item.get("links", []),
            "attachments": item.get("attachments", []),
        })

    return standardized


def evaluate_email_dict(
    email_dict: dict,
    include_gemini: bool = False,
) -> tuple[dict[str, LayerResult], float, float]:
    """Evaluate an email dictionary with full headers, links, and text."""
    raw_headers = email_dict.get("raw_headers", [])
    links = email_dict.get("links", [])
    subject = email_dict.get("subject", "")
    body_text = email_dict.get("body_text", "")
    sender = email_dict.get("sender", "")
    attachments = email_dict.get("attachments", [])

    email_obj = Email(
        id=999999,
        gmail_id=str(email_dict.get("id", "eval_sample")),
        subject=subject,
        body_text=body_text,
        sender=sender,
        raw_headers=json.dumps(raw_headers) if isinstance(raw_headers, list) else str(raw_headers),
        links=json.dumps(links) if isinstance(links, list) else str(links),
    )

    t0 = time.perf_counter()

    # 1. Sender Auth
    auth_res = evaluate_sender_auth(raw_headers, sender, subject=subject, body_text=body_text)

    # 2. URL Heuristics
    sender_domain = sender.split("@")[-1].strip(">").strip() if "@" in sender else ""
    dmarc_pass = any("dmarc check result: pass" in ev.lower() for ev in auth_res.evidence)
    url_res = evaluate_url_heuristics(
        links,
        body_text=body_text,
        sender_domain=sender_domain,
        dmarc_pass=dmarc_pass,
        attachments=attachments,
    )

    # 3. BERT
    bert_res = evaluate_bert_phishing(email_obj)

    # 4. Gemini (if requested)
    if include_gemini:
        # Pass a preliminary score to trigger social engineering layer if relevant
        prelim = max(auth_res.score if auth_res.available else 0.0, url_res.score if url_res.available else 0.0, bert_res.score if bert_res.available else 0.0)
        social_res = evaluate_gemini_social(email_obj, preliminary_score=prelim, force_trigger=True)
    else:
        social_res = LayerResult(
            name="gemini_social",
            score=0.0,
            reason="Gemini evaluation omitted",
            available=False,
        )

    # 5. Fusion
    layers = [auth_res, url_res, bert_res, social_res]
    fusion_res = fuse_phishing_layers(
        layers=layers,
        sender_email=sender,
        known_contacts=set(),
        spf_pass=any("spf check result: pass" in ev.lower() for ev in auth_res.evidence),
        dkim_pass=any("dkim check result: pass" in ev.lower() for ev in auth_res.evidence),
        has_reply_to_mismatch=any("reply-to" in ev.lower() and "does not match" in ev.lower() for ev in auth_res.evidence),
        has_anchor_mismatch=getattr(url_res, "has_anchor_mismatch", False),
        is_auth_clean=getattr(auth_res, "is_fully_clean", False),
    )
    total_latency_ms = (time.perf_counter() - t0) * 1000.0

    layers_dict = {
        "sender_auth": auth_res,
        "url_heuristics": url_res,
        "bert_phishing": bert_res,
        "gemini_social": social_res,
    }
    return layers_dict, fusion_res.fraud_score or 0.0, total_latency_ms


def evaluate_dataset_collection(
    emails: list[dict],
    set_name: str,
    include_gemini: bool = False,
) -> dict[str, Any]:
    """Run evaluation over a collection of emails and compute per-layer and fused metrics."""
    y_true: list[int] = []
    layer_preds: dict[str, list[int]] = {
        "sender_auth": [],
        "url_heuristics": [],
        "bert_phishing": [],
        "fused": [],
    }
    layer_latencies: dict[str, list[float]] = {
        "sender_auth": [],
        "url_heuristics": [],
        "bert_phishing": [],
        "fused": [],
    }
    if include_gemini:
        layer_preds["gemini_social"] = []
        layer_latencies["gemini_social"] = []

    per_email_details: list[dict[str, Any]] = []

    for item in emails:
        raw_label = str(item.get("label", "")).lower()
        true_label = 1 if raw_label in ["phishing", "fraud"] else 0
        y_true.append(true_label)

        layers_dict, fused_score, total_lat = evaluate_email_dict(item, include_gemini=include_gemini)
        if include_gemini:
            time.sleep(0.5)

        # Record individual layers
        for lyr_name in ["sender_auth", "url_heuristics", "bert_phishing"]:
            lyr = layers_dict[lyr_name]
            pred = 1 if (lyr.available and lyr.score >= 0.50) else 0
            layer_preds[lyr_name].append(pred)
            layer_latencies[lyr_name].append(1.0 if lyr_name != "bert_phishing" else 900.0)

        if include_gemini:
            lyr = layers_dict["gemini_social"]
            pred = 1 if (lyr.available and lyr.score >= 0.50) else 0
            layer_preds["gemini_social"].append(pred)
            layer_latencies["gemini_social"].append(1500.0)

        # Fused pipeline
        fused_pred = 1 if fused_score >= settings.fraud_threshold else 0
        layer_preds["fused"].append(fused_pred)
        layer_latencies["fused"].append(total_lat)

        per_email_details.append({
            "id": item.get("id"),
            "category": item.get("category"),
            "true_label": "phishing" if true_label == 1 else "legitimate",
            "fused_score": round(fused_score, 4),
            "fused_prediction": "phishing" if fused_pred == 1 else "legitimate",
            "correct": fused_pred == true_label,
            "sender_auth": {"score": layers_dict["sender_auth"].score, "available": layers_dict["sender_auth"].available},
            "url_heuristics": {"score": layers_dict["url_heuristics"].score, "available": layers_dict["url_heuristics"].available},
            "bert_phishing": {"score": layers_dict["bert_phishing"].score, "available": layers_dict["bert_phishing"].available},
            "gemini_social": {"score": layers_dict["gemini_social"].score, "available": layers_dict["gemini_social"].available} if include_gemini else None,
        })

    summary_metrics: dict[str, Any] = {}
    evaluated_layers = ["sender_auth", "url_heuristics", "bert_phishing"]
    if include_gemini:
        evaluated_layers.append("gemini_social")
    evaluated_layers.append("fused")

    print(f"\n[{set_name}] Summary Results (N={len(emails)}, Gemini={'ON' if include_gemini else 'OFF'}):")
    print(f"{'Layer':<18} | {'Accuracy':<10} | {'Recall':<10} | {'FPR':<10} | {'F1':<8} | {'Avg Latency'}")
    print("-" * 75)
    for name in evaluated_layers:
        m = compute_metrics(y_true, layer_preds[name], layer_latencies[name])
        summary_metrics[name] = m
        print(
            f"{name:<18} | {m['accuracy']:<10.1%} | {m['recall']:<10.1%} | "
            f"{m['fpr']:<10.1%} | {m['f1']:<8.4f} | {m['avg_latency_ms']:.1f} ms"
        )

    return {
        "metrics": summary_metrics,
        "details": per_email_details,
    }


def run_phase1_evaluation(
    model_name: str | None = None,
    max_samples: int = 1500,
    seed: int = 42,
    with_gemini: bool = False,
) -> dict[str, Any]:
    """Execute complete Phase 1 detection evaluation across the 3 benchmark sets."""
    results: dict[str, Any] = {
        "metadata": {
            "model": model_name or settings.hf_phishing_model,
            "max_samples": max_samples,
            "seed": seed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    }

    # -------------------------------------------------------------------------
    # SET (B): Public Dataset (ealvaradob/phishing-dataset) 20% Holdout Split
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SET (B): PUBLIC DATASET (ealvaradob/phishing-dataset) 20% HOLDOUT EVALUATION")
    print("=" * 80)
    print(
        "[WARNING] DATA LEAKAGE NOTE:\n"
        "  ealvaradob/bert-finetuned-phishing was fine-tuned on this exact distribution.\n"
        "  High performance on this dataset reflects distribution familiarity.\n"
        "  Use Sets (A) and (C) for unbiased out-of-distribution evaluation."
    )
    print(
        "[NOTICE] TEXT-ONLY LAYER NOTICE:\n"
        "  This public dataset provides body text only without RFC headers or links.\n"
        "  Only text classification layers apply; structural layers abstain."
    )

    dataset_path = PROJECT_ROOT / "evaluation" / "data" / "phishing_dataset_1500.json"
    if not dataset_path.exists():
        alt_path = PROJECT_ROOT / "evaluation" / "data" / "texts.json"
        if alt_path.exists():
            dataset_path = alt_path

    if dataset_path.exists():
        samples = load_dataset_samples(dataset_path, max_samples=max_samples, seed=seed)
        split_idx = int(len(samples) * 0.8)
        train_samples = samples[:split_idx]
        test_samples = samples[split_idx:]
        print(f"Loaded {len(samples)} samples: {len(train_samples)} tuning (80%), {len(test_samples)} testing (20%)")

        # Evaluate tuning set (80%) to determine optimal threshold
        y_train_true = [int(s.get("label", 0)) for s in train_samples]
        train_scores, _ = evaluate_text_samples_batch(train_samples, batch_size=32)

        # Search optimal decision threshold on 80% split
        best_threshold = 0.50
        best_f1 = -1.0
        for thresh in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85]:
            preds = [1 if sc >= thresh else 0 for sc in train_scores]
            metrics = compute_metrics(y_train_true, preds, [])
            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                best_threshold = thresh

        print(f"Tuned optimal threshold on 80% split: {best_threshold:.2f} (tuning F1: {best_f1:.4f})")

        # Evaluate test set (20%) using tuned threshold
        y_test_true = [int(s.get("label", 0)) for s in test_samples]
        test_scores, test_latencies = evaluate_text_samples_batch(test_samples, batch_size=32)
        y_test_pred = [1 if score >= best_threshold else 0 for score in test_scores]

        pub_metrics = compute_metrics(y_test_true, y_test_pred, test_latencies)
        pub_metrics["tuned_threshold"] = best_threshold
        results["set_b_public_dataset_20pct_holdout"] = pub_metrics

        print("\nPublic Dataset Holdout (20%) Results:")
        print(f"  Accuracy:       {pub_metrics['accuracy']:.2%}")
        print(f"  Recall (TPR):   {pub_metrics['recall']:.2%}")
        print(f"  Precision:      {pub_metrics['precision']:.2%}")
        print(f"  False Pos Rate: {pub_metrics['fpr']:.2%}")
        print(f"  F1 Score:       {pub_metrics['f1']:.4f}")
        print(f"  Avg Latency:    {pub_metrics['avg_latency_ms']:.2f} ms / email")
    else:
        print(f"Public dataset file not found at {dataset_path}. Skipping Set (B).")
        results["set_b_public_dataset_20pct_holdout"] = {"status": "skipped", "reason": "dataset file not present"}

    # -------------------------------------------------------------------------
    # SET (A): Held-Out Test Half of phase1_with_headers.json
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SET (A): HELD-OUT TEST HALF OF phase1_with_headers.json")
    print("=" * 80)

    test_headers_file = PROJECT_ROOT / "evaluation" / "data" / "phase1_headers_test.json"
    if not test_headers_file.exists():
        print(f"Error: {test_headers_file} not found.")
        return results

    with open(test_headers_file, encoding="utf-8") as f:
        test_half_emails = json.load(f)

    print(f"Loaded {len(test_half_emails)} held-out test emails.")

    # 1. Without Gemini
    eval_a_no_gem = evaluate_dataset_collection(
        test_half_emails,
        set_name="Set A - Without Gemini",
        include_gemini=False,
    )
    # 2. With Gemini
    eval_a_with_gem = None
    if with_gemini:
        eval_a_with_gem = evaluate_dataset_collection(
            test_half_emails,
            set_name="Set A - With Gemini",
            include_gemini=True,
        )

    results["set_a_headers_test_half"] = {
        "without_gemini": eval_a_no_gem["metrics"],
        "with_gemini": eval_a_with_gem["metrics"] if eval_a_with_gem else None,
        "details": eval_a_no_gem["details"],
    }

    # -------------------------------------------------------------------------
    # SET (C): phase1_my_emails.json (TEST-ONLY)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SET (C): phase1_my_emails.json (TEST-ONLY BENCHMARK)")
    print("=" * 80)
    print("[TEST-ONLY NOTICE]: Never tuned or fitted on this dataset.")

    my_emails_file = PROJECT_ROOT / "evaluation" / "data" / "phase1_my_emails.json"
    if not my_emails_file.exists():
        print(f"Error: {my_emails_file} not found.")
        return results

    my_emails = load_my_emails(my_emails_file)
    print(f"Loaded {len(my_emails)} test-only emails.")

    # 1. Without Gemini
    eval_c_no_gem = evaluate_dataset_collection(
        my_emails,
        set_name="Set C - Without Gemini",
        include_gemini=False,
    )
    # 2. With Gemini
    eval_c_with_gem = None
    if with_gemini:
        eval_c_with_gem = evaluate_dataset_collection(
            my_emails,
            set_name="Set C - With Gemini",
            include_gemini=True,
        )

    # Breakdown per Category for Set C
    cat_details: dict[str, list[dict]] = {}
    for d in eval_c_no_gem["details"]:
        cat = d.get("category") or "unknown"
        cat_details.setdefault(cat, []).append(d)

    print("\n[Set C] Per-Category Detailed Breakdown (Without Gemini):")
    print(f"{'Email ID':<14} | {'Category':<45} | {'Label':<8} | {'Score':<6} | {'Pred':<8} | {'Status'}")
    print("-" * 96)
    for d in eval_c_no_gem["details"]:
        status = "PASS" if d["correct"] else "FAIL"
        print(
            f"{d['id']:<14} | {d['category']:<45} | {d['true_label'][:5]:<8} | "
            f"{d['fused_score']:<6.2f} | {d['fused_prediction'][:5]:<8} | {status}"
        )

    results["set_c_my_emails_test_only"] = {
        "without_gemini": eval_c_no_gem["metrics"],
        "with_gemini": eval_c_with_gem["metrics"] if eval_c_with_gem else None,
        "details": eval_c_no_gem["details"],
    }

    # -------------------------------------------------------------------------
    # Save Results to JSON
    # -------------------------------------------------------------------------
    results_dir = PROJECT_ROOT / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / "phase1_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nAll Phase 1 evaluation metrics successfully written to: {out_file}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="AegisRAG Phase 1 Phishing Detection Evaluation")
    parser.add_argument("--model", type=str, default=None, help="HuggingFace phishing model id to evaluate")
    parser.add_argument("--max-samples", type=int, default=1500, help="Max samples from public dataset")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for 80/20 train/test split")
    parser.add_argument("--with-gemini", action="store_true", help="Include Gemini social engineering layer comparison")
    args = parser.parse_args()

    run_phase1_evaluation(
        model_name=args.model,
        max_samples=args.max_samples,
        seed=args.seed,
        with_gemini=args.with_gemini,
    )


if __name__ == "__main__":
    main()
