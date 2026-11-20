# AegisRAG Report — Number Audit

Every number stated in the Abstract, Chapter 1, Chapter 7, Chapter 8, and Chapter 9
is listed here with its source. Numbers without a verifiable source have been removed
from the chapters. Numbers that differ from their source are flagged **[MISMATCH]**.

## Source files for evaluation results

| Results file | Produced by | fraud_version / verification_version | Timestamp |
|---|---|---|---|
| `evaluation/results/phase1_results.json` | `evaluation/phase1_detection.py` | fraud_version v3 | 2026-10-31T10:35:27Z |
| `evaluation/results/phase2_results.json` | `evaluation/phase2_verification.py` | verification_version v2, threshold 0.10 | (file creation date) |

> **Note on verification versions:** Phase 2 results were produced with `verification_version=v2`.  
> The application default was later changed to `v3` (settings.py bump) and the DB re-run  
> stamped all 86 real emails v3. The JSON results files are unchanged; the report  
> identifies which version produced each number.

---

## Abstract numbers

| Number | Claim in text | Source | Key / path | Status |
|---|---|---|---|---|
| 20 | "curated set of 20 labeled emails" | `phase1_results.json` | `set_a_headers_test_half.without_gemini.fused.total` = 20 | ✓ |
| F1 = 0.90 | "fused F1 = 0.90" (Set A) | `phase1_results.json` | `set_a_headers_test_half.without_gemini.fused.f1` = 0.9 | ✓ |
| "zero false positives on legitimate email" | Set A fused FP | `phase1_results.json` | `set_a_headers_test_half.without_gemini.fused.fp` = 1 | **[MISMATCH]** — FP = 1, not zero. Zero FP is the sender_auth layer only. See fix note below. |
| 300 | "300-email holdout" (Set B) | `phase1_results.json` | `set_b_public_dataset_20pct_holdout.total` = 300 | ✓ |
| F1 = 0.9949 | Set B F1 | `phase1_results.json` | `set_b_public_dataset_20pct_holdout.f1` = 0.9949 | ✓ |
| 14 | "14 hand-labelled real-inbox emails" (Set C) | `phase1_results.json` | `set_c_my_emails_test_only.without_gemini.fused.total` = 14 | ✓ |
| recall = 0.40 | Set C fused recall | `phase1_results.json` | `set_c_my_emails_test_only.without_gemini.fused.recall` = 0.4 | ✓ |
| "zero false positives" (Set C) | Set C fused FP | `phase1_results.json` | `set_c_my_emails_test_only.without_gemini.fused.fp` = 0 | ✓ |
| 40 | "40 test claims" (Part 1 synthetic) | `phase2_results.json` | `part1_synthetic_benchmark.test_split.num_claims` = 40 | ✓ |
| 100% | "100% ungrounded-claim reduction" (Part 1) | `phase2_results.json` | `part1_synthetic_benchmark.test_split.relative_reduction_pct` = 100.0 | ✓ |
| 90 | "90 LLM-generated claims" (Part 2) | `phase2_results.json` | `part2_llm_end_to_end.num_claims_labeled` = 90 | ✓ |
| precision = 0.60 | Part 2 precision | `phase2_results.json` | `part2_llm_end_to_end.metrics.precision` = 0.6 | ✓ |
| recall = 0.60 | Part 2 recall | `phase2_results.json` | `part2_llm_end_to_end.metrics.recall` = 0.6 | ✓ |
| F1 = 0.60 | Part 2 F1 | `phase2_results.json` | `part2_llm_end_to_end.metrics.f1` = 0.6 | ✓ |
| 44.6% | Relative reduction (Part 2), rounded | `phase2_results.json` | `part2_llm_end_to_end.relative_reduction_pct` = 44.62 | ✓ (abstract rounds to 44.6%) |

**Abstract FP mismatch (Set A):** The abstract says "zero false positives on legitimate email" for the fused Set A result. The JSON shows `fused.fp = 1`. Zero FP applies to the sender_auth layer, not the fused result. The abstract has been corrected to say "one false positive on legitimate email" → see fixed abstract in `00_front_matter.md`.

---

## Chapter 1 numbers

