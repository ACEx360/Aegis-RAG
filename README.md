# AegisRAG — Self-Hosted Agentic Email Assistant

A local, self-hosted agentic email assistant for Gmail that prioritizes emails, detects phishing/fraud, and verifies its own explanations using claim-level NLI verification.

---

## Stage 1 — Ingestion, Authentication & Core Infrastructure
- **Project Scaffolding**: Structured layout per spec, `.env.example`, `.gitignore`, dependencies.
- **SQLite Database Models (SQLAlchemy 2.0)**:
  - `Email`: Ingested emails with headers, snippets, body, attachments, read-state, and `opened_at` tracking.
  - `LLMCache`: Structured caching keyed by `(gmail_id, task_type, prompt_version)`.
- **Gmail Ingestion & OAuth**:
  - OAuth Desktop flow via `google-auth-oauthlib` executed in background threads with non-blocking locks and timeouts.
  - Normalizer converting Gmail API messages into clean schemas while preserving duplicate headers.
- **Demo Mode**:
  - 20 realistic sample emails covering phishing (with SPF pass & fail), newsletters, normal work/personal, receipts, and legit-urgent emails.
- **Gemini Wrapper**:
  - Synchronous `GeminiClient` supporting SQLite caching and exponential backoff retry for 429 rate limits.

---

## Stage 2 — UI Shell (Gmail-like Layout & Swagger-style Collapsible Rows)
- **Zero Node/npm Stack**:
  - Built strictly using Jinja2 templates + HTMX (1.9.12) + Tailwind CSS via CDN.
- **Left Sidebar Navigation with Live Badges**:
  - 📥 **Priority** (Home): Unread emails prioritized by `priority_score DESC`. Excludes newsletters and emails flagged as likely fraud. Shows a notification banner linking to Flagged/Fraud if threats exist.
  - 🕒 **Previous Messages**: Read or opened emails (`opened_at IS NOT NULL` or `is_read == True`), sorted newest first. Excludes newsletters.
  - 📰 **Feed**: Subscribed newsletters only (detected via `List-Unsubscribe`, `Precedence: bulk`, or `CATEGORY_PROMOTIONS` / `CATEGORY_UPDATES`).
  - 🚨 **Flagged / Fraud**: High threat confidence emails (`fraud_score >= threshold`), sorted by fraud confidence descending.
  - ⚙️ **Settings**: Runtime mode toggle (`demo` vs `real`), Gmail OAuth status indicators, pipeline thresholds, and one-click email sync.
- **Top Search Bar**:
  - Live client-side debounce (300ms) filtering across subject, sender, and snippet within the active tab.
- **Swagger-Style Collapsible Email Rows**:
  - Thick 4px color-coded left border:
    - 🔴 **Red**: Likely fraud (`fraud_score >= 0.5`)
    - 🟡 **Amber**: High priority (`priority_label == "High"`)
    - 🟢 **Green**: Low/Medium priority
    - ⚪ **Grey**: Newsletter / Feed
  - Badges for Priority (High/Medium/Low or "Not analyzed yet"), Fraud confidence, and Newsletter tags.
  - Click to expand with smooth rotation chevron.
- **Lazy Loaded 5-Tab Inner Panel**:
  - **Summary**: Quick metadata, priority/fraud indicators, and SPF/DKIM flags.
  - **Verified Explanation**: Clear placeholder notice for Stage 5 NLI claim verification (no fake data).
  - **Detection Layers**: Clear placeholder notice for Stage 4 multi-layer threat detection (no fake data).
  - **Headers**: Complete monospace display of all raw headers, preserving duplicate entries (e.g. `Received`).
  - **Body**: Strictly plain text (`body_text`). Raw HTML rendering is completely disabled for security; links remain plain non-clickable text.
- **Read State & Transition**:
  - Expanding an email triggers row expansion and marks `opened_at` (via `POST /ui/emails/{id}/panel`), dynamically updating tab badges out-of-band and moving it to **Previous Messages** on next refresh.
  - `GET /ui/emails/{id}/panel` remains strictly read-only and never sets `opened_at`.
