# CHAPTER 3: SOFTWARE REQUIREMENTS SPECIFICATION
#
# Target: 8 pages (~2,240–2,400 words).
# Section headings follow institute format exactly.

---

# CHAPTER 3: SOFTWARE REQUIREMENTS SPECIFICATION

     This chapter specifies the requirements for AegisRAG. The specification covers the system's assumptions, functional and non-functional requirements, external interfaces, and system environment requirements. It concludes with a description of the development model applied.

## 3.1 ASSUMPTIONS AND DEPENDENCIES

     The following assumptions underlie the AegisRAG design and must hold for the system to function as described.

     1. The user has a Google account and can authorize the application through the Google OAuth2 consent screen using a Desktop application client type, registered in Google Cloud Platform with the `gmail.readonly` scope.

     2. Python 3.13 and the `uv` package manager are installed on the host machine. Dependencies are installed from `pyproject.toml` via `uv sync`.

     3. The Hugging Face models `sentence-transformers/all-MiniLM-L6-v2`, `lytang/MiniCheck-RoBERTa-Large`, and `ealvaradob/bert-finetuned-phishing` have been downloaded to the local Hugging Face cache before offline use. If a model is absent, the corresponding functionality is disabled gracefully.

     4. A Gemini API key is available in `.env` if LLM-based priority scoring and social-engineering analysis are required. Without a key, the system falls back to deterministic rules for priority and omits the Gemini layer from fusion.

     5. All configuration values — API keys, file paths, model names, thresholds, and weights — are supplied via the `.env` file. No secrets are hardcoded in source code.

     6. The host machine has internet access for the initial OAuth2 authentication flow and for Gemini API calls. After initial authentication, the system can operate with no outbound connections except to the Gemini API.

     7. Gmail tokens expire approximately every seven days while the Google OAuth2 consent screen is in "Testing" mode. The user must re-authenticate after token expiry.

     8. The SQLite database file (`aegis.db`) is stored locally on the host machine and is excluded from version control via `.gitignore`.

## 3.2 FUNCTIONAL REQUIREMENTS

### 3.2.1 Email Ingestion and Normalization

     The system shall connect to the Gmail API using OAuth2 and retrieve emails from the user's inbox within a configurable sync window (default: 14 days, up to 100 messages per sync). Each message shall be normalized into a structured record containing: subject, sender, recipients, UTC timestamp, plain-text body, raw HTML body, extracted links (text and href), all raw headers as a JSON array, attachment metadata, Gmail labels, and a boolean read-state flag. The system shall never render raw HTML from email messages in the browser without a sandboxed iframe with scripts disabled. A demo mode shall be available, loading twenty built-in synthetic emails without requiring Gmail credentials.

### 3.2.2 RAG-Based Priority Classification

     The system shall compute a sentence-transformer embedding for each email (subject + sender + first 500 characters of body text) and store it in the SQLite database. For each unread email, it shall retrieve the top-2 most similar past emails using NumPy cosine similarity. A rule engine shall evaluate known contacts, Gmail labels (IMPORTANT, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, CATEGORY_UPDATES), newsletter headers, urgency keywords, and collaboration keywords to produce a rule score (0–100). If the Gemini API is configured, the system shall call Gemini with numbered evidence items and the email body (truncated to 2,000 characters) for a relevance score; the final priority score shall be 0.4 × rule_score + 0.6 × gemini_score. Bulk and promotional emails shall be capped at 40. The priority label shall be High (score ≥ 70), Medium (30 < score < 70), or Low (score ≤ 30). All LLM outputs shall be cached in the SQLite LLMCache table keyed by (gmail_id, task_type, prompt_version).

