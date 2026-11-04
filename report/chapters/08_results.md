# CHAPTER 8: RESULTS

## 8.1 OUTCOMES

This section reports the quantitative results of the two evaluation scripts described in Chapter 6 (Section 6.3). All numbers are taken directly from the JSON files in `evaluation/results/`. Where a result was produced by an earlier version of the pipeline, the version identifier is stated.

### 8.1.1 Phase 1 — Phishing Detection Results

Phase 1 evaluation was run by `evaluation/phase1_detection.py` using fraud\_version v3. Three evaluation sets were used to assess the detector under different conditions.

**Set A — Curated Header-Rich Set (20 emails)**

Set A consists of twenty hand-crafted emails with realistic Authentication-Results headers, ten labelled phishing and ten legitimate. This set is the most faithful to the deployment scenario because header-based signals (SPF, DKIM, DMARC) are available. Table 8.1 summarises the fused-detector results; Table 8.2 shows per-layer performance.

**Table 8.1: Phase 1 — Fused Detector Results by Evaluation Set**

| Set | Emails | Accuracy | Precision | Recall | F1 | FPR | Avg Latency | Notes |
|---|---|---|---|---|---|---|---|---|
| A (curated, headers) | 20 | 0.90 | 0.90 | 0.90 | 0.90 | 0.10 | 202 ms | Without Gemini layer |
| A (with Gemini) | 20 | 0.90 | 0.90 | 0.90 | 0.90 | 0.10 | 10,826 ms | Gemini layer active |
| B (public dataset, 20% holdout) | 300 | 0.9967 | 0.9898 | 1.00 | 0.9949 | 0.0049 | 1,171 ms | See data-leakage caveat |
| C (real-inbox, hand-labelled) | 14 | 0.5714 | 1.00 | 0.40 | 0.5714 | 0.00 | 232 ms | Without Gemini layer |

**Table 8.2: Phase 1 — Per-Layer Performance on Set A (Without Gemini)**

| Layer | Precision | Recall | F1 | FPR |
|---|---|---|---|---|
| Sender Authentication (SPF/DKIM/DMARC) | 1.00 | 0.70 | 0.8235 | 0.00 |
| URL Heuristics | 0.8571 | 0.60 | 0.7059 | 0.10 |
| BERT Phishing Classifier | 0.70 | 0.70 | 0.70 | 0.30 |
| Gemini Social-Engineering | 0.90 | 0.90 | 0.90 | 0.10 |

The sender-authentication layer achieves zero false positives on Set A because SPF, DKIM, and DMARC results are present and reliable. Its recall of 0.70 reflects that three phishing emails in Set A pass sender-authentication checks — a known real-world pattern where attackers use legitimately registered domains. The URL-heuristics layer contributes complementary signal for these cases.

**Set B — Public Dataset Holdout (300 emails)**

Set B uses the publicly available `ealvaradob/phishing-dataset` (capped at approximately 1,000–2,000 emails for the 80/20 split). The 300-email holdout achieves near-perfect scores. A data-leakage caveat applies: the tuned fraud threshold (0.30, found by sweeping 0.10–0.90 on the 80% split) was optimised on data drawn from the same distribution as the holdout. The very high F1 (0.9949) should therefore be interpreted as an upper bound for in-distribution performance rather than a general deployment estimate.

**Set C — Real Inbox (14 hand-labelled emails)**

Set C is the most challenging set: fourteen real emails drawn from a live Gmail inbox, hand-labelled by the authors. Ten were labelled phishing and four legitimate. The fused detector (without Gemini) achieves precision 1.00 and recall 0.40 (F1 = 0.5714) with zero false positives. Six of the ten phishing emails were missed. When the Gemini social-engineering layer is added, the recall does not improve (standalone Gemini recall = 0.00 on Set C), suggesting that the real phishing emails in this set do not contain the strong urgency or credential-request language that the Gemini prompt targets. The small size of Set C (14 emails) means that these numbers are illustrative rather than statistically reliable.

**Real-Inbox Calibration**

The pipeline was run on 86 real emails (fraud\_version v3) from the authors' Gmail inbox. Two emails were flagged above the fraud threshold (≥ 0.50); both were deliberate test messages sent by the authors. No emails fell in the suspicious range (0.30–0.50). This calibration confirms that the false-positive rate on ordinary inbox traffic is low for this particular inbox, though no ground-truth labels are available for the full 86 emails.

### 8.1.2 Phase 2 — Explanation Verification Results

> **Verification scope.** Of the 86 real emails in the calibration inbox, only 6 received a full LLM explanation and verified claims under verification_version v3. The remaining 80 emails are newsletters (detected from `List-Unsubscribe`, `Precedence: bulk`, or Gmail promotional labels), emails that were opened before the pipeline ran, or emails outside the analysis window; they have no claims to verify. The `verification_version=v3` stamp on those 80 records that they were considered under the v3 configuration, not that MiniCheck was run on them. The Phase 2 evaluation results below come from the separate evaluation scripts in `evaluation/`, not from live inbox processing.

Phase 2 evaluation was run by `evaluation/phase2_verification.py` (verification\_version v2, MiniCheck threshold 0.10). Results in the JSON file were produced before the verification\_version was bumped to v3 in `app/settings.py`; the evaluation data are unchanged, and the JSON file reflects the configuration in effect at evaluation time.

