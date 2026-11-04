# FRONT MATTER
#
# Build instructions for build_report.py:
#   - Cover page: use COVER section below
#   - Certificate: use CERTIFICATE section
#   - Acknowledgement: use ACKNOWLEDGEMENT section
#   - Abstract: use ABSTRACT section
#   - List of Abbreviations: use ABBREVIATIONS section
# All front-matter pages use small Roman page numbers (i, ii, iii ...).
# The Word TOC, List of Figures, and List of Tables are inserted as Word
# field codes (TOC, SEQ Figure, SEQ Table) so that Ctrl+A, F9 refreshes them.

---
## COVER

<!-- FORMAT: P-1 template from VIIT format document. -->
<!-- All text centred. Spacing as specified in format doc. -->

[FOUR BLANK LINES]

A REPORT ON
<!-- 12 pt bold, upper case -->

[TWO BLANK LINES]

AEGISRAG: A SELF-VERIFYING AGENTIC EMAIL ASSISTANT WITH RAG-BASED PRIORITIZATION, PHISHING DETECTION, AND CLAIM-LEVEL EXPLANATION VERIFICATION
<!-- 16 pt bold, upper case — use project title from synopsis exactly -->

[TWO BLANK LINES]

SUBMITTED TO THE VISHWAKARMA INSTITUTE OF INFORMATION TECHNOLOGY, PUNE
IN THE PARTIAL FULFILLMENT OF THE REQUIREMENTS
FOR THE AWARD OF THE DEGREE
<!-- 12 pt, upper case -->

OF
<!-- 12 pt, upper case -->

[TWO BLANK LINES]

BACHELOR OF TECHNOLOGY (COMPUTER ENGINEERING)
<!-- 16 pt bold, upper case -->

[TWO BLANK LINES]

SUBMITTED BY
<!-- 12 pt, upper case -->

[TWO BLANK LINES]

TANISHQ RAINA        EXAM SEAT NO.: [EXAM SEAT NO. TANISHQ]
<!-- 12 pt bold/upper case -->

ALPESH THOOL         EXAM SEAT NO.: [EXAM SEAT NO. ALPESH]

TAYYAB MOHAMMED      EXAM SEAT NO.: [EXAM SEAT NO. TAYYAB]

CHINMAY KALE         EXAM SEAT NO.: [EXAM SEAT NO. CHINMAY]

[TWO BLANK LINES]

<!-- VIIT Logo here — insert viit_logo.png -->

DEPARTMENT OF COMPUTER ENGINEERING
<!-- 16 pt bold, upper case -->

[ONE BLANK LINE]

BRACT'S
VISHWAKARMA INSTITUTE OF INFORMATION TECHNOLOGY
<!-- 12 pt bold, upper case -->

[ONE BLANK LINE]

SURVEY NO. 3/4, KONDHWA (BUDRUK), PUNE – 411048, MAHARASHTRA (INDIA).
<!-- 12 pt bold, upper case -->

[ONE BLANK LINE]

BRACT'S
VISHWAKARMA INSTITUTE OF INFORMATION TECHNOLOGY, PUNE
<!-- 12 pt bold, upper case -->

2026–2027
<!-- 12 pt bold, upper case -->

---
## CERTIFICATE

<!-- FORMAT: P-2 template from VIIT format document. -->

<!-- VIIT Logo here -->

CERTIFICATE
<!-- 14 pt bold, upper case, centred -->

[THREE BLANK LINES]

This is to certify that the project report entitled
<!-- 12 pt, sentence case -->

[ONE BLANK LINE]

AEGISRAG: A SELF-VERIFYING AGENTIC EMAIL ASSISTANT WITH RAG-BASED PRIORITIZATION, PHISHING DETECTION, AND CLAIM-LEVEL EXPLANATION VERIFICATION
<!-- 12 pt bold, upper case -->

[TWO BLANK LINES]

Submitted by

[ONE BLANK LINE]

TANISHQ RAINA        EXAM SEAT NO.: [EXAM SEAT NO. TANISHQ]

ALPESH THOOL         EXAM SEAT NO.: [EXAM SEAT NO. ALPESH]

TAYYAB MOHAMMED      EXAM SEAT NO.: [EXAM SEAT NO. TAYYAB]

CHINMAY KALE         EXAM SEAT NO.: [EXAM SEAT NO. CHINMAY]

[ONE BLANK LINE]

is a Bonafide student at this institute and the work has been carried out by him/her under the supervision of Prof. Mandar Diwakar [CONFIRM title] and it is approved for the partial fulfillment of the requirement of VISHWAKARMA INSTITUTE OF INFORMATION TECHNOLOGY, for the award of the degree of Bachelor of Technology (Computer Engineering).
<!-- 12 pt, sentence case -->

[ONE BLANK LINE]

[FOUR BLANK LINES]

(Prof. Mandar Diwakar [CONFIRM title])        (Dr. S. R. Shinde) [CONFIRM current HoD name]
Guide                                          Head,
Department of Computer Engineering             Department of Computer Engineering
<!-- 12 pt, sentence case -->

[THREE BLANK LINES]

(Dr. Vivek Deshpande) [CONFIRM current Director name]
Director,
BRACT's Vishwakarma Institute of Information Technology, Pune-48

Place: Pune
Date:

---
## ACKNOWLEDGEMENT

<!-- 14 pt bold, upper case, centred -->

