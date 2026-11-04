# CHAPTER 6: PROJECT IMPLEMENTATION
#
# Target: 9 pages (~2,520–2,700 words).
# §6.1 module overview, §6.2 tools and technologies, §6.3 algorithm details.

---

# CHAPTER 6: PROJECT IMPLEMENTATION

     This chapter describes how AegisRAG was implemented. Section 6.1 provides an overview of the application modules. Section 6.2 lists the tools, libraries, and technologies used with their versions and roles. Section 6.3 describes the key algorithms in detail, with one subsection per algorithm.

## 6.1 OVERVIEW OF PROJECT MODULES

     Figure 6.1 shows the module dependency graph of the AegisRAG application.

<!-- FIGURE 6.1 -->
[Figure 6.1: Module Dependency Graph]
<!-- source: figures/fig6_1_modules.mmd -->
Figure 6.1: Module Dependency Graph

Legend: Arrows indicate import dependencies. `app/main.py` imports the API and UI routers and starts the background worker on startup. The background worker imports the priority classifier, phishing detector, explanation generator, and NLI verifier. All modules that access the database import from `app/db/`. All modules that call Gemini import from `app/llm/`. `app/settings.py` is imported by every module that reads configuration. The diagram omits test files and the evaluation scripts.

     The application is organized as follows.

     **app/main.py** is the FastAPI application entry point. It creates the database tables on startup, loads the demo emails if `DEMO_MODE=True`, starts the background worker thread, and mounts the API and UI routers. It also starts the Gmail OAuth flow in a separate thread so the server is non-blocking during authentication.

     **app/settings.py** is the single source of configuration truth. All constants — API keys, model names, file paths, thresholds, weights, and version strings — are declared here as `pydantic_settings.BaseSettings` fields, read from `.env`. No values are hardcoded anywhere else in the application.

     **app/db/models.py** defines the two SQLAlchemy ORM models: `Email` and `LLMCache`. JSON columns are stored as `TEXT` with serialization/deserialization handled by the ORM models' property accessors.

     **app/ingest/** contains the Gmail API client and normalizer. The Gmail client handles OAuth2 flow using `InstalledAppFlow.run_local_server`, token persistence in `token.json`, and paginated message listing with a date filter. The normalizer converts raw Gmail API message objects into `Email` ORM instances, extracting headers (all of them, stored as a JSON array), body text (preferring `text/plain`, falling back to HTML-stripped text), and links from both plain-text and HTML body parts.

     **app/rag/** implements the embedding and retrieval layer. `embeddings.py` loads the `sentence-transformers/all-MiniLM-L6-v2` model on first use and computes 384-dimensional embeddings from the email's subject, sender, and first 500 characters of body text. `vector_store.py` fetches all stored embeddings as NumPy arrays and computes cosine similarity between the query embedding and each stored embedding in a single vectorized operation, returning the top-K most similar emails.

     **app/priority/** implements the hybrid priority classifier. `rules.py` evaluates eleven signal categories — known contacts, Gmail labels, List-Unsubscribe, urgency keywords, collaboration keywords, attachment presence, length, time of day, reply-chain depth, and newsletter signals — producing a rule score between 0 and 100. `classifier.py` calls Gemini with a structured prompt that includes the numbered evidence items from the RAG retrieval and the email body (truncated to 2,000 characters). `worker.py` is a resumable background thread that processes all emails with a null `priority_score` or an outdated `fraud_version`/`verification_version` in batches of three.

     **app/phishing/** contains the detector orchestrator and four provider modules. Each provider module implements a `run(email)` function that returns a dictionary with keys `name`, `score`, `reason`, `available`, and `details`. The fusion engine in `fusion.py` collects the four provider outputs, applies the re-normalized weighted average, and then applies the floor, cap, and trust rules in sequence. The final result is written back to the `Email` record as `fraud_score`, `fraud_label`, and `layer_results`.

     **app/explain/** contains the explanation generator, which calls Gemini twice: once to generate the unified natural-language explanation (conditioned on the numbered evidence), and once to decompose the explanation into a JSON array of atomic claims. Both calls use separate `task_type` keys in the LLM cache. **app/verify/** contains the MiniCheck verifier, which loads `lytang/MiniCheck-RoBERTa-Large` from local Hugging Face cache on first use and batches all (claim, evidence) pairs for an email into a single model forward pass.

     **app/llm/** contains the Gemini client wrapper. It maintains a list of configured API keys and rotates through them on each call. On HTTP 429 (rate limit) responses, it waits with exponential backoff (starting at 10 seconds, doubling up to 120 seconds) and logs the wait. All Gemini API responses are cached in the `llm_cache` table after a successful call; on subsequent calls for the same (gmail_id, task_type, prompt_version), the cached response is returned immediately without an API call.

     **app/api/** exposes JSON endpoints under the `/api/` prefix, documented with FastAPI tags and `response_model` declarations. All data-mutating operations are POST requests; GET requests never modify data. **app/ui/** serves Jinja2 HTML templates and handles HTMX partial-page update requests. Panel content is loaded lazily on first expansion; the first `POST /ui/emails/{id}/panel` call also sets `opened_at`.

     The application's test infrastructure is in the `tests/` directory. Each test file covers one application module. Tests run against a separate in-memory SQLite database created by a `pytest` fixture; the `TESTING=1` environment variable suppresses lifespan side effects (model loading, background worker startup) so that tests are fast and isolated. The 113 fast tests cover the normalizer, rule engine, URL heuristics, sender authentication, BERT provider, Gemini social provider, fusion engine, priority classifier, explanation generator, verifier (with mock model), API endpoints, and UI endpoints. One slow test in `tests/test_verify_real.py` requires the real MiniCheck model to be cached locally and is excluded from the default `not slow` marker run. The `ruff` linter enforces PEP 8 compliance, unused import detection, and consistent style across all application and test code.

## 6.2 TOOLS AND TECHNOLOGIES USED

     Table 6.1 lists the major tools and libraries used in AegisRAG. The technology selection was driven by the project constraints: Python 3.11+, no Docker, no Node/npm build steps for the application, and SQLite as the sole database. All dependencies are pinned in `uv.lock` and installed reproducibly via `uv sync`. PyTorch is installed from the PyTorch CPU-only index to keep the download size manageable and to ensure the application runs on any x86-64 machine without a GPU.

     Table 6.1 lists the major tools and libraries used in AegisRAG.

<!-- TABLE 6.1 -->
[Table 6.1: Tools and Technologies]

| Technology | Version Used | Role |
|---|---|---|
| Python | 3.13.2 | Application language |
| uv | Latest | Dependency management, lock file, virtual environment |
| FastAPI | ≥ 0.162.0 | Web framework and API server |
| Uvicorn | — | ASGI server |
| Jinja2 | ≥ 3.1.6 | Server-side HTML templates |
| HTMX | CDN | Dynamic partial-page updates without a JavaScript build step |
| Tailwind CSS | CDN | Utility-first CSS framework |
| SQLAlchemy | ≥ 2.1.6 | ORM for SQLite database access |
| SQLite | Built-in | Local database; WAL mode for concurrent access |
| google-genai | ≥ 2.33.0 | Gemini API SDK |
| google-api-python-client | ≥ 2.201.0 | Gmail API client |
| google-auth-oauthlib | — | OAuth2 Desktop application flow |
| sentence-transformers | ≥ 6.2.0 | Email embedding (all-MiniLM-L6-v2) |
| transformers (Hugging Face) | — | Loading BERT phishing model and MiniCheck |
| PyTorch (CPU) | ≥ 2.15.0 | Inference backend for all transformer models |
| numpy | ≥ 2.5.4 | Cosine similarity computation over embedding arrays |
| pydantic-settings | ≥ 2.16.1 | Settings management from .env |
| pytest | 9.2.0 | Test runner |
| ruff | — | Linter (PEP 8 compliance, unused imports, etc.) |
| ealvaradob/bert-finetuned-phishing | — | Pre-trained BERT phishing classifier (Layer 3) |
| lytang/MiniCheck-RoBERTa-Large | — | NLI fact-checking model for claim verification |
| sentence-transformers/all-MiniLM-L6-v2 | — | Local embedding model (384 dimensions) |

## 6.3 ALGORITHM DETAILS

### 6.3.1 Email Normalization Algorithm

     The normalizer processes a raw Gmail API message object (a JSON dictionary with `payload` tree structure) to extract all required fields. The algorithm is as follows:

     1. Extract all headers from `payload.headers` as a flat list of `{name, value}` dictionaries and store them as `raw_headers` (JSON). Duplicate header names are preserved.
     2. Identify the body content by traversing the `payload.parts` MIME tree recursively. If a `text/plain` part is found, use it as `body_text`. If only `text/html` is found, strip all HTML tags using a regex-based cleaner to obtain plain text. If both are found, prefer `text/plain`.
     3. Extract all links (`<a href="...">text</a>`) from the HTML part (if any), storing each as a dictionary with keys `text` and `href`. This forms the link list for URL heuristics analysis.
     4. Parse the `Date` header as a UTC datetime. Parse `From`, `To`, `Cc`, and `Subject` headers. Detect the `List-Unsubscribe` header to set the `is_newsletter` flag.
     5. Read Gmail labels from the `labelIds` field. Map `UNREAD` to read-state = False. Map `CATEGORY_PROMOTIONS` and `CATEGORY_UPDATES` to newsletter signals.

### 6.3.2 RAG Retrieval and Evidence Assembly

     The RAG retrieval algorithm runs as follows for each email being analyzed:

     1. Compute the query embedding $q$ for the email using the `sentence-transformers/all-MiniLM-L6-v2` model (384-dimensional float32 vector). The query string is `"{subject} {sender} {body_text[:500]}"`.
     2. Fetch all stored embeddings from the database. If no past emails have embeddings, return an empty context.
     3. Compute pairwise cosine similarity: $\text{sim}(q, e_j) = (q \cdot e_j) / (||q|| \cdot ||e_j||)$ for each stored embedding $e_j$, using NumPy vectorized operations. Exclude the email being analyzed itself.
     4. Select the top-K (default: K = 2) emails by cosine similarity. Return their subjects, senders, priority labels, and first 200 characters of body text as the RAG context.
     5. Assemble the numbered evidence set. Evidence items are numbered sequentially and drawn from: (a) the retrieved similar emails (as context snippets), (b) the sender authentication results (parsed SPF/DKIM/DMARC outcomes written as plain sentences), (c) the URL heuristic findings (each flagged signal type written as a plain sentence), and (d) the rule engine signals (e.g. "Sender is not in the user's contact list"). The complete evidence set is stored in `priority_evidence` (for priority) and `fraud_evidence` (for phishing) as JSON arrays.

### 6.3.3 Hybrid Priority Classification Algorithm

     1. The rule engine evaluates eleven categories in sequence and accumulates a score:
        - Known contact (sender in past sent-mail): +30 points.
        - Gmail IMPORTANT label: +20 points.
        - Urgency keywords in subject or body (e.g. "urgent", "deadline", "action required"): up to +15 points.
        - Collaboration keywords (e.g. "meeting", "review", "please confirm"): up to +10 points.
        - Gmail CATEGORY_PROMOTIONS or CATEGORY_SOCIAL label: -30 points.
        - List-Unsubscribe header present: -20 points.
        - Additional signals add or subtract points within defined ranges. The total is clipped to [0, 100].
     2. If `GEMINI_API_KEY` is configured, Gemini is called with a prompt that includes the numbered evidence items and the email body. Gemini returns a JSON object with `relevance_score` (0–100) and `justification`. The score is read from the JSON; on parse error, the rule score alone is used.
     3. The final priority score $P = 0.4 \times r + 0.6 \times g$ (or $P = r$ if Gemini is unavailable).
     4. The priority label (High / Medium / Low) and the justification string are written to the `Email` record. The numbered evidence items are stored in `priority_evidence`.

### 6.3.4 Phishing Detection and Fusion Algorithm

     Figure 6.2 shows the phishing fusion algorithm as a flowchart.

<!-- FIGURE 6.2 -->
[Figure 6.2: Phishing Detection and Fusion Algorithm]
<!-- source: figures/fig6_2_fusion.mmd -->
Figure 6.2: Phishing Detection and Fusion Algorithm

Legend: The four provider layers (Sender Auth, URL Heuristics, BERT, Gemini Social) run in sequence. Each either produces a score or abstains (available=False). After all four have run, the Fusion Engine re-normalizes the weights over available layers, computes the weighted average, then applies three adjustment rules in order: strong-layer floor, threat-intel floor (if applicable), and clean-sender cap and trust discount. The final fraud_score and fraud_label are written to the database.

     **Layer 1 — Sender Authentication.** The `Authentication-Results` header from mx.google.com is parsed using a regex that extracts `spf=`, `dkim=`, `dmarc=` outcomes. The sender score is computed from: SPF fail (+0.4), DKIM fail (+0.3), DMARC fail (+0.2), From/Return-Path domain mismatch (+0.35), display-name spoofing (+0.25), and credential solicitation from an unauthenticated sender (+0.15). Scores are clamped to [0, 1].

     **Layer 2 — URL Heuristics.** Each link in the email is analyzed for: IP-address host, lookalike domain (edit-distance check against a list of high-value domain names), punycode IDN, deceptive subdomain (e.g. `paypal.com.evil.net`), anchor-text vs. href mismatch (different registered domains), URL shortener (list of known shortener services), open-redirect parameter, and dangerous file extension in the URL path. Each detected signal type contributes a weighted increment to the layer score, capped at 1.0. If no links are present, the layer abstains.

     **Layer 3 — BERT Semantic Classifier.** The email body is tokenized with the `ealvaradob/bert-finetuned-phishing` tokenizer (max 512 tokens). The model's softmax output for the "phishing" class is used directly as the layer score. If the model is not cached locally (`local_files_only=True` raises an exception), the layer abstains gracefully.

     **Layer 4 — Gemini Social Engineering Analysis.** This layer is triggered only if `GEMINI_API_KEY` is configured and the preliminary fused score from the other available layers meets or exceeds 0.25. Gemini is prompted to assess four vectors (urgency/threats, authority impersonation, credential harvesting, financial coercion) and return a JSON object with a confidence score for each. The maximum of the four vector scores is used as the layer score.

### 6.3.5 Explanation Generation and Claim Decomposition Algorithm

     1. The explanation generator assembles a combined evidence document from `priority_evidence` and `fraud_evidence`, numbering all items sequentially. It constructs a Gemini prompt that encloses the email body in XML delimiters and instructs Gemini to write a natural-language explanation of why the email was ranked and/or flagged, citing evidence items by number. The explanation prompt version is tracked (`explanation_prompt_version = "v2"`) for cache invalidation.
     2. The claim decomposer sends the explanation to Gemini with a separate prompt instructing it to decompose the explanation into at most six atomic, self-contained claims in JSON format (a JSON array of strings). Each claim must name the specific entity (sender, domain, header, attachment) it refers to and must not use pronouns or raw citation markers.
     3. If Gemini is unavailable, the explanation is a deterministic concatenation of the `priority_reason` and `fraud_reason` strings, and no claim decomposition is performed (the explanation is presented as a single unsplit block).

### 6.3.6 NLI Claim Verification Algorithm

     Figure 6.3 shows the claim verification pipeline.

<!-- FIGURE 6.3 -->
[Figure 6.3: Claim Verification Pipeline]
<!-- source: figures/fig6_3_verify.mmd -->
Figure 6.3: Claim Verification Pipeline

Legend: Each atomic claim is paired with the full evidence document and with each individual evidence item. All pairs for a single email are batched into one forward pass through MiniCheck-RoBERTa-Large. The maximum support probability across the full-document and per-item pairs is taken as the claim confidence. Claims with confidence ≥ 0.10 (the evaluated threshold) are labeled "supported"; the rest are "unsupported". Supported claims are stored with their best-matching evidence citation. Unsupported claims are stored separately for optional display.

     The detailed steps are:

     1. Assemble the evidence document $E$ by joining all numbered evidence items as a single string.
     2. For each claim $c_j$, create input pairs: $(c_j, E)$ and $(c_j, E_i)$ for each individual evidence item $E_i$.
     3. Tokenize all pairs using `AutoTokenizer` for `lytang/MiniCheck-RoBERTa-Large` and stack them into a single batch tensor.
     4. Run the batch through `AutoModelForSequenceClassification` in inference mode (`torch.no_grad()`). The model outputs two logits per pair; apply softmax to obtain the "supported" class probability.
     5. For each claim, take $\text{conf}(c_j) = \max(p(c_j, E), \max_i p(c_j, E_i))$.
     6. Label each claim as "supported" if $\text{conf}(c_j) \geq 0.10$, else "unsupported".
     7. For supported claims, record the index of the evidence item $E_i$ with the highest support probability as the citation.
     8. Write the full results (per-claim label, confidence, and citation) as JSON to the `verified_claims` column of the `Email` record. Update `verification_version` to "v3".