- **Placeholder Scores (Removed in Stage 3)**:
  - Previously used `placeholder_scores.py`; replaced by the hybrid rules + RAG priority engine in Stage 3.

---

## Stage 3 — RAG + Priority Classifier + Background Worker & Evidence Generation
- **Local Embeddings (sentence-transformers)**:
  - Uses `all-MiniLM-L6-v2` loaded lazily on first access. Runs fast on CPU via PyTorch.
  - Embeds subject + sender + first ~500 chars of `body_text`.
- **NumPy Vector Store**:
  - In-memory/NumPy cosine similarity over SQLite-stored embedding vectors — no bloated external vector databases or FAISS dependencies.
- **RAG Email History & Known Contacts**:
  - Automatically derives trusted contacts from the user's `SENT` mail (or demo sent contacts).
  - Indexes past email interactions to provide real retrieval context for priority classification.
- **Hybrid Priority Classifier**:
  - Combines deterministic rule heuristics (known contacts, deadlines, urgency keywords, Gmail category/importance labels) with Gemini relevance scoring.
  - Configurable blend weights (`0.4` rules / `0.6` LLM).
  - Strict guardrails: prompt injection defenses via XML delimiters, body truncation, and hard rule caps (bulk/promotions can never exceed Medium/40 score regardless of LLM claims).
- **System-Constructed Numbered Evidence**:
  - System constructs numbered evidence items (rule facts, retrieved snippets, header flags); Gemini cites these exact evidence item numbers in its justification.
- **Resumable Non-Blocking Background Worker**:
  - Background thread analyzes unread emails newest-first in small batches (batch size 3) with thread-safe DB sessions.
  - Respects rate limits with exponential backoff and pauses.
  - Live progress tracking displayed in the UI via HTMX polling every 2s ("Analyzing X/Y").
- **SQLite Concurrency & Normalizer Hardening (Step 1 Fixes)**:
  - Enabled WAL journal mode, 30s busy timeout, and NORMAL synchronous mode to eliminate database lock contention during concurrent sync and panel viewing.
  - Rewrote HTML-to-text normalizer to safely handle void tags (`<meta>`, `<link>`, `<br>`, `<img>`), extract link details (hostnames, decoded redirect targets, image anchors), and provide fallback to image alt text and snippets.

---

## Stage 4 — Multi-Layer Phishing Detection & Evaluation (Pass 4a & 4b Complete)
- **Layer 1: Sender Authentication (`app/phishing/providers/sender_auth.py`)**:
  - Trusts strictly the topmost `Authentication-Results` header with `authserv-id: mx.google.com`. Ignores forged/extra headers and records an evidence line.
  - Parses SPF, DKIM, DMARC outcomes (`pass`, `fail`, `softfail`, `neutral`, `none`).
  - Detects `From` vs `Return-Path` / `smtp.mailfrom` domain mismatches (catches attacker relay spoofing; recognizes ESP bounce domains when DMARC passes).
  - Detects `From` vs `Reply-To` domain discrepancies (flags BEC and reply rerouting; handles shared organization SLDs under alternate marketing TLDs).
  - Flags display name anomalies (embedded foreign emails or brand name spoofing).
  - Abstains (`available=False`) when trusted auth headers are absent.
- **Layer 2: URL & Domain Heuristics (`app/phishing/providers/url_heuristics.py`)**:
  - Scans all extracted HTML links and plain body URLs.
  - Flags IP-address hosts, lookalike/typosquatting domains (`paypa1`, `micros0ft`), deceptive subdomains embedding foreign TLDs (`naukri.com.evil.net`), punycode, URL shorteners, and insecure HTTP on auth paths.
  - Flags anchor text vs real `href` host mismatches (e.g. text says `paypal.com` but points to `paypa1.example.com`).
  - Flags open redirect / forwarding parameters pointing to external domains (e.g. `google.com/url?q=evil.com`).
  - Includes an allowlist for known ESP/tracking services (`naukri.com`, `sendgrid.net`, `mailchimp.com`, etc.) that exempts subdomain penalties via registered-domain suffix checks, while never exempting anchor mismatches or external redirects.
  - Abstains (`available=False`) with a clean explanation when an email contains no links.
