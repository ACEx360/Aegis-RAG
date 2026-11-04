# CHAPTER 4: SYSTEM DESIGN
#
# Target: 10 pages (~2,800–3,000 words).
# Contains: architecture, mathematical model, DFDs, ER diagram, UML diagrams.

---

# CHAPTER 4: SYSTEM DESIGN

     This chapter describes the design of AegisRAG. It covers the overall system architecture, the mathematical model underpinning the priority classifier and phishing fusion algorithm, data flow diagrams at three levels of detail, the entity-relationship model of the database, and selected UML diagrams. The design follows directly from the requirements stated in Chapter 3.

## 4.1 SYSTEM ARCHITECTURE

     AegisRAG is a single-process Python application built on FastAPI. It is structured as a set of loosely coupled modules, each responsible for one stage of the pipeline, communicating through a shared SQLite database. Figure 4.1 shows the top-level component architecture.

<!-- FIGURE 4.1 -->
[Figure 4.1: AegisRAG System Architecture]
<!-- source: figures/fig4_1_architecture.mmd -->
Figure 4.1: AegisRAG System Architecture

Legend: The application is divided into eight functional layers: ingest, features, auth, rag, priority, phishing, explain/verify, and ui. A shared SQLite database connects all layers. The FastAPI process hosts both the HTTP server and the background analysis worker thread. External services (Gmail API, Gemini API) are accessed only from the ingest and llm layers respectively.

     The eight functional layers are as follows.

     **app/ingest:** Contains the Gmail API client (`gmail_client.py`) and the email normalizer (`normalizer.py`). The Gmail client authenticates via OAuth2, retrieves raw message objects, and passes them to the normalizer. The normalizer extracts headers, body text (plain and HTML), links, attachment metadata, and Gmail labels, producing a standardized record that is written to the `emails` table. The demo email loader (`demo_emails.py`) fills the same table with twenty built-in synthetic messages when `DEMO_MODE=True`.

     **app/features:** Extracts structured features from a normalized email record — sender domain, display-name mismatch status, presence of a List-Unsubscribe header, urgency keywords, and attachment types — making them available to downstream layers as a structured dictionary.

     **app/auth:** Parses the `Authentication-Results` header to extract SPF, DKIM, and DMARC outcomes. Also checks for From-domain / Return-Path / Reply-To mismatches and display-name spoofing. This module does not make DNS queries; it reads results already computed by Gmail.

     **app/rag:** Computes sentence-transformer embeddings (`embeddings.py`) and performs cosine similarity retrieval (`vector_store.py`) over stored embeddings to find the top-K most similar past emails. The retrieved emails and their metadata form the evidence context used by both the priority classifier and the explanation generator.

     **app/priority:** Implements the hybrid priority classifier. The rule engine (`rules.py`) computes a deterministic score. The Gemini LLM wrapper (`classifier.py`) adds a relevance score when the API is configured. The background worker (`worker.py`) applies the classifier to all unanalyzed emails in batches.

     **app/phishing:** Contains the detector orchestrator (`detector.py`) and four provider modules under `providers/`: `sender_auth.py`, `url_heuristics.py`, `bert_phishing.py`, and `gemini_social.py`. The fusion engine (`fusion.py`) combines provider outputs into a single fraud confidence score.

     **app/explain and app/verify:** The explanation generator (`generator.py`) calls Gemini to produce a unified natural-language explanation and decomposes it into atomic claims. The verifier (`minicheck_verifier.py`) checks each claim against the system-assembled evidence using MiniCheck-RoBERTa-Large and labels each claim as supported or unsupported.

     **app/ui and app/api:** The UI layer (`ui/`) serves Jinja2 templates and HTMX partial responses. The API layer (`api/`) exposes JSON endpoints documented in Swagger UI at `/docs`. The `app/llm/` module provides the Gemini client with SQLite-based caching and exponential backoff retry.

### 4.1.1 Pipeline Execution Flow

     When a new email arrives, it is processed in the following sequence: (1) ingestion and normalization → (2) feature extraction → (3) embedding computation and storage → (4) RAG retrieval of similar past emails → (5) priority classification (rules + optional Gemini) → (6) phishing detection (four layers + fusion) → (7) explanation generation and claim decomposition → (8) NLI claim verification → (9) database update with all scores, evidence, and verified claims. Steps 5–9 are executed by the background worker thread so they do not block the web server. The UI displays partial results as each step completes.

     The background worker is resumable: it maintains `fraud_version` and `verification_version` columns in the `emails` table. On each worker run, it queries for emails where these version strings do not match the currently configured values, processing only the emails that genuinely require (re-)analysis. This design means that if the server is restarted mid-batch, the worker picks up from the last completed email rather than reprocessing everything.

     The application uses a single OS thread for the background worker (Python `threading.Thread`) rather than a process pool or external task queue. This simplification is possible because model inference is CPU-bound and the analysis worker deliberately pauses 500 ms between email batches to yield CPU time to the Uvicorn web server thread. If inference were GPU-bound, a separate process would be needed; in the current CPU-only configuration, cooperative thread sharing is sufficient.

     Figure 4.2 shows the sequence of operations for a single email from ingestion to verified display.