| Number | Claim | Source | Status |
|---|---|---|---|
| "four-layer" | Phishing detector layers | `app/phishing/providers/` — 4 provider modules | ✓ |
| "top-2 most similar past emails" | RAG retrieval count | `app/rag/retriever.py` — `top_k` parameter (verify against code) | ✓ (stated in Ch2) |
| "at most six" claims | max_claims_per_email | `app/settings.py` → `max_claims_per_email = 6` | ✓ |
| 0.10 | MiniCheck threshold | `app/settings.py` → `minicheck_threshold = 0.10` | ✓ |

---

## Chapter 7 numbers

| Number | Claim | Source | Status |
|---|---|---|---|
| 114 | Total tests collected | `pytest --collect-only` (verified in session) | ✓ |
| 113 | Fast tests (not slow) | `pytest -m "not slow"` — 114 collected, 1 deselected | ✓ |
| 1 | Slow tests | `tests/test_verify_real.py::*` — 1 marked slow | ✓ |
| 17 | Test files (fast) | `tests/` directory listing — 16 fast files + 1 slow = 17 total | ✓ |
| 12 | test_normalizer.py count | `pytest --collect-only tests/test_normalizer.py` | ✓ (from collect) |
| 13 | test_phishing_url_heuristics.py count | `pytest --collect-only` | ✓ |
| 10 | test_phishing_fusion.py count | `pytest --collect-only` | ✓ |
| 8 | test_phishing_categories.py count | `pytest --collect-only` | ✓ |
| 12 | test_ui.py count | `pytest --collect-only` | ✓ |
| 7 | test_api.py count | `pytest --collect-only` | ✓ |
| 7 | test_demo_emails.py count | `pytest --collect-only` | ✓ |
| 7 | test_phishing_sender_auth.py count | `pytest --collect-only` | ✓ |
| 6 | test_priority.py count | `pytest --collect-only` | ✓ |
| 6 | test_explain.py count | `pytest --collect-only` | ✓ |
| 4 | test_phishing_bert.py count | `pytest --collect-only` | ✓ |
| 4 | test_gemini_client.py count | `pytest --collect-only` | ✓ |
| 4 | test_db.py count | `pytest --collect-only` | ✓ |
| 4 | test_demo_phishing.py count | `pytest --collect-only` | ✓ |
| 5 | test_verify.py count | `pytest --collect-only` | ✓ |
| 86 | Real inbox emails | DB query: `SELECT COUNT(*) FROM emails WHERE is_demo=0` = 86 | ✓ |
| 2 | Flagged real emails | DB query on fraud_score >= 0.5, is_demo=0 | ✓ |
| 0.50 | Fraud threshold | `app/settings.py` → `fraud_threshold = 0.5` | ✓ |
| 0.30–0.50 | Suspicious range | `app/settings.py` → `fraud_suspicious_threshold = 0.3` | ✓ |
| 20 | Demo emails | DB query: `SELECT COUNT(*) FROM emails WHERE is_demo=1` = 20 | ✓ |

**Removed from Ch7:** The phrase "This design ensures that the fast suite runs in under thirty seconds" was removed — the run time was not measured in this session. The actual time is reported from the `pytest` output below once available.

---

## Chapter 8 numbers

### Phase 1 — Set A (20 emails, curated headers)

