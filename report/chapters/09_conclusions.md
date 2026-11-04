# CHAPTER 9: CONCLUSIONS

## 9.1 CONCLUSIONS

AegisRAG is a local, self-hosted agentic email assistant for Gmail that combines retrieval-augmented generation, multi-layer phishing detection, and claim-level explanation verification into a single integrated pipeline. The system was built from scratch using Python 3.13, FastAPI, SQLite, sentence-transformers, MiniCheck, and the Google Gemini API, with a Jinja2 and HTMX front end. It runs without Docker, without external databases, and without any mandatory API keys; a built-in Demo mode with twenty realistic sample emails makes the application fully functional out of the box.

The core contribution of this project is the integration of three independent analytical capabilities — email prioritisation, phishing detection, and claim-level explanation verification — into a coherent pipeline in which the same retrieved context feeds all three paths. This design avoids redundant retrieval and keeps the system's explanations grounded in the same evidence that drives its decisions.

**Phishing Detection.** The four-layer detector (sender authentication, URL heuristics, a BERT-based phishing classifier, and Gemini social-engineering analysis) achieves an F1 score of 0.90 on the curated evaluation set (Set A, 20 emails with realistic headers). On an in-distribution public-dataset holdout (Set B, 300 emails), the fused detector reaches F1 = 0.9949; this high figure carries a data-leakage caveat noted in Chapter 8. On real-inbox emails (Set C, 14 hand-labelled), recall drops to 0.40 with precision 1.00, reflecting a class of phishing attacks that pass sender authentication and avoid obvious social-engineering language. The sender-authentication layer is the strongest individual contributor (F1 = 0.8235 on Set A), with zero false positives on that set.

**Explanation Verification.** The MiniCheck-based verifier decomposes Gemini-generated explanations into atomic claims and checks each claim against the system's own retrieved evidence. On 90 LLM-generated claims (Part 2, threshold 0.10), the verifier achieves precision 0.60 and recall 0.60 (F1 = 0.60), reducing the ungrounded-claim rate from 27.78 % to 15.38 % — a relative reduction of 44.62 %. The result demonstrates that claim-level verification provides a measurable improvement in explanation quality while acknowledging that the current model removes some well-supported claims (10 false positives) and misses some unsupported ones (10 false negatives).

**System Design Decisions.** Several design choices made during implementation diverged from the original synopsis. NumPy cosine similarity replaced FAISS because the inbox sizes encountered in testing (fewer than a few thousand emails) do not benefit from approximate nearest-neighbour indexing. Fixed fusion weights replaced a trained layer for the same reason: the labelled dataset available for training is too small to reliably estimate weights, and interpretability is more important than marginal accuracy gain. The MiniCheck verifier uses two labels (supported / unsupported) rather than three (entailed / neutral / contradicted) because the distinction between neutral and contradicted is difficult to annotate reliably at this scale. These trade-offs are documented in Section 1.4.3.

**Honest Assessment.** The system performs reliably on in-distribution data and in Demo mode with zero configuration. Its main limitation is recall on real-world phishing that evades header-based signals. The verification results are promising but depend on AI-assisted labels reviewed by the authors; an independently annotated benchmark would provide stronger evidence.

## 9.2 FUTURE WORK

Several directions for future development follow directly from the limitations identified in Chapters 7 and 8.

**Scalable Vector Search.** The current retrieval component stores all email embeddings in a NumPy array and performs a linear cosine-similarity scan. For inboxes with tens of thousands of emails, this approach will become slow. A drop-in replacement using FAISS or Chroma would provide sub-linear retrieval time without changing the surrounding pipeline. The system was architected to make this replacement straightforward.

**Improved Real-Inbox Recall.** The low recall on Set C suggests that the detector should be extended with additional signals such as header-field timing anomalies, reply-to mismatches, and language-model perplexity scores on the email body. Integrating Google Safe Browsing and URLhaus/OpenPhish threat-intelligence feeds (stubbed as optional providers) would add a known-bad-URL signal that does not depend on heuristic pattern matching.

**Active Learning for Fusion Weights.** The current fusion weights are manually tuned constants. Collecting binary feedback from users (correct/incorrect flagging decisions) would allow the weights to be updated through logistic regression or a Bayesian update rule. Even a modest amount of user feedback would likely improve real-inbox recall without risking overfitting.

**Three-Label NLI Verification.** The current verifier uses two labels. Extending to three labels (supported, unsupported, contradicted) would allow the UI to distinguish claims that are merely unverified from those that actively conflict with the evidence. A larger annotated dataset and a model fine-tuned on domain-specific email explanations would be needed.

**Real-Time Streaming Analysis.** The current pipeline processes new emails in batches when the user opens the dashboard. A background worker that monitors the Gmail push-notification webhook and processes emails as they arrive would reduce latency and make the Priority tab reflect the actual inbox state continuously.

## 9.3 APPLICATIONS

**Personal and Small-Organisation Email Security.** AegisRAG is designed for individuals and small organisations that receive phishing and social-engineering attacks but lack the resources to deploy commercial email-security gateways. The system runs entirely on a local machine, keeps all email data within the user's environment, and adds a prioritisation layer that reduces the cognitive load of a high-volume inbox.

**Explainable AI in Security Contexts.** The claim-verification component addresses a general problem in security AI: explaining why a model made a particular decision in language that users can understand and trust. The pipeline architecture — retrieve evidence, generate explanation, decompose into claims, verify each claim — is applicable to any domain where decisions must be explained and the explanations must be grounded in retrievable evidence.

**Educational Tool for Phishing Awareness.** In Demo mode, AegisRAG provides a self-contained illustration of how phishing detection works. The Detection Layers panel shows the contribution of each individual signal, and the Verified Explanation panel shows how the system builds and checks its reasoning. This makes the system suitable as a teaching tool in courses on cybersecurity or applied machine learning.

