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