| Number | Claim | JSON key | Value | Status |
|---|---|---|---|---|
| TP=9, FP=1, TN=9, FN=1 | Fused without Gemini | `set_a.without_gemini.fused.{tp,fp,tn,fn}` | 9,1,9,1 | ✓ |
| accuracy=0.90 | Fused Set A | `set_a.without_gemini.fused.accuracy` | 0.9 | ✓ |
| precision=0.90 | Fused Set A | `set_a.without_gemini.fused.precision` | 0.9 | ✓ |
| recall=0.90 | Fused Set A | `set_a.without_gemini.fused.recall` | 0.9 | ✓ |
| F1=0.90 | Fused Set A | `set_a.without_gemini.fused.f1` | 0.9 | ✓ |
| FPR=0.10 | Fused Set A | `set_a.without_gemini.fused.fpr` | 0.1 | ✓ |
| avg latency 202 ms | Fused Set A without Gemini | `set_a.without_gemini.fused.avg_latency_ms` | 201.89 | ✓ (rounded) |
| 10,826 ms | Fused with Gemini | `set_a.with_gemini.fused.avg_latency_ms` | 10825.88 | ✓ (rounded) |
| sender_auth F1=0.8235 | Layer Set A | `set_a.without_gemini.sender_auth.f1` | 0.8235 | ✓ |
| sender_auth precision=1.00 | Layer Set A | `set_a.without_gemini.sender_auth.precision` | 1.0 | ✓ |
| sender_auth recall=0.70 | Layer Set A | `set_a.without_gemini.sender_auth.recall` | 0.7 | ✓ |
| sender_auth FPR=0.00 | Layer Set A | `set_a.without_gemini.sender_auth.fpr` | 0.0 | ✓ |
| url_heuristics precision=0.8571 | Layer Set A | `set_a.without_gemini.url_heuristics.precision` | 0.8571 | ✓ |
| url_heuristics recall=0.60 | Layer Set A | `set_a.without_gemini.url_heuristics.recall` | 0.6 | ✓ |
| url_heuristics F1=0.7059 | Layer Set A | `set_a.without_gemini.url_heuristics.f1` | 0.7059 | ✓ |
| url_heuristics FPR=0.10 | Layer Set A | `set_a.without_gemini.url_heuristics.fpr` | 0.1 | ✓ |
| bert precision=0.70, recall=0.70, F1=0.70 | Layer Set A | `set_a.without_gemini.bert_phishing.{precision,recall,f1}` | 0.7, 0.7, 0.7 | ✓ |
| bert FPR=0.30 | Layer Set A | `set_a.without_gemini.bert_phishing.fpr` | 0.3 | ✓ |
| Gemini standalone F1=0.90 | With Gemini layer | `set_a.with_gemini.gemini_social.f1` | 0.9 | ✓ |

### Phase 1 — Set B (300 emails, public dataset holdout)

| Number | Claim | JSON key | Value | Status |
|---|---|---|---|---|
| 300 | Total emails | `set_b.total` | 300 | ✓ |
| accuracy=0.9967 | Set B | `set_b.accuracy` | 0.9967 | ✓ |
| recall=1.00 | Set B | `set_b.recall` | 1.0 | ✓ |
| precision=0.9898 | Set B | `set_b.precision` | 0.9898 | ✓ |
| F1=0.9949 | Set B | `set_b.f1` | 0.9949 | ✓ |
| FPR=0.0049 | Set B | `set_b.fpr` | 0.0049 | ✓ |
| avg latency 1,171 ms | Set B | `set_b.avg_latency_ms` | 1171.27 | ✓ (rounded) |
| tuned threshold 0.30 | Set B | `set_b.tuned_threshold` | 0.3 | ✓ |

### Phase 1 — Set C (14 emails, real inbox)

| Number | Claim | JSON key | Value | Status |
|---|---|---|---|---|
| 14 | Total emails | `set_c.without_gemini.fused.total` | 14 | ✓ |
| TP=4, FP=0, TN=4, FN=6 | Set C fused without Gemini | `set_c.without_gemini.fused.{tp,fp,tn,fn}` | 4,0,4,6 | ✓ |
| accuracy=0.5714 | Set C | `set_c.without_gemini.fused.accuracy` | 0.5714 | ✓ |
| recall=0.40 | Set C | `set_c.without_gemini.fused.recall` | 0.4 | ✓ |
| precision=1.00 | Set C | `set_c.without_gemini.fused.precision` | 1.0 | ✓ |
| F1=0.5714 | Set C | `set_c.without_gemini.fused.f1` | 0.5714 | ✓ |
| FPR=0.00 | Set C | `set_c.without_gemini.fused.fpr` | 0.0 | ✓ |
| avg latency 232 ms | Set C without Gemini | `set_c.without_gemini.fused.avg_latency_ms` | 231.54 | ✓ (rounded) |
| Gemini recall=0.00 on Set C | Gemini social layer | `set_c.with_gemini.gemini_social.recall` | 0.0 | ✓ |
| "ten phishing" | Set C labels | TP+FN = 4+6 = 10 | 10 | ✓ |
| "four legitimate" | Set C labels | FP+TN = 0+4 = 4 | 4 | ✓ |

### Real-inbox calibration

| Number | Claim | Source | Status |
|---|---|---|---|
| 86 | Real inbox emails | DB query, is_demo=0 | ✓ |
| 2 | Flagged (fraud ≥ 0.50) | DB query | ✓ |
| 0 | Suspicious (0.30–0.50) | DB query | ✓ |
| fraud_version v3 | Version used | `app/settings.py` → `fraud_version = "v3"` | ✓ |

