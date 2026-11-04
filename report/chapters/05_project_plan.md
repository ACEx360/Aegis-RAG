# CHAPTER 5: PROJECT PLAN
#
# Target: 5 pages (~1,400–1,500 words).
# Uses real git log dates for the implementation phase.
# Earlier phases have [TO CONFIRM BY TEAM] dates.
# Team roles: [TO CONFIRM BY TEAM]. Module owner column left blank.

---

# CHAPTER 5: PROJECT PLAN

     This chapter describes how the AegisRAG project was planned and managed. It covers cost and effort estimates, risk management, the project schedule, and team organization.

## 5.1 PROJECT ESTIMATE

### 5.1.1 Size Estimation

     AegisRAG is a research prototype comprising approximately 4,500 lines of Python application code, 1,200 lines of Jinja2 HTML templates, 1,800 lines of test code, and 300 lines of evaluation scripts — approximately 7,800 lines in total, excluding configuration files and documentation. The system is divided into eleven functional modules (ingest, features, auth, rag, priority, phishing/providers, explain, verify, fusion, api, ui), each independently testable. The test suite contains 113 fast unit and integration tests across 17 test files plus 1 slow integration test requiring a real NLI model.

     Table 5.1 summarizes the estimated effort (in person-hours) for each development stage, based on actual time recorded by the team during implementation. These are post-hoc estimates and are approximate.

<!-- TABLE 5.1 -->
[Table 5.1: Effort Estimates by Development Stage]

| Stage | Description | Estimated Person-Hours |
|---|---|---|
| Stage 1 | Core infrastructure, Gmail ingest, demo mode, DB schema | [TO CONFIRM BY TEAM] |
| Stage 2 | UI shell (Jinja2, HTMX, tabs, collapsible rows) | [TO CONFIRM BY TEAM] |
| Stage 3 | RAG embeddings, NumPy vector store, priority classifier | [TO CONFIRM BY TEAM] |
| Stage 4 | Phishing detection (4 providers + fusion) | [TO CONFIRM BY TEAM] |
| Stage 5 | Explanation generation, NLI verification, evaluation | [TO CONFIRM BY TEAM] |
| — | Testing, debugging, documentation, report writing | [TO CONFIRM BY TEAM] |
| **Total** | | **[TO CONFIRM BY TEAM]** |

### 5.1.2 Cost Estimation

     AegisRAG uses exclusively open-source or free-tier tools. The primary cost components are:

     - **Compute:** Development performed on personal laptops (CPU-only inference). No cloud compute was used.
     - **Gemini API:** Free-tier usage during development (rate-limited). No monetary cost was incurred.
     - **Hugging Face models:** All models downloaded free from Hugging Face Hub. Total model storage: approximately 2.0 GB (sentence-transformers/all-MiniLM-L6-v2: 90 MB, ealvaradob/bert-finetuned-phishing: 420 MB, lytang/MiniCheck-RoBERTa-Large: 1.5 GB).
     - **Gmail API:** Accessed within the free-tier quotas for personal account usage.
     - **Total monetary cost:** Zero (all components used within free tiers or open licenses).

## 5.2 RISK MANAGEMENT

### 5.2.1 Risk Identification

     Table 5.2 lists the risks identified during project planning, each with an initial likelihood and impact rating.

<!-- TABLE 5.2 -->
[Table 5.2: Identified Project Risks]

| ID | Risk | Likelihood | Impact |
|---|---|---|---|
| R1 | Gmail OAuth token expiry (~7 days in Testing mode) disrupting development | High | Medium |
| R2 | Gemini API rate limiting delaying batch analysis | Medium | Medium |
| R3 | MiniCheck-RoBERTa-Large too slow for interactive use on CPU | Medium | High |
| R4 | Labeled evaluation dataset too small for statistically reliable results | High | Medium |
| R5 | BERT phishing model performing poorly on real inbox emails | Medium | High |
| R6 | Team member availability reduced by other coursework deadlines | Medium | Medium |
| R7 | Dependency version conflicts between PyTorch, transformers, and sentence-transformers | Low | High |

