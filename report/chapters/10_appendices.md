# APPENDICES

---

## APPENDIX A: FEASIBILITY ASSESSMENT

### A.1 Technical Feasibility

AegisRAG relies entirely on mature, widely-deployed software components. Python 3.11+ is the de facto standard for machine-learning and web-development projects. FastAPI is a production-grade asynchronous web framework with comprehensive documentation and an active maintenance community. The `sentence-transformers` library provides pre-trained embedding models that run efficiently on CPU hardware. The MiniCheck verifier uses a RoBERTa-Large model loaded through the standard Hugging Face `transformers` library; models of this size (approximately 1.4 GB) are routinely deployed on consumer-grade machines with 8 GB or more of RAM.

The Gmail API, OAuth2 authentication, and Google Gemini API are production services with published Python SDKs. All other dependencies — SQLite, HTMX, Jinja2, Tailwind CSS (CDN), Ruff, pytest — are standard tools with no unusual system requirements.

No component of AegisRAG requires specialised hardware. The pipeline runs end-to-end on a standard developer laptop without a GPU; the only significant resource requirement is the approximately 1.4 GB of RAM needed to load the MiniCheck model.

The technical feasibility assessment is: **feasible**. All required components exist, are freely available, and have been demonstrated to work together in the implemented system.

### A.2 Operational Feasibility

AegisRAG is designed for single-user local deployment. Setup requires four commands: `uv sync`, copy `.env.example` to `.env`, optionally add API keys, and `uv run uvicorn app.main:app --reload --reload-dir app`. No server infrastructure, no cloud accounts, and no database administration are required. Demo mode provides a fully functional experience with zero configuration.

The web interface is accessible at `http://localhost:8000` and is designed to be operated by a user with no technical background once the application is started. The operational feasibility assessment is: **feasible**.

### A.3 Economic Feasibility

All software dependencies are open-source and available without cost. The Gemini API has a free tier that is sufficient for individual use at typical email volumes. Google Safe Browsing and VirusTotal APIs have free tiers available with registration. The HuggingFace models used (all-MiniLM-L6-v2, MiniCheck RoBERTa-Large, ealvaradob/bert-finetuned-phishing) are publicly available without licensing fees.

The economic feasibility assessment is: **feasible** at zero marginal cost for personal use.

### A.4 Satisfiability and Complexity Analysis

Each computational component of AegisRAG is analysed below.

**Email normalisation and feature extraction** involve string parsing, regular expression matching, and header field lookup. These operations are linear in the length of the email and constitute polynomial-time algorithms.

**Embedding generation and cosine-similarity retrieval** involve a fixed forward pass through a pre-trained transformer (all-MiniLM-L6-v2) followed by a dot-product computation over the stored embedding matrix. Both operations are polynomial in the number of embeddings and the embedding dimension; retrieval is O(*n* · *d*) for *n* stored embeddings of dimension *d*.

**Phishing-detection layers** — sender-authentication parsing, URL heuristics, BERT classifier inference, and Gemini API calls — each involve a fixed amount of computation per email. The BERT and MiniCheck forward passes are polynomial in the input length and model size.

**Claim decomposition and NLI verification** involve one Gemini API call (claim decomposition) and one MiniCheck forward pass per claim (NLI). Both are polynomial-time operations on fixed-size inputs.

**Fusion** is a weighted average: a constant-time operation regardless of the number of providers.

**Conclusion:** All core computations in AegisRAG are polynomial-time algorithms. No component requires solving an NP-complete or NP-hard problem. The system does not implement any exact combinatorial search, constraint satisfaction, or integer programming. The overall pipeline complexity per email is dominated by the transformer inference steps, which are polynomial in the model and input sizes and constant in the number of emails already processed (due to caching).

---

## APPENDIX B: PUBLICATION DETAILS

Not applicable at the time of submission.

---

## APPENDIX C: PLAGIARISM REPORT

*This page is reserved for the Turnitin plagiarism report.*

*The plagiarism report shall be inserted here before final submission of the project report.*

