# AegisRAG — Project Spec (read this first, every session)

## 1. Goal
A local, self-hosted agentic email assistant for Gmail that does three things in one pipeline:
1. **Prioritizes** emails using RAG over past emails.
2. **Detects phishing/fraud** using our own detector plus premade internet services.
3. **Verifies its own explanations**: split each explanation into atomic claims, check every claim against the retrieved evidence with an NLI model, and flag or remove claims that are unsupported or contradicted.

This is a B.Tech major project. Code must be readable and explainable, and must be measurable (see Section 10).

## 2. Hard constraints
- Python 3.11+, FastAPI. **No Docker.**
- Setup must be exactly: create venv -> `pip install -r requirements.txt` -> copy `.env.example` to `.env` -> `uvicorn app.main:app --reload`. Write this in README.md and keep it true.
- SQLite only. FAISS or Chroma (local) for vectors.
- **No Node/npm.** Frontend is Jinja2 templates + HTMX + Tailwind via CDN.
- Every external service is an **optional provider**. If its key is missing, skip it gracefully and show "not configured" in the UI. The app must run with zero keys in **Demo mode** (about 20 built-in sample emails: some phishing, some newsletters, some normal).
- Never hardcode secrets. All keys and file paths come from `.env`.
- Ask before adding any large dependency (over ~500 MB, e.g. torch). If it is needed, explain why first.

## 3. Credentials and secrets
- `credentials.json` and `token.json` in the project root are **temporary placeholders** and will be replaced with real ones. Never copy their contents into code or logs.
- Add to `.gitignore` immediately: `credentials.json`, `token.json`, `.env`, `*.db`, `data/`, `.venv/`.
- Provide `.env.example` with: GEMINI_API_KEY, GEMINI_MODEL, GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH, SAFE_BROWSING_API_KEY, VIRUSTOTAL_API_KEY, NLI_MODEL, HF_PHISHING_MODEL, DEMO_MODE.

## 4. Gmail auth (GCP OAuth2)
- OAuth client type is **Desktop app**. Use `google-auth-oauthlib` `InstalledAppFlow.run_local_server` for the first login; it writes `token.json`.
- Scope: `gmail.readonly` only.
- If `credentials.json` is missing or invalid, or the token is expired or revoked, **do not crash**. Show a Login / Re-login page and offer Demo mode. (While the Google consent screen is in "Testing" mode, tokens expire after about 7 days, so this is expected.)

## 5. LLM (Gemini)
- Use the `google-genai` SDK. Key in GEMINI_API_KEY, model name in GEMINI_MODEL (never hardcode the model name).
- Ask Gemini for structured JSON output wherever the result is parsed (scores, claim lists).
- **Cache every LLM output** in SQLite keyed by Gmail message ID + task type. Never call Gemini again for an email already processed.
- Handle 429/rate-limit errors with retry + backoff. Show "rate limited, retrying" in the UI instead of crashing.
- Process only new emails, in small batches.
- Embeddings for RAG: **local** `sentence-transformers` (small model), not the API.

## 6. Pipeline (in this order)
1. **Ingest**: Gmail API -> normalized email (headers, body text, links, attachment metadata, labels).
2. **Preprocess / features**: URLs, sender domain, display-name mismatch, header anomalies, newsletter signals.
3. **Sender auth**: parse the `Authentication-Results` header for SPF / DKIM / DMARC results (Gmail already computed them). Use `dnspython` only to check whether the sender domain publishes SPF/DMARC records.
4. **RAG retrieval**: fetch similar past emails and context. The SAME retrieved context feeds both the priority path and the phishing path.
5. **Dual-path analysis**: priority classifier + phishing detector (Section 7).
6. **Explanation generation**: one combined natural-language explanation of why the email was ranked and/or flagged.
7. **Claim decomposition + verification** (Section 8).
8. **Risk fusion + save to DB + dashboard.**

### Priority classifier
Hybrid: simple rules (known contacts, deadlines, keywords) + Gemini relevance score (0-100) + similar past emails from RAG. Output: score and label High / Medium / Low, plus a short justification.

## 7. Phishing detection
Each layer is a separate module under `app/phishing/providers/` returning `{name, score 0-1, reason, available}`:
1. **Sender auth** (SPF/DKIM/DMARC failures are strong signals).
2. **URL / domain heuristics** (scikit-learn or rules: lookalike domains, IP URLs, shorteners, mismatched link text vs target).
3. **Premade services** (each optional): Google Safe Browsing API, VirusTotal API, URLhaus / OpenPhish downloadable feeds (cached locally), and a pretrained Hugging Face phishing-email classifier (model id in HF_PHISHING_MODEL).
4. **LLM social-engineering analysis** via Gemini (urgency, authority impersonation, credential requests, unusual payment requests).

**Fusion**: weighted average with weights in one config file. Rules: if any threat-intel provider (Safe Browsing, VirusTotal, URLhaus/OpenPhish) reports a known-bad URL, floor the fraud confidence at 90%. If a provider is unavailable, drop it and re-normalize the weights. Output a **fraud confidence 0-100%** and keep every layer's result so the UI can show each one.

## 8. Claim-level explanation verification (core contribution)
- Use Gemini to split the combined explanation into **atomic claims** (one fact each), as JSON.
- Build an **evidence set** of short text facts from: retrieved context snippets AND the extracted features written as plain sentences (e.g. "SPF check result: fail", "Link text says paypal.com but points to paypa1-login.net", "Sender is not in the user's past contacts").
- Check each claim against the evidence using an NLI model (NLI_MODEL in `.env`; default to a small DeBERTa/MiniLM NLI cross-encoder; `roberta-large-mnli` or MiniCheck must be switchable by config only).
- Label every claim: **entailed / contradicted / unsupported**, with the best-matching evidence snippet and the NLI confidence.
- Remove or visibly flag contradicted and unsupported claims. The user must only see the verified explanation by default, with an option to view removed claims.
- Keep thresholds in config.