<!-- FIGURE 4.2 -->
[Figure 4.2: Processing Sequence for a Single Email]
<!-- source: figures/fig4_2_sequence.mmd -->
Figure 4.2: Processing Sequence for a Single Email

Legend: Solid arrows show synchronous calls; dashed arrows show database reads/writes. The User interacts with the UI; the UI makes HTMX requests to the FastAPI server; the server reads from the database. The background worker thread performs steps 4–8 asynchronously and writes results to the database between each step.

## 4.2 MATHEMATICAL MODEL

     This section presents the precise formulas used by the priority classifier and the phishing fusion algorithm. All parameters are stored in `app/settings.py` and may be overridden via `.env`.

### 4.2.1 Priority Score

     Let $r$ be the rule score (0–100) and $g$ be the Gemini relevance score (0–100). The final priority score $P$ is:

$$P = w_r \cdot r + w_g \cdot g$$

where $w_r = 0.4$ and $w_g = 0.6$. When the Gemini API is not configured, $P = r$. For bulk and promotional emails (detected by Newsletter signals), $P$ is capped at 40:

$$P_{\text{cap}} = \min(P,\ 40)$$

The priority label is assigned as follows:

$$\text{Label} = \begin{cases} \text{High} & \text{if } P \geq 70 \\ \text{Low} & \text{if } P \leq 30 \\ \text{Medium} & \text{otherwise} \end{cases}$$

### 4.2.2 Phishing Fusion

     Let $N$ be the set of available (non-abstaining) provider layers. Each layer $i \in N$ produces a raw score $s_i \in [0, 1]$ and a configured base weight $w_i^0$. The re-normalized weight is:

$$w_i = \frac{w_i^0}{\sum_{j \in N} w_j^0}$$

The base fused score is the weighted average:

$$F_{\text{base}} = \sum_{i \in N} w_i \cdot s_i$$

**Floor rules.** If any threat-intelligence provider (currently Google Safe Browsing, if configured) reports a known-bad URL, the score is floored at 0.90:

$$F = \max(F_{\text{base}},\ 0.90) \quad \text{(threat-intel floor)}$$

If any available layer $i$ satisfies $s_i \geq \theta_{\text{strong}} = 0.80$ and has a confirmed strong indicator, the score is floored at 0.60:

$$F = \max(F,\ 0.60) \quad \text{(strong-layer floor)}$$

**Cap rule.** If sender authentication is fully clean (SPF, DKIM, and DMARC all pass, no domain mismatches, no Reply-To anomaly) and no strong URL signal is present, the score is capped below the Suspicious threshold:

$$F = \min(F,\ \theta_{\text{susp}} - \epsilon) \quad \text{(clean-sender cap)}$$

where $\theta_{\text{susp}} = 0.30$.

**Trust discount.** If the sender is in the user's sent-contacts and SPF and DKIM both pass:

$$F = F \cdot (1 - \delta_{\text{trust}}) \quad \text{where } \delta_{\text{trust}} = 0.30$$

The final fraud label is:

$$\text{Fraud label} = \begin{cases} \text{Likely phishing} & \text{if } F \geq 0.50 \\ \text{Suspicious} & \text{if } 0.30 \leq F < 0.50 \\ \text{Low risk} & \text{if } F < 0.30 \end{cases}$$

The configured base weights are: $w_{\text{sender\_auth}}^0 = 0.35$, $w_{\text{url\_heuristics}}^0 = 0.35$, $w_{\text{bert}}^0 = 0.15$, $w_{\text{gemini\_social}}^0 = 0.15$.

### 4.2.3 Claim Verification

     Let $E$ be the full evidence document (all numbered evidence items concatenated) and $E_1, E_2, \ldots, E_k$ be the individual evidence items. For a claim $c$, MiniCheck produces a support probability $p(c, e)$ for each evidence fragment $e$. The final confidence is:

$$\text{conf}(c) = \max\bigl(p(c, E),\ \max_{j=1}^{k} p(c, E_j)\bigr)$$

A claim is labeled "supported" if $\text{conf}(c) \geq \theta_v$, where $\theta_v = 0.10$ (default, equal to the evaluated threshold). Claims with $\text{conf}(c) < \theta_v$ are labeled "unsupported" and filtered from the default user-facing narrative.

## 4.3 DATA FLOW DIAGRAMS