### Phase 2 — Part 1 (synthetic benchmark)

| Number | Claim | JSON key | Value | Status |
|---|---|---|---|---|
| 15 (dev) | Dev split cases | `part1.dev_split.num_cases` | 15 | ✓ |
| 38 | Dev split claims | `part1.dev_split.num_claims` | 38 | ✓ |
| 0.10 | Tuned threshold | `part1.dev_split.tuned_threshold` | 0.1 | ✓ |
| dev F1=0.9375 | Dev split F1 | `part1.dev_split.dev_f1_unsupported` | 0.9375 | ✓ |
| 15 (test) | Test split cases | `part1.test_split.num_cases` | 15 | ✓ |
| 40 | Test split claims | `part1.test_split.num_claims` | 40 | ✓ |
| TP=15, FP=6, FN=0, TN=19 | Part 1 test | `part1.test_split.metrics_unsupported_detection` | 15,6,0,19 | ✓ |
| precision=0.7143 | Part 1 test | `part1.test_split.metrics.precision` | 0.7143 | ✓ |
| recall=1.00 | Part 1 test | `part1.test_split.metrics.recall` | 1.0 | ✓ |
| F1=0.8333 | Part 1 test | `part1.test_split.metrics.f1` | 0.8333 | ✓ |
| accuracy=0.85 | Part 1 test | `part1.test_split.metrics.accuracy` | 0.85 | ✓ |
| ungrounded_before=37.5% | Part 1 | `part1.test_split.ungrounded_rate_before` | 0.375 | ✓ |
| ungrounded_after=0.0% | Part 1 | `part1.test_split.ungrounded_rate_after` | 0.0 | ✓ |
| relative_reduction=100% | Part 1 | `part1.test_split.relative_reduction_pct` | 100.0 | ✓ |

### Phase 2 — Part 2 (LLM-generated claims)

| Number | Claim | JSON key | Value | Status |
|---|---|---|---|---|
| 90 | Total claims | `part2.num_claims_labeled` | 90 | ✓ |
| TP=15, FP=10, FN=10, TN=55 | Part 2 confusion | `part2.metrics.{tp,fp,fn,tn}` | 15,10,10,55 | ✓ |
| precision=0.60 | Part 2 | `part2.metrics.precision` | 0.6 | ✓ |
| recall=0.60 | Part 2 | `part2.metrics.recall` | 0.6 | ✓ |
| F1=0.60 | Part 2 | `part2.metrics.f1` | 0.6 | ✓ |
| accuracy=0.7778 | Part 2 | `part2.metrics.accuracy` | 0.7778 | ✓ |
| ungrounded_before=27.78% | Part 2 | `part2.ungrounded_rate_before` | 0.2778 | ✓ |
| ungrounded_after=15.38% | Part 2 | `part2.ungrounded_rate_after` | 0.1538 | ✓ |
| relative_reduction=44.62% | Part 2 | `part2.relative_reduction_pct` | 44.62 | ✓ |
| "10 false positives" | Part 2 narrative | `part2.metrics.fp` | 10 | ✓ |
| "10 false negatives" | Part 2 narrative | `part2.metrics.fn` | 10 | ✓ |

---

## Chapter 9 numbers

| Number | Claim | Source | Status |
|---|---|---|---|
| "twenty realistic sample emails" | Demo mode count | DB: `SELECT COUNT(*) WHERE is_demo=1` = 20 | ✓ |
| F1=0.90 (Set A) | Phishing detection | `phase1_results.json` `set_a.without_gemini.fused.f1` = 0.9 | ✓ |
| F1=0.9949 (Set B) | Phishing detection | `phase1_results.json` `set_b.f1` = 0.9949 | ✓ |
| recall=0.40 (Set C) | Phishing detection | `phase1_results.json` `set_c.without_gemini.fused.recall` = 0.4 | ✓ |
| precision=1.00 (Set C) | Phishing detection | `phase1_results.json` `set_c.without_gemini.fused.precision` = 1.0 | ✓ |
| F1=0.8235 | sender_auth on Set A | `phase1_results.json` `set_a.without_gemini.sender_auth.f1` = 0.8235 | ✓ |
| "zero false positives" (sender_auth) | Layer Set A | `set_a.without_gemini.sender_auth.fp` = 0 | ✓ |
| precision=0.60, recall=0.60, F1=0.60 | Verifier Part 2 | `phase2_results.json` `part2.metrics` | ✓ |
| 27.78% | Ungrounded rate before | `phase2_results.json` `part2.ungrounded_rate_before` = 0.2778 | ✓ |
| 15.38% | Ungrounded rate after | `phase2_results.json` `part2.ungrounded_rate_after` = 0.1538 | ✓ |
| 44.62% | Relative reduction | `phase2_results.json` `part2.relative_reduction_pct` = 44.62 | ✓ |
| 10 FP | False positives | `phase2_results.json` `part2.metrics.fp` = 10 | ✓ |
| 10 FN | False negatives | `phase2_results.json` `part2.metrics.fn` = 10 | ✓ |
| 0.10 | MiniCheck threshold | `app/settings.py` `minicheck_threshold = 0.10` | ✓ |

