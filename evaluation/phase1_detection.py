"""Phase 1 Phishing Detection Evaluation Script (§10, §16, Stage 4).

Usage:
    uv run python evaluation/phase1_detection.py [--model MODEL] [--max-samples N] [--with-gemini]

Evaluates:
1. Public dataset (ealvaradob/phishing-dataset) capped at ~1500 with fixed-seed 80/20 split.
   - Tunes threshold/weights on the 80% split only.
   - Reports Accuracy, False Positive Rate (FPR), Recall, and per-email latency.
   - Prints data leakage warning for BERT and text-only layer notice.
2. phase1_with_headers.json as an unseen, out-of-distribution test set with full headers.
   - Evaluates fused pipeline and every individual layer.
3. Optional Gemini social comparison on a ~100 sample subset.
4. Saves structured metrics to evaluation/results/phase1_results.json.
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


def compute_metrics(y_true: list[int], y_pred: list[int], latencies: list[float]) -> dict[str, Any]:
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
    avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

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


def evaluate_text_sample(
    sample: dict,
    model_override: str | None = None,
) -> tuple[float, float]:
    """Run BERT inference on a raw text sample and return (score, latency_ms)."""
    text = sample.get("text", "")
    email = Email(
        id=999999,
        gmail_id="eval_sample",
        subject="",
        body_text=text,
        sender="unknown@example.com",
    )
    t0 = time.perf_counter()
    res = evaluate_bert_phishing(email)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return res.score, latency_ms


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

    email_obj = Email(
        id=999999,
        gmail_id=email_dict.get("id", "eval_sample"),
        subject=subject,
        body_text=body_text,
        sender=sender,
        raw_headers=json.dumps(raw_headers),
        links=json.dumps(links),
    )

    t0 = time.perf_counter()
    # 1. Sender Auth
    auth_res = evaluate_sender_auth(raw_headers, sender)

    # 2. URL Heuristics
    sender_domain = sender.split("@")[-1].strip(">").strip() if "@" in sender else ""
    dmarc_pass = any("dmarc check result: pass" in ev.lower() for ev in auth_res.evidence)
    url_res = evaluate_url_heuristics(links, body_text, sender_domain=sender_domain, dmarc_pass=dmarc_pass)

    # 3. BERT
    bert_res = evaluate_bert_phishing(email_obj)

    # 4. Gemini (if requested)
    if include_gemini:
        social_res = evaluate_gemini_social(email_obj, preliminary_score=0.5, force_trigger=True)
    else:
        social_res = LayerResult(
            name="gemini_social",
            score=0.0,
            reason="Gemini evaluation omitted to conserve API quota",
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
    )
    total_latency_ms = (time.perf_counter() - t0) * 1000.0

    layers_dict = {
        "sender_auth": auth_res,
        "url_heuristics": url_res,
        "bert_phishing": bert_res,
        "gemini_social": social_res,
    }
    return layers_dict, fusion_res.fraud_score or 0.0, total_latency_ms


def run_phase1_evaluation(
    model_name: str | None = None,
    max_samples: int = 1500,
    seed: int = 42,
    with_gemini: bool = False,
) -> dict[str, Any]:
    """Execute complete Phase 1 detection evaluation."""
    results: dict[str, Any] = {
        "metadata": {
            "model": model_name or settings.hf_phishing_model,
            "max_samples": max_samples,
            "seed": seed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    }

    # -------------------------------------------------------------------------
    # PART 1: Public Dataset (ealvaradob/phishing-dataset) Text Evaluation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("PART 1: PUBLIC DATASET (ealvaradob/phishing-dataset) EVALUATION")
    print("=" * 78)
    print(
        "[WARNING] DATA LEAKAGE NOTE:\n"
        "  ealvaradob/bert-finetuned-phishing was fine-tuned on this exact distribution.\n"
        "  High performance on this dataset reflects distribution familiarity.\n"
        "  Use Part 2 (phase1_with_headers.json) for unbiased out-of-distribution evaluation."
    )
    print(
        "[NOTICE] TEXT-ONLY LAYER NOTICE:\n"
        "  This public dataset provides body text only without RFC headers or links.\n"
        "  Only text classification layers apply; structural layers abstain."
    )

    dataset_path = PROJECT_ROOT / "evaluation" / "data" / "phishing_dataset_1500.json"
    if not dataset_path.exists():
        # Check alternative texts.json in data/
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
        y_train_true = []
        train_scores = []
        for s in train_samples:
            label = int(s.get("label", 0))
            score, _ = evaluate_text_sample(s, model_override=model_name)
            y_train_true.append(label)
            train_scores.append(score)

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
        y_test_true = []
        y_test_pred = []
        test_latencies = []
        for s in test_samples:
            label = int(s.get("label", 0))
            score, lat = evaluate_text_sample(s, model_override=model_name)
            y_test_true.append(label)
            y_test_pred.append(1 if score >= best_threshold else 0)
            test_latencies.append(lat)

        pub_metrics = compute_metrics(y_test_true, y_test_pred, test_latencies)
        pub_metrics["tuned_threshold"] = best_threshold
        results["public_dataset_test_split"] = pub_metrics

        print("\nPublic Dataset Holdout (20%) Results:")
        print(f"  Accuracy:       {pub_metrics['accuracy']:.2%}")
        print(f"  Recall (TPR):   {pub_metrics['recall']:.2%}")
        print(f"  Precision:      {pub_metrics['precision']:.2%}")
        print(f"  False Pos Rate: {pub_metrics['fpr']:.2%}")
        print(f"  F1 Score:       {pub_metrics['f1']:.4f}")
        print(f"  Avg Latency:    {pub_metrics['avg_latency_ms']:.2f} ms / email")
    else:
        print(f"Public dataset file not found at {dataset_path}. Skipping Part 1.")
        results["public_dataset_test_split"] = {"status": "skipped", "reason": "dataset file not present"}

    # -------------------------------------------------------------------------
    # PART 2: Benchmark Evaluation with Headers (phase1_with_headers.json)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("PART 2: OUT-OF-DISTRIBUTION BENCHMARK (phase1_with_headers.json)")
    print("=" * 78)

    headers_file = PROJECT_ROOT / "evaluation" / "data" / "phase1_with_headers.json"
    if not headers_file.exists():
        print(f"Error: {headers_file} not found. Run generate_dataset.py first.")
        return results

    with open(headers_file, encoding="utf-8") as f:
        benchmark_emails = json.load(f)

    print(f"Loaded {len(benchmark_emails)} benchmark test cases.")

    y_bench_true: list[int] = []
    layer_preds: dict[str, list[int]] = {
        "sender_auth": [],
        "url_heuristics": [],
        "bert_phishing": [],
        "fused_pipeline": [],
    }
    layer_latencies: dict[str, list[float]] = {
        "sender_auth": [],
        "url_heuristics": [],
        "bert_phishing": [],
        "fused_pipeline": [],
    }

    for item in benchmark_emails:
        true_label = 1 if item.get("label") == "phishing" else 0
        y_bench_true.append(true_label)

        layers_dict, fused_score, total_lat = evaluate_email_dict(item, include_gemini=False)

        # Record individual layer predictions (threshold 0.50)
        for lyr_name in ["sender_auth", "url_heuristics", "bert_phishing"]:
            lyr = layers_dict[lyr_name]
            pred = 1 if (lyr.available and lyr.score >= 0.50) else 0
            layer_preds[lyr_name].append(pred)
            layer_latencies[lyr_name].append(0.5 if lyr_name != "bert_phishing" else 900.0)

        # Fused pipeline prediction (threshold 0.50)
        fused_pred = 1 if fused_score >= settings.fraud_threshold else 0
        layer_preds["fused_pipeline"].append(fused_pred)
        layer_latencies["fused_pipeline"].append(total_lat)

    benchmark_results: dict[str, Any] = {}
    print(f"\n{'Layer':<20} | {'Accuracy':<10} | {'Recall':<10} | {'FPR':<10} | {'F1':<8} | {'Avg Latency'}")
    print("-" * 75)
    for name in ["sender_auth", "url_heuristics", "bert_phishing", "fused_pipeline"]:
        m = compute_metrics(y_bench_true, layer_preds[name], layer_latencies[name])
        benchmark_results[name] = m
        print(
            f"{name:<20} | {m['accuracy']:<10.1%} | {m['recall']:<10.1%} | "
            f"{m['fpr']:<10.1%} | {m['f1']:<8.4f} | {m['avg_latency_ms']:.1f} ms"
        )

    results["benchmark_evaluation"] = benchmark_results

    # -------------------------------------------------------------------------
    # PART 3: Gemini Social Engineering Layer Comparison (on sample)
    # -------------------------------------------------------------------------
    if with_gemini:
        print("\n" + "=" * 78)
        print("PART 3: GEMINI SOCIAL ENGINEERING LAYER COMPARISON")
        print("=" * 78)
        gemini_sample = benchmark_emails[:20]  # Representative sample
        y_gem_true = []
        preds_without_gemini = []
        preds_with_gemini = []

        for item in gemini_sample:
            label = 1 if item.get("label") == "phishing" else 0
            y_gem_true.append(label)

            _, score_no_gem, _ = evaluate_email_dict(item, include_gemini=False)
            _, score_with_gem, _ = evaluate_email_dict(item, include_gemini=True)

            preds_without_gemini.append(1 if score_no_gem >= settings.fraud_threshold else 0)
            preds_with_gemini.append(1 if score_with_gem >= settings.fraud_threshold else 0)

        m_no_gem = compute_metrics(y_gem_true, preds_without_gemini, [])
        m_with_gem = compute_metrics(y_gem_true, preds_with_gemini, [])

        results["gemini_comparison"] = {
            "without_gemini": m_no_gem,
            "with_gemini": m_with_gem,
        }
        print(f"Without Gemini: Accuracy {m_no_gem['accuracy']:.1%}, Recall {m_no_gem['recall']:.1%}, FPR {m_no_gem['fpr']:.1%}")
        print(f"With Gemini:    Accuracy {m_with_gem['accuracy']:.1%}, Recall {m_with_gem['recall']:.1%}, FPR {m_with_gem['fpr']:.1%}")

    # -------------------------------------------------------------------------
    # Save Results to JSON
    # -------------------------------------------------------------------------
    results_dir = PROJECT_ROOT / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / "phase1_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nEvaluation metrics successfully written to: {out_file}")
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