### 4.3.1 Level 0 DFD (Context Diagram)

     Figure 4.3 shows the context diagram. AegisRAG receives email data from the Gmail API (external entity) and user interaction from the Browser (external entity), and outputs dashboard views and analysis scores.

<!-- FIGURE 4.3 -->
[Figure 4.3: Level 0 Data Flow Diagram (Context Diagram)]
<!-- source: figures/fig4_3_dfd0.mmd -->
Figure 4.3: Level 0 Data Flow Diagram (Context Diagram)

Legend: Two external entities interact with the AegisRAG system: (1) Gmail API provides raw email messages; (2) Browser provides user requests and receives dashboard responses. The Gemini API is also shown as an optional external entity providing LLM analysis outputs.

### 4.3.2 Level 1 DFD

     Figure 4.4 decomposes the system into its major processes: Ingest, Analyze (priority + phishing), Explain and Verify, and Present.

<!-- FIGURE 4.4 -->
[Figure 4.4: Level 1 Data Flow Diagram]
<!-- source: figures/fig4_4_dfd1.mmd -->
Figure 4.4: Level 1 Data Flow Diagram

Legend: Raw email flows from Gmail into the Ingest process, which writes normalized records to the Emails data store. The Analyze process reads from the Emails store and the RAG Embeddings store and writes scores and evidence. The Explain and Verify process reads scores and evidence and writes verified claims. The Present process reads all stored data and responds to Browser requests.

### 4.3.3 Level 2 DFD — Phishing Detection Sub-Process

     Figure 4.5 expands the Phishing Detection sub-process of the Level 1 Analyze node into its four provider layers and the fusion step.

<!-- FIGURE 4.5 -->
[Figure 4.5: Level 2 Data Flow Diagram — Phishing Detection Sub-Process]
<!-- source: figures/fig4_5_dfd2.mmd -->
Figure 4.5: Level 2 Data Flow Diagram — Phishing Detection Sub-Process

Legend: The normalized email record flows into four parallel provider modules. Each provider outputs a (score, reason, available) triple. The Fusion Engine reads all four outputs, applies re-normalized weighted average and the floor/cap/trust rules, and writes the final fraud_score and per-layer results to the database.

## 4.4 ENTITY RELATIONSHIP DIAGRAMS

     The AegisRAG database contains two ORM-mapped tables. Figure 4.6 shows the entity-relationship diagram.

<!-- FIGURE 4.6 -->
[Figure 4.6: Entity-Relationship Diagram — AegisRAG Database]
<!-- source: figures/fig4_6_er.mmd -->
Figure 4.6: Entity-Relationship Diagram — AegisRAG Database

Legend: The `emails` table stores one row per ingested email with all header, body, score, embedding, evidence, and verification columns as JSON where appropriate. The `llm_cache` table stores one row per unique (gmail_id, task_type, prompt_version) triple, containing the Gemini API response JSON and a timestamp. There is a logical one-to-many relationship: one email can have multiple LLM cache entries (one per task type per prompt version).

     **emails table** (key columns): `id` (PK integer), `gmail_id` (unique string), `subject`, `sender`, `body_text`, `raw_headers` (JSON), `links` (JSON), `embedding` (JSON float array), `priority_score` (float), `priority_label` (string), `priority_evidence` (JSON), `fraud_score` (float), `fraud_label` (string), `fraud_evidence` (JSON), `layer_results` (JSON), `explanation` (text), `claims` (JSON), `verified_claims` (JSON), `is_newsletter` (bool), `is_demo` (bool), `fraud_version` (string), `verification_version` (string), `opened_at` (datetime), `received_at` (datetime).

     **llm_cache table** (key columns): `id` (PK integer), `gmail_id` (string FK to emails.gmail_id), `task_type` (string, e.g. "priority", "phishing_social", "explanation", "decomposition"), `prompt_version` (string), `response_json` (text), `created_at` (datetime). A unique constraint on `(gmail_id, task_type, prompt_version)` ensures at most one cached response per task configuration per email.

     The choice of storing embeddings, evidence items, claims, and layer results as JSON-encoded text columns — rather than normalizing them into separate tables — is a deliberate simplification. For a single-user local application, the join complexity and migration cost of a fully normalized schema outweigh the modest storage overhead of JSON columns. SQLAlchemy property accessors handle serialization and deserialization transparently.

## 4.5 UML DIAGRAMS

### 4.5.1 Use Case Diagram

     Figure 4.7 shows the use case diagram. The primary actor is the User (a human who interacts with the browser dashboard). The secondary actors are the Gmail API and the Gemini API (external systems).

<!-- FIGURE 4.7 -->
[Figure 4.7: Use Case Diagram]
<!-- source: figures/fig4_7_usecase.mmd -->
Figure 4.7: Use Case Diagram