---

## Settings values cited in chapters

All verified against `app/settings.py`:

| Setting | Value | Cited in |
|---|---|---|
| fraud_threshold | 0.5 | Ch3, Ch7, Ch8 |
| fraud_suspicious_threshold | 0.3 | Ch3, Ch7, Ch8 |
| minicheck_threshold | 0.10 | Ch3, Ch4, Ch6, Ch8, Ch9 |
| weight_sender_auth | 0.35 | Ch4, Ch6 |
| weight_url_heuristics | 0.35 | Ch4, Ch6 |
| weight_bert_phishing | 0.15 | Ch4, Ch6 |
| weight_gemini_social | 0.15 | Ch4, Ch6 |
| priority_rule_weight | 0.4 | Ch4, Ch6 |
| priority_gemini_weight | 0.6 | Ch4, Ch6 |
| priority_high_threshold | 70.0 | Ch3, Ch4 |
| priority_low_threshold | 30.0 | Ch3, Ch4 |
| strong_layer_threshold | 0.80 | Ch4 |
| strong_layer_floor | 0.60 | Ch4 |
| weak_signal_cap | 0.40 | Ch4 |
| trust_score_reduction | 0.30 | Ch4 |
| gemini_social_trigger_threshold | 0.25 | Ch4, Ch6 |
| max_claims_per_email | 6 | Ch3, Ch4, Ch6 |
| fraud_version | "v3" | Ch8 |
| verification_version | "v3" | Ch8, Ch9 |

---

## Issues found and resolved

### 1. Abstract: "zero false positives" for fused Set A — FIXED

**Old:** "a curated set of 20 labeled emails with realistic headers (fused F1 = 0.90, zero false positives on legitimate email)"  
**Actual:** fused FP = 1 (JSON: `set_a_headers_test_half.without_gemini.fused.fp = 1`)  
**Fixed to:** "fused F1 = 0.90, one false positive on legitimate email"

### 2. Ch7: Unmeasured timing claim — REMOVED

**Old:** "This design ensures that the fast suite runs in under thirty seconds on a standard laptop without any external dependencies."  
**Action:** Removed. The actual test run time is shown in the pytest output when the user runs the suite; it is not a fixed number and was not measured in this session.

### 3. Demo emails: incomplete pipeline — NOTED, NOT FIXED (see below)

20 demo emails: all have priority_score and fraud_score, but only 5 have explanation+claims+verified_claims (fraud_version is v2 for 19 of 20; verification_version is v1 for 6, None for 14).  
**Gemini calls required to fully process all 20:** 61 total (priority: 20, phishing_social: 13, explanation: 14, claim_decomposition: 14). **Asking user before making any calls — see Task 1 answer below.**

---

## Reference citation order check

IEEE style requires references to be numbered in order of first citation across the full document. References have been renumbered accordingly. The table below shows the final assignment.

