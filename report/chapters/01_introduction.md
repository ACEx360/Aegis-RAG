# CHAPTER 1: INTRODUCTION
#
# Target: 5 pages (~1,400–1,500 words prose; ~1,900 including table cells).
# Trimmed from original: §1.1 condensed to 2 paragraphs, §1.2 to 1 paragraph,
# §1.3 objectives condensed to numbered list, §1.4.3 deviations to 1-sentence each.

---

# CHAPTER 1: INTRODUCTION

## 1.1 OVERVIEW

     Electronic mail remains the dominant medium for professional communication and simultaneously the most common vector for phishing and social-engineering attacks. Agentic artificial intelligence systems that rank and assess email on behalf of the user have therefore attracted sustained research interest. Retrieval-Augmented Generation (RAG) — conditioning a large language model (LLM) on retrieved documents at inference time — has emerged as the standard pattern for such systems, allowing the model to ground its outputs in the user's own email history.

     AegisRAG is a local, self-hosted agentic email assistant that addresses two gaps current RAG-based systems leave open: (1) priority classifiers do not integrate phishing detection, so a phishing email crafted to appear urgent can be ranked highly and reach the user with an endorsement rather than a warning; and (2) the natural-language explanations agentic systems generate for their decisions are not verified against the evidence used to produce them, which is a safety problem for any system that acts autonomously on a user's behalf. AegisRAG closes both gaps in a single unified pipeline that ingests Gmail messages, classifies priority, runs a four-layer phishing detector, generates a combined explanation, and verifies each atomic claim using a local Natural Language Inference (NLI) model. The system runs entirely on a personal machine with no cloud storage of email data and zero mandatory external services. Figure 1.1 shows the high-level pipeline overview.

<!-- FIGURE 1.1 -->
[Figure 1.1: AegisRAG System Overview]
<!-- source: figures/fig1_1_overview.mmd -->
Figure 1.1: AegisRAG System Overview

Legend: The six-stage pipeline ingests email from Gmail or the built-in demo set, classifies priority, detects phishing across four independent layers, generates a combined explanation, verifies each atomic claim using MiniCheck-RoBERTa-Large, and presents the result in a browser-based dashboard.

## 1.2 MOTIVATION

     The motivation for this project arises from three converging trends. First, phishing has become more sophisticated: the Anti-Phishing Working Group has reported sustained growth in reported attacks, and recent academic work has shown that LLM-generated phishing emails can match human-crafted attacks in credibility [1], [2]. Static rule-based filters are poorly equipped against novel, semantically plausible content. Second, agentic AI systems are being granted more autonomy; when such a system takes action and provides a natural-language justification, a hallucinated or ungrounded justification means the user cannot safely evaluate the action. Third, the tools needed to address both gaps are now accessible to individual researchers: pre-trained transformer models for phishing detection and NLI verification run locally on a standard laptop CPU, and the Gemini API provides a capable LLM at low cost. AegisRAG demonstrates that the combination is practically deployable in a unified, self-hosted system.

## 1.3 PROBLEM DEFINITION AND OBJECTIVES

     **Problem Definition.** No lightweight, self-hostable agentic email system currently unifies RAG-based email prioritization, multi-layer phishing detection, and claim-level verification of system-generated explanations in a single coherent pipeline. Existing systems either treat detection and triage as separate products, or generate explanations without verifying those explanations against the evidence used to produce them.

     **Objectives.** This project has five primary objectives:

     1. To build a local email ingestion and normalization pipeline connecting to Gmail via OAuth2, extracting headers, body text, links, and attachment metadata suitable for downstream analysis.

     2. To implement a hybrid priority classifier combining deterministic rule-based scoring with RAG-retrieved historical context and LLM relevance scoring, producing a labelled priority score (High, Medium, or Low) with a numbered evidence justification.

     3. To implement a multi-layer phishing detector comprising four independent providers — sender authentication, URL heuristics, a fine-tuned BERT semantic classifier, and LLM social-engineering analysis — fused into a single fraud confidence score with per-layer transparency.

     4. To generate a combined natural-language explanation, decompose it into atomic claims, and verify each claim against the system's own evidence using a local NLI model, so that only verified claims are presented to the user by default.

     5. To evaluate the system quantitatively: Phase 1 measures phishing detection performance and Phase 2 measures explanation-verification performance, both reported with appropriate caveats on dataset size and construction.