### 5.2.2 Risk Analysis

     Risk R4 (dataset size) and Risk R5 (BERT generalization) were assessed as the highest combined concern because they affect the validity of the evaluation results directly. R3 (MiniCheck latency) was assessed as acceptable because verification is performed asynchronously in the background worker and does not block the UI. R7 (dependency conflicts) was assessed as low likelihood because `uv` locks exact dependency versions in `uv.lock`.

### 5.2.3 Risk Mitigation

     - **R1 (OAuth expiry):** Implemented a graceful re-login flow. The application shows a Login page and offers Demo Mode when the token is expired or missing, so development and demonstration can continue without interruption.
     - **R2 (Gemini rate limits):** Implemented exponential backoff retry with configurable delay. Added support for round-robin rotation across up to six API keys. Added SQLite caching of all Gemini outputs keyed by (gmail_id, task_type, prompt_version), so repeated analysis runs do not incur additional API calls.
     - **R3 (MiniCheck latency):** Verification is batched (all claims for one email in a single forward pass). On CPU, the average latency per email is acceptable for background processing. The background worker pauses 500 ms between email batches to avoid saturating the CPU while the UI server is also running.
     - **R4 (dataset size):** Results are reported with explicit caveats on set size and construction method. Set B results are reported with a data-leakage caveat. Phase 2 Part 2 labels are reported with the provenance (AI-draft labels reviewed by the authors).
     - **R5 (BERT generalization):** The BERT model is used as one of four independent layers; the fusion algorithm down-weights it relative to sender authentication and URL heuristics if no phishing signal is found. The Phase 1 Set C evaluation explicitly tests generalization on real inbox emails.
     - **R6 (availability):** Staged development with independent testable increments ensured that a delay in one stage did not block another team member's work.
     - **R7 (conflicts):** All dependencies pinned via `uv.lock`. Platform-specific PyTorch index used for CPU builds.

## 5.3 PROJECT SCHEDULE

### 5.3.1 Overall Timeline

     The project was executed over one semester. Table 5.3 shows the planned and actual schedule for each phase. Implementation dates are derived from git log timestamps; earlier phase dates are subject to team confirmation.

<!-- TABLE 5.3 -->
[Table 5.3: Project Schedule]

| Phase | Description | Start Date | End Date |
|---|---|---|---|
| Phase 1 | Synopsis preparation, literature survey, requirements | [TO CONFIRM BY TEAM] | [TO CONFIRM BY TEAM] |
| Phase 2 | System design, architecture decisions | [TO CONFIRM BY TEAM] | [TO CONFIRM BY TEAM] |
| Phase 3 | Implementation — Stage 1 & 2 (Infrastructure, UI shell) | 28 Oct 2026 | 28 Oct 2026 |
| Phase 4 | Implementation — Stage 3 (Priority & RAG) | 29 Oct 2026 | 29 Oct 2026 |
| Phase 5 | Implementation — Stage 4 (Phishing detection) | 29 Oct 2026 | 31 Oct 2026 |
| Phase 6 | Implementation — Stage 5 (Explanation & Verification) | 01 Nov 2026 | 01 Nov 2026 |
| Phase 7 | Evaluation, testing, and debugging | 01 Nov 2026 | 01 Nov 2026 |
| Phase 8 | Report writing | 02 Nov 2026 | [TO CONFIRM BY TEAM] |

### 5.3.2 Milestones

     Table 5.4 lists the key project milestones and their dates.

<!-- TABLE 5.4 -->
[Table 5.4: Project Milestones]

| Milestone | Description | Date |
|---|---|---|
| M1 | Synopsis submitted | [TO CONFIRM BY TEAM] |
| M2 | Stage 1 & 2 complete — app starts with demo mode | 28 Oct 2026 |
| M3 | Stage 3 complete — priority and RAG working | 29 Oct 2026 |
| M4 | Stage 4 complete — phishing detection and fusion working | 31 Oct 2026 |
| M5 | Stage 5 complete — verified explanations working | 01 Nov 2026 |
| M6 | All 113 fast tests passing, ruff clean | 01 Nov 2026 |
| M7 | Phase 1 and Phase 2 evaluation complete | 01 Nov 2026 |
| M8 | Report submitted | [TO CONFIRM BY TEAM] |