### 3.2.3 Multi-Layer Phishing Detection

     The system shall evaluate each email through four independent detection providers and fuse their scores into a single fraud confidence value.

     - **Layer 1 — Sender Authentication:** Parses the topmost `Authentication-Results` header from mx.google.com and extracts SPF, DKIM, and DMARC outcomes. Detects From-domain / Return-Path mismatches, display-name spoofing, and credential-soliciting content from unauthenticated senders. Abstains (available = False) if no trusted header is present.

     - **Layer 2 — URL and Domain Heuristics:** Analyses all links from the email body and HTML, checking for IP-address hosts, lookalike domains, punycode IDN domains, deceptive subdomains, anchor-text vs. href mismatches, URL shorteners, open-redirect parameters, and dangerous payload extensions. Abstains if no links are present.

     - **Layer 3 — BERT Semantic Classifier:** Runs `ealvaradob/bert-finetuned-phishing` over the email body (truncated to 512 tokens) and records the phishing probability and inference latency. Degrades gracefully if model weights are not cached.

     - **Layer 4 — LLM Social Engineering Analysis:** If the Gemini API is configured and the preliminary score from the other three layers meets or exceeds 0.25, calls Gemini with the email body (enclosed in strict XML delimiters) and requests a structured JSON assessment of four social-engineering vectors: urgency and threats, authority impersonation, credential harvesting, and financial coercion.

     Fusion applies a re-normalized weighted average (weights: sender_auth = 0.35, url_heuristics = 0.35, bert_phishing = 0.15, gemini_social = 0.15; unavailable layers are dropped and weights re-normalized). If any layer reaches the strong-layer threshold (0.80) with a confirmed strong indicator, the final score is floored at 0.60. If any threat-intelligence provider reports a malicious URL, the score is floored at 0.90. If sender authentication is fully clean and no strong URL signal exists, the score is capped below the Suspicious threshold. If the sender is in the user's sent-contacts and SPF and DKIM both pass, a trust discount of 0.30 is applied. The fraud label shall be "Likely phishing" (score ≥ 0.50), "Suspicious" (0.30 ≤ score < 0.50), or "Low risk" (score < 0.30).

### 3.2.4 Explanation Generation and Claim Decomposition

     The system shall generate a single unified natural-language explanation for each analyzed email, produced by Gemini conditioned on numbered system-built evidence items from the priority and fraud evidence fields. If Gemini is unavailable, a deterministic fallback combining the priority and fraud reason strings shall be used. Gemini shall then decompose the explanation into at most six atomic, self-contained claims in JSON format. Each claim shall not use pronouns or raw citation markers and shall explicitly name the sender, domain, header, or attachment it refers to.

### 3.2.5 Claim-Level NLI Verification

     The system shall verify each atomic claim against the assembled evidence set using the MiniCheck-RoBERTa-Large NLI model. For each claim, it shall compute the support probability against the full evidence document and against each individual evidence item in a single batched forward pass; the maximum of these probabilities is taken as the final confidence. A claim shall be labelled "supported" if the confidence meets or exceeds the configured threshold (default: 0.10 in `settings.py`, tuned on the Part 1 development split; the post-hoc exploratory sweep covered thresholds from 0.10 to 0.90). Supported claims shall include a citation to the best-matching evidence item; unsupported claims shall be filtered from the user-facing narrative and stored for optional display. The system-generated verdict line shall be displayed unconditionally and shall not be subjected to NLI verification.

### 3.2.6 Dashboard and User Interface

     The system shall provide a browser-based dashboard with five tabs: Priority (unread, non-newsletter, non-flagged emails sorted by score descending), Previous Messages (opened emails, newest first), Feed (newsletters only), Flagged/Fraud (emails with fraud_score ≥ 0.50), and Settings. Each email shall appear as a collapsible row with a colour-coded left border (red for likely fraud, amber for high priority, green for normal, grey for newsletter). Expanding a row shall load a five-tab inner panel (Summary, Verified Explanation, Detection Layers, Headers, Body) via HTMX lazy loading; the first expansion shall record the `opened_at` timestamp via a POST request. The Priority tab shall display a banner listing the count of flagged emails when threats exist.

### 3.2.7 Demo Mode Operation

     When DEMO_MODE is enabled (the default), the system shall operate with twenty built-in synthetic emails without any Gmail credentials, Gemini API key, or locally cached models. The demo emails shall include realistic `Authentication-Results` headers with a mix of passing and failing outcomes, at least one email that passes SPF but exhibits phishing indicators in other layers, at least one legitimately urgent email, and four to five pre-opened emails. All placeholder scores in demo mode shall be marked `is_demo = True` in the database.