## 1.4 PROJECT SCOPE & LIMITATIONS

### 1.4.1 Scope

     The scope of AegisRAG covers email ingestion from Gmail via OAuth2 (read-only); local processing with no external cloud storage; hybrid priority classification with RAG retrieval; four-layer phishing detection with fused confidence score; claim-level NLI verification; a browser-based dashboard (FastAPI + Jinja2 + HTMX) with five tabs; a self-contained demonstration mode with twenty built-in synthetic emails requiring no API keys; and an evaluation suite covering both detection (Phase 1) and verification (Phase 2).

### 1.4.2 Limitations

     Known limitations of the current implementation include the following. The `gmail.readonly` scope means the system cannot label, move, delete, or reply to any email; all actions are recommendations in the dashboard only. Priority and phishing scores are computed asynchronously in a background worker thread in batches of three, with no real-time streaming. The RAG vector store uses NumPy cosine similarity over SQLite-stored embeddings, which is suitable for hundreds of emails but would need a dedicated vector database for very large inboxes. The claim verifier uses two labels (supported, unsupported) and does not distinguish between claims that are contradicted by evidence and claims for which evidence is simply absent. Evaluation datasets are small: Set A contains 20 labeled emails; Set C contains 14 real-inbox emails; Set B uses a public dataset on which the BERT model was trained, introducing a data-leakage caveat. OAuth tokens expire approximately every seven days while the Google consent screen is in "Testing" mode.

### 1.4.3 Deviations from the Synopsis

     The project synopsis, submitted under the title "MailPilot-Verify," described the intended implementation in terms of tools available at the time of writing. The following concrete decisions differ from the synopsis; none affects the core research contribution.

     1. **No MailPilot code reused.** AegisRAG was built from scratch; reimplementing cleanly produced a more coherent and auditable codebase.
     2. **Gemini (google-genai) instead of Anthropic/OpenAI or open-source LLM.** Gemini provided structured JSON output mode and consistent availability during development.
     3. **No LangChain.** The pipeline is implemented in plain Python; removing the dependency reduces abstraction layers that must be explained in a viva.
     4. **NumPy cosine similarity instead of FAISS or Chroma.** Embeddings are stored in SQLite and compared with NumPy; sufficient for evaluated inbox sizes and removes a large binary dependency.
     5. **No Docker.** The project uses `uv` and a plain Python virtual environment.
     6. **Gmail-provided authentication results instead of live DNS lookups.** Gmail's pre-computed `Authentication-Results` header is more reliable and faster than re-running DNS queries at analysis time.
     7. **No scikit-learn for URL features.** The URL heuristics provider is a pure-Python rule-based module.
     8. **SQLite only (no PostgreSQL).** Sufficient for a local, single-user assistant.
     9. **Jinja2 + HTMX instead of React.** No Node.js or npm build step required.
     10. **Priority and fraud kept separate.** Combining them into a single number would obscure which dimension drove a given decision.
     11. **Fixed weights instead of a trained fusion layer.** The labeled dataset is too small to train reliably; weights are set manually and stored in `settings.py`.
     12. **Two verifier labels instead of three.** MiniCheck produces a single "grounded" probability; a separate contradiction detector would require a different model.
     13. **MiniCheck-RoBERTa-Large loaded via Hugging Face Transformers directly**, rather than through the MiniCheck library's higher-level API.

## 1.5 METHODOLOGIES OF PROBLEM SOLVING

     This project follows a staged, incremental development methodology driven by evaluation at each stage, with three characteristics. First, **staged construction**: the system is built in five sequential stages, each producing an independently functional and testable subsystem (ingest; UI shell; RAG and priority; phishing detection; explanation and verification). Each stage is complete before the next begins, and design may be refined in later stages based on what earlier stages reveal. Second, **incremental integration**: each new module is integrated into the running application immediately so the system is always demonstrable; the background worker is resumable, continuing from where it stopped if interrupted. Third, **evaluation-driven design**: the Phase 1 and Phase 2 evaluation scripts are used to measure, adjust, and re-measure fusion weights, the MiniCheck threshold, and URL heuristic signal weights. This is a structured, repeatable process of parameter tuning — not formal machine learning, as the labeled sets are too small for statistical generalization.

     The methodology does not claim to be Agile, Scrum-based, or sprint-driven. The staged, incremental, evaluation-driven process is a deliberate fit to the constraints of a four-person academic project over a single semester.