- **Layer 3: Local BERT Semantic Classifier (`app/phishing/providers/bert_phishing.py`)**:
  - Fine-tuned transformer model (`ealvaradob/bert-finetuned-phishing`) loaded locally from Hugging Face cache on CPU (`local_files_only=True`).
  - Truncates to strict 512-token limit and measures per-email CPU latency in milliseconds.
  - Detects rhetorical manipulation, urgency cues, and non-lexical phrasing.
  - Gracefully degrades to `available=False` if model weights are not installed.
- **Layer 4: LLM Social Engineering Check (`app/phishing/providers/gemini_social.py`)**:
  - Gemini structured JSON analysis evaluating 4 psychological attack vectors: urgency/threats, authority impersonation, credential harvesting, and financial coercion.
  - Prompt injection defense: email content is wrapped in strict boundary markers and treated strictly as untrusted data.
  - Quota optimization: only triggered when preliminary risk score $\ge 0.25$.
  - SQLite caching keyed by `(gmail_id, task_type='phishing_social', prompt_version='v2')`.
- **Risk Fusion Engine (`app/phishing/fusion.py`)**:
  - Weighted average with automatic re-normalization across operational layers only.
  - Strong layer floor: if any available layer scores $\ge 0.80$ with a strong threat indicator (IP host, punycode, lookalike domain, anchor mismatch, auth failure), final confidence is floored at $\ge 0.60$.
  - Sent-contacts trust discount ($-30\%$): applied only when the sender's email address is in the user's sent contacts, SPF/DKIM both pass, and there are NO Reply-To or anchor-text mismatches. Never applied on display name alone.
  - Confidence bands: `"Likely phishing - N% confidence"` ($\ge 50\%$), `"Suspicious"` ($30\%\text{--}49\%$), and `"Low risk"` ($< 30\%$). Unscored emails remain `"Not analyzed yet"`.
  - Numbered, system-verified factual evidence items (`[1] SPF check result: ...`, `[2] ...`).