## 3.3 EXTERNAL INTERFACE REQUIREMENTS

### 3.3.1 User Interfaces

     The user interface is a server-rendered web application at `http://127.0.0.1:8000`, built using Jinja2 server-side templates, HTMX for dynamic partial-page updates, and Tailwind CSS from CDN. The interface requires no JavaScript framework or build step and is designed for a modern desktop browser. The API is also exposed as a Swagger UI at `/docs`, with all endpoints tagged, described, and accompanied by example responses.

### 3.3.2 Hardware Interfaces

     The system interacts with no physical hardware directly. It uses the host CPU for model inference (sentence-transformer embeddings, BERT classification, and MiniCheck NLI). If a CUDA-capable GPU is available, the MiniCheck model will use it automatically; otherwise CPU is used.

### 3.3.3 Software Interfaces

     - **Gmail API:** Email retrieval (read-only) via OAuth2 Desktop application flow using `google-auth-oauthlib`.
     - **Google Gemini API (google-genai SDK):** Priority relevance scoring, phishing social-engineering analysis, explanation generation, and claim decomposition. Model name configured via `GEMINI_MODEL` in `.env`; up to six API keys supported for round-robin rotation.
     - **Hugging Face Transformers:** MiniCheck-RoBERTa-Large and BERT phishing classifier, both loaded from local cache only (`local_files_only=True`, `HF_HUB_OFFLINE=1`).
     - **sentence-transformers:** Email embeddings via `all-MiniLM-L6-v2`.
     - **SQLAlchemy 2.0 ORM:** All database interactions; WAL journal mode, 30-second busy timeout.
     - **FastAPI / Uvicorn:** Web server and API framework.

### 3.3.4 Communication Interfaces

     All external communication uses HTTPS. The Gmail API and Gemini API are reached over HTTPS. The local web server uses plain HTTP over loopback (127.0.0.1:8000), which is acceptable for a local, single-user application. No email content is transmitted externally other than to the Gemini API (for LLM analysis) and the Gmail API (for retrieval).

## 3.4 NONFUNCTIONAL REQUIREMENTS

### 3.4.1 Performance Requirements

     The background analysis worker shall process emails in batches of three, pausing 500 ms between batches to avoid resource contention. Models are loaded on first use, not at startup. The application shall start and serve the Priority tab within five seconds in demo mode. Analysis of a single email without LLM calls shall complete in under two seconds on a standard laptop CPU. The UI shall show analysis progress via HTMX polling every two seconds.

### 3.4.2 Safety Requirements

     The application shall operate with the `gmail.readonly` OAuth2 scope only. It shall not delete, modify, label, move, or reply to any Gmail message. All recommended actions shall be recorded in the dashboard only. Email HTML shall never be rendered directly; the body tab shall display plain text only.

### 3.4.3 Security Requirements

     No API keys, OAuth tokens, or email content shall be hardcoded in source code or committed to version control. All secrets are read from `.env`, which is listed in `.gitignore`. Prompt injection attacks shall be mitigated by enclosing email body content in strict XML delimiters (`<email_content>`, `<body>`) and instructing the LLM to treat content between those tags as untrusted data. Gemini response content displayed in the UI shall be HTML-escaped via Jinja2's automatic escaping before any citation tokens are styled, making the UI immune to stored XSS attacks via email content.

### 3.4.4 Software Quality Attributes

     - **Maintainability:** All configuration parameters are consolidated in `app/settings.py`. Each module has a docstring explaining its purpose and design rationale. Functions are kept short. There is no unused code.
     - **Testability:** The test suite covers 113 fast tests and 1 slow test across 17 test files. Tests use a separate in-memory SQLite database and a `TESTING=1` environment flag. The `ruff` linter is run as part of the quality check.
     - **Graceful Degradation:** Every optional component — Gemini API, BERT model, MiniCheck model, Gmail authentication — has a defined fallback behaviour. The application runs in demo mode with zero external keys.
     - **Resumability:** The background worker tracks `fraud_version` and `verification_version`; emails already analyzed at the current version are skipped, allowing interrupted runs to be resumed.