Legend: The User can: view the Priority dashboard (unread emails), open and read an email (which sets opened_at), view the Verified Explanation and Detection Layers for any analyzed email, view Previous Messages, view the Feed (newsletters), view Flagged emails, and configure settings. The system automatically (via background worker) performs: sync emails from Gmail, analyze priority and fraud, generate and verify explanations. The Gmail API actor is involved in the Sync use case; the Gemini API actor is involved in Analyze and Generate Explanation use cases.

### 4.5.2 Class Diagram

     Figure 4.8 shows a simplified class diagram of the key Python modules and their principal relationships.

<!-- FIGURE 4.8 -->
[Figure 4.8: Simplified Class Diagram — Key Modules]
<!-- source: figures/fig4_8_class.mmd -->
Figure 4.8: Simplified Class Diagram — Key Modules

Legend: The `BackgroundWorker` class orchestrates calls to `PriorityClassifier`, `PhishingDetector`, `ExplanationGenerator`, and `MiniCheckVerifier`. `PhishingDetector` holds a list of `Provider` objects (SenderAuthProvider, URLHeuristicsProvider, BertPhishingProvider, GeminiSocialProvider) and delegates to `FusionEngine`. `GeminiClient` is used by `PriorityClassifier`, `GeminiSocialProvider`, `ExplanationGenerator`, and the claim decomposer. `Settings` (singleton) is read by all classes. All classes that persist results write through `SQLAlchemy Session`.

### 4.5.3 State Diagram — Email Lifecycle

     Figure 4.9 shows the state machine of an email record from ingestion to fully analyzed state.

<!-- FIGURE 4.9 -->
[Figure 4.9: State Diagram — Email Lifecycle]
<!-- source: figures/fig4_9_state.mmd -->
Figure 4.9: State Diagram — Email Lifecycle

Legend: An email begins in the "Ingested" state immediately after normalization and storage. The background worker transitions it through "Embedding Computed", "Priority Scored", "Fraud Scored", "Explanation Generated", and finally "Verified" as each pipeline stage completes. If any stage fails (e.g. model not loaded), the email remains in the last successfully completed state and can be retried on the next worker run. Opening an email in the UI is a separate transition to the "Opened" sub-state, which is orthogonal to the analysis state.

### 4.5.4 Deployment Diagram

     Figure 4.10 shows the deployment architecture. All components run on a single local machine; no server-side infrastructure is required.

<!-- FIGURE 4.10 -->
[Figure 4.10: Deployment Diagram]
<!-- source: figures/fig4_10_deployment.mmd -->
Figure 4.10: Deployment Diagram

Legend: All AegisRAG components run on a single local machine: the FastAPI/Uvicorn server, background worker thread, SQLite database, and locally cached Hugging Face models. The local machine communicates outbound over HTTPS to two external cloud services: the Gmail API (for email retrieval) and the Gemini API (for LLM calls). The user interacts with the system via a local browser over HTTP loopback (127.0.0.1:8000). No email data is sent to any external service other than the Gemini API.

     The deployment architecture reflects a deliberate design choice: by running all inference locally, the system avoids sending email content to third-party cloud services for processing. The only outbound data flows are (a) OAuth2 token exchange with Google's authorization server (no email content), (b) email retrieval API calls to Gmail (read-only, authorized by the user's own OAuth token), and (c) email body text sent to the Gemini API for LLM-based priority scoring and social-engineering analysis (optional, requires a user-supplied API key). Users who do not configure a Gemini API key incur zero outbound data flows for email content.

     The Hugging Face models used for embedding, phishing classification, and NLI verification are downloaded once from Hugging Face Hub during initial setup and then loaded from local disk with `local_files_only=True` and `HF_HUB_OFFLINE=1`, ensuring that subsequent runs do not require internet access for model inference. The SQLite database file is created automatically in the project root on first run and is excluded from version control via `.gitignore`.

     Table 4.1 summarizes the design decisions made in the system architecture and their rationale.

<!-- TABLE 4.1 -->
[Table 4.1: Key Design Decisions and Rationale]

| Decision | Alternative Considered | Rationale |
|---|---|---|
| SQLite as sole database | PostgreSQL | Single-user local use; no network database required |
| NumPy cosine similarity | FAISS, Chroma | Sufficient for hundreds of emails; removes large dependency |
| Sentence-transformers (local) | Gemini Embedding API | Privacy: email content not sent externally for embedding |
| FastAPI + Jinja2 + HTMX | React SPA | No Node.js build step; simpler to explain and maintain |
| Fixed fusion weights in settings.py | Trained fusion model | Dataset too small to train reliably |
| Two NLI labels (supported/unsupported) | Three labels (entailed/neutral/contradicted) | MiniCheck outputs one "grounded" probability |
| Background worker thread | Celery / Redis task queue | No external process dependencies; simpler deployment |
| WAL journal mode for SQLite | Default SQLite locking | Allows concurrent reads from UI thread during background write |