**Part 1 — Synthetic Benchmark (30 cases)**

Thirty synthetic cases (15 for threshold tuning on the development split, 15 for evaluation on the test split) were constructed with fixed, known-correct labels. The threshold sweep over 0.10–0.90 on the development split selected 0.10 as the optimal threshold (dev F1 = 0.9375). On the 15 test cases (40 claims total):

- Precision: 0.7143, Recall: 1.00, F1: 0.8333, Accuracy: 0.85
- Ungrounded-claim rate before verification: 37.5 %
- Ungrounded-claim rate after verification: 0.0 %
- Relative reduction: 100 %

The 100 % reduction is by construction: in Part 1, the synthetic cases are designed so that every unsupported claim is flagged. This result validates the verifier's basic ability to identify unsupported claims in a controlled setting, but does not measure real-world performance.

**Part 2 — LLM-Generated Claims with Author Review (90 claims)**

Ninety claims were drawn from LLM-generated explanations for real and demo emails and labelled by an AI assistant following a written labelling protocol, then reviewed by the authors. Table 8.3 summarises the results.

**Table 8.3: Phase 2 — Verifier Performance on Part 2 (90 claims)**

| Metric | Value |
|---|---|
| True Positives (correctly flagged unsupported) | 15 |
| False Positives (good claims incorrectly flagged) | 10 |
| False Negatives (unsupported claims missed) | 10 |
| True Negatives (supported claims correctly passed) | 55 |
| Precision | 0.60 |
| Recall | 0.60 |
| F1 Score | 0.60 |
| Accuracy | 0.7778 |
| Ungrounded-claim rate before verification | 0.2778 (27.78 %) |
| Ungrounded-claim rate after verification | 0.1538 (15.38 %) |
| Relative reduction | 44.62 % |

The verifier reduces the ungrounded-claim rate by 44.62 % (from 27.78 % to 15.38 %) on this set. Ten false positives indicate that the verifier removes some well-supported claims; this is consistent with the low threshold of 0.10, which trades precision for higher recall. The 10 false negatives show that some genuinely unsupported claims pass the verifier — primarily cases where the claim and the evidence use overlapping vocabulary without a genuine logical entailment relationship.

**Limitations and Caveats**

The labelling protocol for Part 2 defines "supported" as consistent with the system's own retrieved evidence, not independently verifiable. Labels were drafted by an AI assistant and reviewed by the authors; inter-annotator agreement was not formally measured. The synthetic cases in Part 1 cannot substitute for a large, independently annotated benchmark. These results are presented as a proof-of-concept demonstration rather than a definitive performance claim.

### 8.1.3 Summary of Key Findings

The phishing detector performs well on curated and in-distribution data (Set A F1 = 0.90; Set B F1 = 0.9949) but shows limited recall on real-world phishing that passes sender-authentication checks and lacks obvious social-engineering language (Set C recall = 0.40). The explanation verifier reduces ungrounded claims by approximately 45 % on LLM-generated explanations with a precision and recall of 0.60, demonstrating that claim-level verification adds measurable value while acknowledging room for improvement.

## 8.2 SCREEN SHOTS

The following figures illustrate the main views of the AegisRAG dashboard. Screenshots were captured in Demo mode with the twenty built-in sample emails. All screenshots are presented in greyscale.

**Figure 8.1: Priority Tab — Inbox View**

[Screenshot placeholder: The Priority tab showing unread emails sorted by priority score, with coloured left borders (amber for high priority, green for low), badges displaying priority label and fraud percentage, and the "N flagged" banner when fraudulent emails are present.]

**Figure 8.2: Expanded Email Row — Summary Panel**

[Screenshot placeholder: An expanded email row with the inner-tab navigation (Summary | Verified Explanation | Detection Layers | Headers | Body) visible, showing the email subject, sender, date, and the Summary tab content with the priority score and fraud confidence displayed as callout badges.]

**Figure 8.3: Verified Explanation Panel**

[Screenshot placeholder: The Verified Explanation tab showing atomic claims, each labelled with an entailed or unsupported badge and the best-matching evidence snippet below it. Removed (contradicted or unsupported) claims are shown in a collapsed "Removed claims" section.]

**Figure 8.4: Detection Layers Panel**

[Screenshot placeholder: The Detection Layers tab showing each phishing-detection provider (Sender Auth, URL Heuristics, BERT Classifier, Gemini Social-Engineering), its individual score (0–1), reason string, and "not configured" label for providers with missing API keys.]

**Figure 8.5: Flagged / Fraud Tab**

[Screenshot placeholder: The Flagged tab showing emails with fraud confidence above the threshold, sorted by fraud score descending, with red left borders and "Likely phishing" badges.]

**Figure 8.6: Feed Tab — Newsletter View**

[Screenshot placeholder: The Feed tab showing newsletters (emails with List-Unsubscribe header or CATEGORY\_PROMOTIONS label) in a clean card layout, separate from the Priority inbox.]

**Figure 8.7: Settings Page**

[Screenshot placeholder: The Settings page showing the currently configured providers (API keys present/absent), the fraud and suspicious thresholds, and the minicheck threshold, all drawn from the .env configuration.]

**Figure 8.8: Previous Messages Tab**

[Screenshot placeholder: The Previous Messages tab showing already-opened emails sorted by date descending, with the same row format as the Priority tab but showing all emails regardless of priority score.]