## 3.5 SYSTEM REQUIREMENTS

### 3.5.1 Database Requirements

     AegisRAG uses SQLite as its sole database engine. The database file is created automatically at the path specified by `DB_URL` in `.env` (default: `aegis.db` in the project root). WAL journal mode is enabled with a 30-second busy timeout to handle concurrent access from the web server thread and the background worker. The two ORM-mapped tables are `emails` (storing all ingested data including embeddings, analysis scores, evidence items, and claim verification results as JSON columns) and `llm_cache` (keyed by gmail_id, task_type, and prompt_version).

### 3.5.2 Software Requirements (Platform Choice)

     The recommended software environment is as follows. Values listed as "recommended" reflect the development environment; the application may function with similar versions, but this has not been verified.

     - Python 3.13 (required; `pyproject.toml` specifies `>=3.13,<3.14`)
     - `uv` package manager (recommended) or `pip` with a virtual environment
     - PyTorch (CPU variant; recommended: ≥ 2.15.0)
     - sentence-transformers ≥ 6.2.0; transformers (Hugging Face); FastAPI ≥ 0.162.0
     - SQLAlchemy ≥ 2.1.6; google-genai ≥ 2.33.0; Jinja2 ≥ 3.1.6
     - numpy ≥ 2.5.4; pydantic-settings ≥ 2.16.1
     - A modern web browser (Chrome, Firefox, or Edge)

### 3.5.3 Hardware Requirements

     The following hardware configuration is recommended based on the development environment. Values are recommendations; actual minimum requirements have not been formally measured.

     - RAM: 8 GB recommended (BERT and MiniCheck together occupy approximately 2–3 GB when both are loaded)
     - Disk: 10 GB recommended free space (PyTorch CPU: approximately 700 MB; sentence-transformers model: approximately 90 MB; BERT phishing model: approximately 420 MB; MiniCheck-RoBERTa-Large: approximately 1.5 GB; application and database: < 100 MB)
     - CPU: Any modern x86-64 processor; no GPU is required
     - GPU: Optional; if a CUDA-capable GPU is available, MiniCheck will use it automatically

## 3.6 ANALYSIS MODELS: SDLC MODEL TO BE APPLIED

     AegisRAG is developed using an **incremental development model**. The system is divided into five increments (stages), each adding a functional subsystem to the application. Each increment is planned, designed, implemented, and tested before the next begins, and the application is in a runnable and demonstrable state at the end of every increment.

     The five increments are: (1) Core Infrastructure — database schema, Gmail ingestion, OAuth flow, demo email set, Gemini client wrapper, FastAPI skeleton; (2) UI Shell — Jinja2 templates, HTMX panel loading, tab navigation, collapsible rows, read-state tracking; (3) Priority Classification and RAG — sentence-transformer embeddings, NumPy vector store, rule engine, hybrid LLM classifier, background worker; (4) Phishing Detection — sender authentication, URL heuristics, BERT classifier, Gemini social-engineering provider, fusion engine; (5) Explanation and Verification — explanation generator, claim decomposer, MiniCheck verifier, UI integration, Phase 1 and Phase 2 evaluation scripts.

     The incremental model was chosen because each stage produces independently testable software, allowing defects to be isolated to the most recently added increment; the application can be demonstrated at any stage; and the evaluation-driven design of Stages 4 and 5 requires iterative measurement and parameter adjustment, which fits naturally into the increment cycle. Figure 3.1 illustrates the cycle.

<!-- FIGURE 3.1 -->
[Figure 3.1: Incremental Development Model Applied to AegisRAG]
<!-- source: figures/fig3_1_sdlc.mmd -->
Figure 3.1: Incremental Development Model Applied to AegisRAG

Legend: Each increment (Stage 1 through Stage 5) passes through the same four phases — Plan, Design, Implement, Test — before the next increment begins. The application is demonstrable at the end of every stage.