ACKNOWLEDGEMENT

     It gives us great pleasure in presenting this project report on "AegisRAG: A Self-Verifying Agentic Email Assistant with RAG-Based Prioritization, Phishing Detection, and Claim-Level Explanation Verification."

     We express our sincere gratitude to our project guide, Prof. Mandar Diwakar [CONFIRM title], Department of Computer Engineering, Vishwakarma Institute of Information Technology, for his constant guidance, constructive suggestions, and encouragement throughout the course of this project. His insights shaped the direction of the work at every stage.

     We are grateful to Dr. S. R. Shinde [CONFIRM], Head of the Department of Computer Engineering, VIIT, for providing the resources and environment necessary to carry out this project. We also thank the faculty members of the Department of Computer Engineering for their support and advice.

     We thank the project coordinator and all reviewers whose feedback helped us improve the quality of this work.

     We are thankful to our parents and families for their patience and encouragement throughout the duration of this project.

[BLANK LINES]

Tanishq Raina

Alpesh Thool

Tayyab Mohammed

Chinmay Kale

---
## ABSTRACT

ABSTRACT
<!-- 14 pt bold, upper case, centred — note: format doc shows ABSTRACT at top of page -->

     Email remains one of the primary attack surfaces for phishing and social-engineering fraud, while the volume of legitimate mail in an average inbox makes manual triage impractical. Agentic AI systems that use Retrieval-Augmented Generation (RAG) to prioritize email have begun to address the triage problem, but they leave two related gaps: phishing detection and priority ranking are treated as separate concerns, and the natural-language explanations that such systems generate for their decisions are not checked against the evidence on which those decisions were based, creating a trust gap when ungrounded reasoning reaches the user.

     This report describes AegisRAG, a local, self-hosted agentic email assistant that addresses both gaps in a single pipeline. The system ingests Gmail messages via the Gmail API, computes local sentence-transformer embeddings for RAG-based retrieval, and classifies each email's priority using a weighted combination of deterministic rules and a Gemini large-language-model score. In parallel, a four-layer phishing detector — comprising sender-authentication parsing, URL and domain heuristics, a fine-tuned BERT classifier, and a Gemini social-engineering check — produces a fraud confidence score through a fixed-weight fusion engine. A single unified explanation is then generated by Gemini, grounded in a numbered set of system-verified evidence items; the explanation is decomposed into atomic claims; and each claim is independently verified against the evidence using the MiniCheck-RoBERTa-Large natural language inference model. Only claims confirmed as supported are shown to the user by default, with removed claims available on demand.

     The system was evaluated in two phases. Phase 1 measured detection performance across three evaluation sets: a curated set of 20 labeled emails with realistic headers (fused F1 = 0.90, one false positive on legitimate email), a 300-email holdout from a public BERT training dataset (F1 = 0.9949 with a noted data-leakage caveat), and 14 hand-labelled real-inbox emails (fused recall = 0.40, zero false positives). Phase 2 measured claim-verification performance: a synthetic benchmark of 40 test claims showed 100% ungrounded-claim reduction (by construction); an end-to-end evaluation across 90 LLM-generated claims (90 annotated by the authors) showed verifier precision of 0.60, recall of 0.60, F1 of 0.60, and a 44.6% relative reduction in the ungrounded-claim rate. An exploratory post-hoc threshold sensitivity sweep over the range 0.1 to 0.9 is also reported. All code, evaluation scripts, and results are available in the project repository.

---
## ABBREVIATIONS

LIST OF ABBREVIATIONS

<!-- Format: two-column table, left = abbreviation, right = expansion.
     Sorted alphabetically. -->

| Abbreviation | Expansion |
|---|---|
| API | Application Programming Interface |
| APWG | Anti-Phishing Working Group |
| BERT | Bidirectional Encoder Representations from Transformers |
| CDN | Content Delivery Network |
| CPU | Central Processing Unit |
| CUDA | Compute Unified Device Architecture |
| DFD | Data Flow Diagram |
| DKIM | DomainKeys Identified Mail |
| DMARC | Domain-based Message Authentication, Reporting, and Conformance |
| ER | Entity Relationship |
| ESP | Email Service Provider |
| F1 | Harmonic mean of Precision and Recall |
| FAISS | Facebook AI Similarity Search |
| FastAPI | Fast Application Programming Interface (Python web framework) |
| FP | False Positive |
| FPR | False Positive Rate |
| GPU | Graphics Processing Unit |
| HF | Hugging Face |
| HTML | HyperText Markup Language |
| HTTP | HyperText Transfer Protocol |
| HTTPS | HyperText Transfer Protocol Secure |
| HTMX | Hypertext Markup Language eXtensions |
| IP | Internet Protocol |
| JSON | JavaScript Object Notation |
| LLM | Large Language Model |
| NLI | Natural Language Inference |
| NLP | Natural Language Processing |
| OAuth | Open Authorization |
| ORM | Object-Relational Mapper |
| PDF | Portable Document Format |
| PRN | Permanent Registration Number |
| RAG | Retrieval-Augmented Generation |
| REST | Representational State Transfer |
| SPF | Sender Policy Framework |
| SQL | Structured Query Language |
| SQLite | Structured Query Language Lite (embedded database engine) |
| TLD | Top-Level Domain |
| TOC | Table of Contents |
| UI | User Interface |
| URL | Uniform Resource Locator |
| WAL | Write-Ahead Logging |
| XAI | Explainable Artificial Intelligence |
| XSS | Cross-Site Scripting |