## 9. UI (Gmail-like, Swagger-style rows)
**Tabs (left sidebar):** Priority (home), Previous Messages, Feed, Flagged / Fraud, Settings. Top search bar. Clean Gmail-like look.

**Email rows are collapsible, like Swagger UI operations:**
- Colored left border + badges (priority, fraud %, newsletter), subject, sender, time. Click to expand.
- Row colors: red = likely fraud, amber = high priority, green = low priority, grey = newsletter. Same style on every tab.
- Expanded panel has inner tabs: **Summary | Verified Explanation | Detection Layers | Headers | Body**.
- Load panel content lazily with HTMX on first expand.

**Callout badges:** priority (High / Medium / Low) and fraud (e.g. "Likely phishing - 87% confidence"). Colors: red / amber / green.

**Verified Explanation view:** each claim shown with an entailed / contradicted / unsupported marker and its evidence snippet.

**Detection Layers view:** each provider's score and reason, or "not configured".

**Read / unread logic:**
- Unread = Gmail `UNREAD` label AND `opened_at` is NULL in our DB.
- Expanding an email's row sets `opened_at` (we cannot modify Gmail with the read-only scope).
- **Priority (home)** shows only unread mail, sorted by priority score, highest first.
- **Previous Messages** shows opened/read mail, newest first.

**Feed tab:** newsletters only, detected from the `List-Unsubscribe` header, `Precedence: bulk`, and Gmail labels `CATEGORY_PROMOTIONS` / `CATEGORY_UPDATES`. Show them in a clean, readable layout, separate from the Priority tab.

**API docs:** FastAPI's `/docs` (Swagger) must stay clean: tags, descriptions, example responses. It is our API explorer.

**Actions:** the app only labels and recommends (flag / quarantine / prioritize) inside our own dashboard. It must never delete or modify Gmail data.

## 10. Evaluation (needed for the report)
Create `evaluation/` with runnable scripts:
- `phase1_detection.py`: runs the phishing detector on a labeled dataset (80/20 split) and prints accuracy, false-positive rate, per-email latency.
- `phase2_verification.py`: runs a test query set **with and without** the claim verifier, including deliberately unanswerable "trap" cases, and prints the ungrounded-claim rate for both, plus verifier precision and recall.
- Put the sample dataset and trap cases in `evaluation/data/` in simple CSV/JSON files. Results are saved to `evaluation/results/`.

## 11. Code structure and rules
```
app/
  main.py, settings.py
  ingest/      # gmail client, demo emails
  features/    # feature extraction
  auth/        # SPF/DKIM/DMARC parsing + DNS checks
  rag/         # embeddings, vector store, retrieval
  priority/    # priority classifier
  phishing/    # detector + providers/
  explain/     # explanation generator, claim decomposition
  verify/      # NLI verifier
  fusion/      # risk fusion
  db/          # SQLite models
  llm/         # Gemini client wrapper (caching, retry)
  api/         # JSON API routes (tagged for /docs)
  ui/          # Jinja2 templates, HTMX views, static
evaluation/
tests/
```
- Type hints and Pydantic models everywhere. Config only in `settings.py`.
- One `pytest` test file per module (at least basic tests), using demo emails.
- Short docstrings that explain WHY, since the team must explain this code in a viva.
- Keep functions small. No unused code.

## 12. How to work (rules for the agent)
- Build **one stage at a time** (the user will say which). Do not start the next stage.
- Before coding: show a short plan and wait for approval.
- After coding: run the app and the tests, then report what works and what does not, and how to run it. Do not claim something works unless you ran it.
- If a requirement is unclear or conflicts with this file, ask instead of guessing.
- Update README.md at the end of each stage.

## 13. Definition of done (per stage)
1. App starts with the 4 setup commands. 2. Demo mode works with no keys. 3. Tests pass. 4. README updated. 5. No secrets in code or git.

## 14. Addendum (overrides earlier sections where they conflict)
- Tooling: this project uses uv. Manage dependencies with `uv add` and
  keep requirements.txt in sync (`uv export --no-hashes -o requirements.txt`).
  README setup: `uv sync`, copy .env.example to .env,
  `uv run uvicorn app.main:app --reload`, plus a plain pip fallback.
  Delete the default main.py that `uv init` created.
- GET endpoints never change data. Marking an email as opened is
  POST /api/emails/{id}/open (sets opened_at).
- Store ALL email headers in raw_headers, not just key ones.
- LLMCache has a prompt_version column; cache lookup matches
  message_id + task_type + prompt_version.
- NLI_MODEL defaults to a small NLI cross-encoder. HF_PHISHING_MODEL is
  empty in .env.example until we verify a real model in Stage 4.
  Never invent model or package names; if unsure something exists, say so.
- Never render email HTML directly. Show plain text by default; if HTML
  is shown, use a sandboxed iframe with scripts disabled.
- Run the Gmail login flow in a thread so it doesn't block the server.
- Demo emails: realistic Authentication-Results headers (mix of pass and
  fail), include one legit-but-urgent email and one phishing email that
  passes SPF, mark 4-5 as already read, use dates relative to now, use
  fake/reserved domains for phishing.
- Include tests/test_normalizer.py.