- **Real-Inbox Calibration**:
  - Calibrated across 75 real Gmail messages in `aegis.db`: exactly 2 flagged (the user's intentional test phishing attacks), 0 suspicious, and 73 verified Low risk.
- **Phase 1 Evaluation Benchmark (`evaluation/`)**:
  - `evaluation/data/phase1_with_headers.json`: 42 curated, labeled benchmark test cases (21 phishing, 21 legitimate) exercising all edge conditions.
  - `evaluation/phase1_detection.py`: Runnable evaluation script supporting public dataset tuning (80/20 split) with data leakage warnings, text-only layer notices, per-layer/fused metrics, and structured JSON results export.
- **Resumable Worker & "Re-run detection" Action**:
  - Tracks `fraud_version` column in SQLite; worker skips emails already scored at the current version.
  - Provides `POST /api/emails/re-detect` and Settings tab action to trigger immediate re-analysis.
- **Swagger-Style UI Detection Layers View**:
  - Expanded email panel features live breakdown cards for each provider with scores, reasons, and per-layer evidence items.
  - Callout badges reflect confidence bands.
  - Flagged tab dynamically sorts confirmed threats by fraud confidence.

---

## Stage 5 — Claim-Level Explanation Verification (Core Contribution)
- **Unified Grounded Explanation Synthesis (`app/explain/generator.py`)**:
  - Synthesizes priority triage and threat analysis into a single coherent explanation.
  - Generates a permanent system-built **Verdict Line** (priority label + fraud band from DB fields) that is never removed or altered.
  - Encloses system evidence items (`[1]..[N]`) in strict XML delimiters, prompting Gemini to ground all statements strictly in the facts.
  - Deterministic fallback for demo mode without API keys.
- **Atomic Claim Decomposition (`app/explain/generator.py`)**:
  - Gemini decomposes the explanation into at most 6 self-contained factual claims (JSON array).
  - Enforces entity clarity: no ambiguous pronouns ('it', 'they'), no raw `[N]` references; entities (sender, URL/domain, header, attachment) are explicitly named.
  - Cached in SQLite `LLMCache` keyed by `(gmail_id, 'claim_decomposition', prompt_version)`.
- **Local MiniCheck NLI Verifier (`app/verify/minicheck_verifier.py`)**:
  - Uses `lytang/MiniCheck-RoBERTa-Large` directly from the local HuggingFace cache with `local_files_only=True` and `HF_HUB_OFFLINE=1`.
  - Auto-detects device (runs fast on CPU with zero remote downloads).
  - Two labels only: `supported` (confidence $\ge$ threshold) and `unsupported` (hallucinations, ungrounded claims, contradictions).
  - Efficient batch scoring: evaluates each claim against the full evidence document and individual evidence items to identify the best supporting evidence index `[N]`.
  - Graceful degradation: if model weights are missing, the UI displays "Verifier not available" and the unverified explanation is withheld.
- **Filtering & Secure Presentation**:
  - Unsupported claims are filtered out of the user-facing narrative by default.
  - Stored in `verified_claims` and displayed struck-through under a collapsible **Removed Unsupported Claims** toggle.
  - Supported claims are linked to their evidence item pills.
  - Strict Jinja autoescape security: text is escaped before citation tokens `[N]` are wrapped in styled badges. Completely immune to `<script>` injection.
- **Worker & API Integration**:
  - Resumable 3rd pass in `app/priority/worker.py` running on unread non-newsletter emails and flagged emails.
  - On-demand verification endpoint `POST /api/emails/{id}/verify`.
- **Phase 2 Evaluation Benchmark (`evaluation/`)**:
  - `evaluation/data/phase2_trap_cases.json`: 30 benchmark cases (15 dev, 15 test) with ~50% trap cases (sender past behavior traps, bank name traps, auth header traps, urgent wire traps, malware traps, URL destination traps).
  - `evaluation/phase2_verification.py`:
    - **Part 1 (Deterministic Benchmark)**: Tunes threshold on Dev (0.100) and reports held-out Test set:
      - Unsupported Claim Detection Recall: **100.0%**
      - Unsupported Claim Detection Precision: **71.4%**
      - Verifier F1 Score: **83.3%**
      - Overall Accuracy: **85.0%**
      - Ungrounded-claim rate reduction: **37.5% $\rightarrow$ 0.0%** (100% relative reduction, by construction).
    - **Part 2 (End-to-End LLM Generation)**: Prompts Gemini across the 15 test cases, decomposes into atomic claims, verifies each claim, and exports 90 generated claims to `evaluation/data/phase2_generated_claims_to_label.json` for human annotation.

---

## Quickstart

### Option A: Using `uv` (Recommended)

1. **Install dependencies and sync environment**:
   ```bash
   uv sync
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   *(By default `DEMO_MODE=true` is enabled, running out of the box with zero external keys!)*

3. **Run development server**:
   ```bash
   uv run uvicorn app.main:app --reload --reload-dir app
   ```

4. **Open the application**:
   - **Main Dashboard**: [http://127.0.0.1:8000/priority](http://127.0.0.1:8000/priority)
   - **Settings & Mode Gateway**: [http://127.0.0.1:8000/settings](http://127.0.0.1:8000/settings)
   - **Login & Auth Flow**: [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login)
   - **Swagger API Explorer**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### Option B: Plain `pip` Fallback

1. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment and run**:
   ```bash
   cp .env.example .env
   uvicorn app.main:app --reload --reload-dir app
   ```

---

## Running Tests

To run the complete test suite (51 automated tests):

```bash
uv run pytest tests/ -v
```

Tests cover normalizers, demo dataset rules, database models, Gemini caching/retries, API endpoints, UI tab partitioning, security autoescaping, and HTMX panel interactions.