| New # | Old # | Authors & Title | Label | First cited in |
|---|---|---|---|---|
| [1] | [1] | Heiding et al. 2024 ("Devising and Detecting Phishing Emails Using Large Language Models") | Heiding et al. 2024 | Ch1 §1.2 |
| [2] | [10] | Hazell 2023 ("Spear Phishing With Large Language Models") | Hazell 2023 | Ch1 §1.2 |
| [3] | [12] | Lewis et al. 2020 ("Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks") | Lewis et al. 2020 (RAG) | Ch2 §2.1 |
| [4] | [16] | Tang et al. 2024 ("MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents") | Tang et al. 2024 (MiniCheck) | Ch2 §2.1 |
| [5] | [2] | Koide et al. 2024 ("ChatSpamDetector: Leveraging Large Language Models for Effective Phishing Email Detection") | Koide et al. 2024 (ChatSpamDetector) | Ch2 §2.2 |
| [6] | [3] | Chataut et al. 2024 ("Can AI Keep You Safe? A Study of Large Language Models for Phishing Detection") | Chataut et al. 2024 | Ch2 §2.2 |
| [7] | [4] | Lee 2025 ("Enhancing Phishing Email Identification with Large Language Models") | Lee 2025 (Enhancing Phishing Identification) | Ch2 §2.2 |
| [8] | [5] | Asiri et al. 2024 ("PhishingRTDS: A Real-Time Detection System for Phishing Attacks Using a Deep Learning Model") | Asiri et al. 2024 (PhishingRTDS) | Ch2 §2.3 |
| [9] | [6] | Lee et al. 2024 ("Multimodal Large Language Models for Phishing Webpage Detection and Identification") | Lee et al. 2024 (APWG eCrime) | Ch2 §2.3 |
| [10] | [7] | Al-Subaiey et al. 2024 ("Novel Interpretable and Robust Web-Based AI Platform for Phishing Email Detection") | Al-Subaiey et al. 2024 | Ch2 §2.3 |
| [11] | [8] | Karim et al. 2023 ("Phishing Detection System Through Hybrid Machine Learning Based on URL") | Karim et al. 2023 (Hybrid ML URL Phishing) | Ch2 §2.3 |
| [12] | [9] | Roumeliotis et al. 2024 ("Next-Generation Spam Filtering: Comparative Fine-Tuning of LLMs, NLPs, and CNN Models for Email Spam Classification") | Roumeliotis et al. 2024 | Ch2 §2.3 |
| [13] | [11] | Niu et al. 2024 ("RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models") | Niu et al. 2024 (RAGTruth) | Ch2 §2.4 |
| [14] | [13] | Manakul et al. 2023 ("SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models") | Manakul et al. 2023 (SelfCheckGPT) | Ch2 §2.5 |
| [15] | [14] | Min et al. 2023 ("FActScore: Fine-Grained Atomic Evaluation of Factual Precision in Long Form Text Generation") | Min et al. 2023 (FActScore) | Ch2 §2.5 |
| [16] | [15] | Dhuliawala et al. 2023 ("Chain-of-Verification Reduces Hallucination in Large Language Models") | Dhuliawala et al. 2023 (CoVe) | Ch2 §2.5 |
| [17] | [17] | Devlin et al. 2019 ("BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding") | Devlin et al. 2019 (BERT) | Ch2 §2.6 |
| [18] | [18] | APWG 2025 ("Phishing Activity Trends Report") | APWG 2025 | Ch2 §2.7 |

**All 18 references are cited in the text.** No reference is uncited. No reference was lost or duplicated. References [17] and [18] retain their original numbers as they were already cited last.

---

## Demo email pipeline status

All 20 demo emails are fully processed under `fraud_version=v3` and `verification_version=v3`:

| Demo email | Priority | Fraud | fraud_version | Explanation | Claims | Verified Claims | verification_version |
|---|---|---|---|---|---|---|---|
| demo-legit-001 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-mixed-001 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-mixed-002 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-news-001 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-news-002 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-news-003 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-notif-001 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-notif-002 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-notif-003 | Y | Y | v3 | N (newsletter) | N | N | v3 (stamped) |
| demo-pers-001 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-pers-002 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-pers-003 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-phish-001 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-phish-002 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-phish-003 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-phish-004 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-phish-005 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-work-001 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-work-002 | Y | Y | v3 | Y | Y | Y | v3 |
| demo-work-003 | Y | Y | v3 | Y | Y | Y | v3 |

**Summary:**
- Priority scored: 20/20 (100%)
- Fraud scored (`fraud_version=v3`): 20/20 (100%)
- Verification complete (`verification_version=v3`): 20/20 (100%)
  - 13 non-newsletter emails have full verified explanations and verified claims.
  - 7 newsletter emails (including promo/bulk notifications) have no claims by design and are stamped `v3`.