### 5.3.3 Work Breakdown Structure

     Figure 5.1 shows the project schedule as a timeline, derived from the git log commit dates for the implementation phases and planned dates for the earlier phases.

<!-- FIGURE 5.1 -->
[Figure 5.1: Project Timeline (Implementation Phases from Git Log)]
<!-- source: figures/fig5_1_timeline.mmd -->
Figure 5.1: Project Timeline (Implementation Phases from Git Log)

Legend: Each horizontal bar represents one development phase. Implementation phases (Stages 1–5) use exact dates from the git log. Earlier phases (synopsis, requirements, design) use [TO CONFIRM BY TEAM] placeholders. The critical path runs through Stages 3, 4, and 5 in sequence, since each stage depends on the previous stage's output.

## 5.4 TEAM ORGANIZATION

### 5.4.1 Team Structure

     The project was carried out by four B.Tech students as an equal-effort team. Table 5.5 lists the team members. The Owner column is to be confirmed by the team.

<!-- TABLE 5.5 -->
[Table 5.5: Team Members]

| Name | PRN | Roll No. | Primary Module(s) |
|---|---|---|---|
| Tanishq Raina | 22310084 | 17 | [TO CONFIRM BY TEAM] |
| Alpesh Thool | 22310727 | 05 | [TO CONFIRM BY TEAM] |
| Tayyab Mohammed | 22311292 | 32 | [TO CONFIRM BY TEAM] |
| Chinmay Kale | 22310757 | 21 | [TO CONFIRM BY TEAM] |

### 5.4.2 Module Ownership

     Table 5.6 maps each application module to its primary owner. The Owner column is to be filled by the team before submission.

<!-- TABLE 5.6 -->
[Table 5.6: Module Ownership]

| Module | Directory | Description | Owner |
|---|---|---|---|
| Ingest & Normalizer | app/ingest/ | Gmail API client, demo emails, normalizer | [TO CONFIRM] |
| Features | app/features/ | Feature extraction | [TO CONFIRM] |
| Auth / SPF-DKIM-DMARC | app/auth/ | Authentication-Results parsing | [TO CONFIRM] |
| RAG / Embeddings | app/rag/ | Embedding, vector store, retrieval | [TO CONFIRM] |
| Priority Classifier | app/priority/ | Rule engine, LLM classifier, worker | [TO CONFIRM] |
| Phishing — Sender Auth | app/phishing/providers/ | Layer 1 | [TO CONFIRM] |
| Phishing — URL Heuristics | app/phishing/providers/ | Layer 2 | [TO CONFIRM] |
| Phishing — BERT | app/phishing/providers/ | Layer 3 | [TO CONFIRM] |
| Phishing — Gemini Social | app/phishing/providers/ | Layer 4 | [TO CONFIRM] |
| Fusion Engine | app/phishing/ | Weighted fusion, floor/cap/trust rules | [TO CONFIRM] |
| Explanation Generator | app/explain/ | LLM explanation + claim decomposition | [TO CONFIRM] |
| NLI Verifier | app/verify/ | MiniCheck-RoBERTa-Large integration | [TO CONFIRM] |
| Gemini Client | app/llm/ | Caching, retry, key rotation | [TO CONFIRM] |
| UI / Templates | app/ui/ | Jinja2 templates, HTMX views | [TO CONFIRM] |
| API Routes | app/api/ | FastAPI JSON endpoints | [TO CONFIRM] |
| Evaluation Scripts | evaluation/ | Phase 1 and Phase 2 scripts | [TO CONFIRM] |
| Tests | tests/ | pytest test files (17 files, 113 tests) | [TO CONFIRM] |

