# CHAPTER 2: LITERATURE SURVEY
#
# Target: 7 pages (~1,960–2,100 words).
# References are numbered in order of first citation across the report.
# IEEE style: [N] Author(s), "Title," Venue, year, doi/url if known.
# Unverifiable details are marked [VERIFY].
# References sourced from AegisRAG_Synopsis.pdf §4.9 (refs [1]–[18]).

---

# CHAPTER 2: LITERATURE SURVEY

     This chapter reviews the published literature relevant to the three core problems addressed by AegisRAG: phishing detection, retrieval-augmented generation and hallucination, and claim-level explanation verification. The survey is organized into five thematic sections, preceded by a brief background on the key techniques, and concluded with a gap analysis and summary table.

## 2.1 BACKGROUND

     **Retrieval-Augmented Generation (RAG).** RAG augments a generative language model with a retrieval step: at inference time, the model fetches relevant documents from a corpus and conditions its output on the retrieved content rather than on parametric training knowledge alone [3]. This allows the model to ground responses in current, user-specific data. In AegisRAG, RAG is applied to email triage: the priority classifier retrieves the top-2 most similar past emails via cosine similarity over local sentence-transformer embeddings and uses them as context when querying the LLM for a relevance score.

     **Natural Language Inference and Claim Verification.** Natural language inference (NLI) is the task of determining whether one text (a hypothesis) is entailed by, contradicts, or is neutral with respect to a second text (a premise). Fine-tuned transformer models for NLI are standard components in fact-checking pipelines. In the claim-verification context relevant to this project, the premise is an evidence document assembled by the system and the hypothesis is an atomic claim extracted from the LLM-generated explanation. MiniCheck [4] uses this formulation with a RoBERTa-Large or DeBERTa-v3-Large encoder to predict a single "grounded" probability for each (claim, evidence) pair.

     **Email Authentication Protocols.** SPF (Sender Policy Framework), DKIM (DomainKeys Identified Mail), and DMARC (Domain-based Message Authentication, Reporting, and Conformance) are three complementary DNS-based protocols for authenticating the source of an email. SPF verifies that the sending mail server is authorized by the domain's DNS record. DKIM verifies a cryptographic signature added by the sending domain. DMARC specifies the policy to apply when SPF and DKIM fail. Gmail evaluates these protocols before delivery and records the results in the `Authentication-Results` header. AegisRAG parses this header rather than re-running DNS queries.

     **Evaluation Metrics.** The standard binary classification metrics used in this project are: precision (the fraction of flagged emails that are true phishing), recall (the fraction of phishing emails that are flagged), F1 (the harmonic mean of precision and recall), accuracy (the fraction of all emails correctly classified), and false-positive rate (FPR, the fraction of legitimate emails incorrectly flagged). For claim verification, precision and recall are defined over the set of unsupported claims: precision is the fraction of claims labeled unsupported by the verifier that are genuinely unsupported; recall is the fraction of genuinely unsupported claims that the verifier identifies.

## 2.2 LLM-BASED PHISHING DETECTION

     Heiding et al. [1] demonstrated that LLM-generated phishing emails achieve click-through and credibility rates comparable to human-crafted attacks on a dataset of 112 employees across multiple organizations. The same work showed that appropriately prompted LLMs can detect phishing intent at rates matching rule-based baselines, with the key limitation that the detection prompts used were optimized on the same LLM family used for generation, raising a potential evaluation bias. This dual finding — LLMs as simultaneous attack surface and detection tool — directly motivates AegisRAG's Gemini social-engineering analysis layer.

     Koide et al. [5] introduced ChatSpamDetector, using LLM prompting for phishing email detection evaluated on a labeled corpus [VERIFY exact dataset size and F1]. The approach is related to AegisRAG's Layer 4 (Gemini social-engineering), but AegisRAG combines LLM analysis with three independent detection layers and uses structured JSON output to extract four specific social-engineering vectors rather than free-form prompting.

     Chataut et al. [6] evaluated several LLMs for phishing detection and reported trade-offs between model capability and deployment cost across multiple commercially available and open-source models [VERIFY specific models and accuracy figures]. The results support the argument that LLM-based detection is feasible but must be balanced against API rate limits, which is why AegisRAG triggers its Gemini layer only when the preliminary score from the other three layers exceeds a threshold of 0.25.

     Lee [7] studied techniques for improving phishing email identification using LLMs, proposing enhanced prompting strategies [VERIFY specific dataset and measured improvement]. The work is relevant to the design of AegisRAG's structured JSON prompt for the social-engineering analysis, which explicitly enumerates the four vectors the model must assess.

     Hazell [2] examined LLM-assisted spear-phishing, finding that LLM assistance significantly reduces the cost and time required to craft targeted attacks. The implication for defensive systems is that detectors trained on older, manually crafted corpora may generalize poorly to LLM-generated content — a limitation that applies directly to AegisRAG's BERT classifier (Layer 3) and is acknowledged in the evaluation discussion.

## 2.3 TRADITIONAL AND HYBRID PHISHING DETECTION

     Asiri et al. [8] proposed PhishingRTDS, a real-time detection system using deep learning over URL and content features [VERIFY specific accuracy and dataset]. The work demonstrated that URL structural features — host type, domain age, and path patterns — are strong phishing discriminators, informing the design of AegisRAG's URL heuristics layer (Layer 2).

     Lee et al. [9] investigated multimodal LLMs for phishing webpage detection, combining visual rendering with textual analysis [VERIFY specific results]. While AegisRAG operates at the email level rather than webpage level, the finding that combining multiple modalities outperforms single-signal approaches reinforces the fusion design adopted in AegisRAG.

     Al-Subaiey et al. [10] presented an interpretable web-based phishing detection platform with per-feature explanations alongside classification decisions [VERIFY specific model and features]. The emphasis on interpretability aligns with AegisRAG's design of presenting per-layer scores and evidence to the user rather than a single opaque confidence number.

     Karim et al. [11] proposed a hybrid machine-learning approach for phishing detection using URL features, reporting on a standard benchmark [VERIFY specific dataset and F1]. The work is relevant to AegisRAG's Phase 1 evaluation design, which measures per-layer as well as fused performance to isolate each signal's contribution.

     Roumeliotis et al. [12] performed a comparative evaluation of fine-tuned LLMs, NLP models, and CNN architectures for spam classification, finding that fine-tuned transformer models outperform CNN-based approaches on standard metrics [VERIFY specific models compared]. This supports the choice of a pre-trained BERT-based model (`ealvaradob/bert-finetuned-phishing`) as AegisRAG's semantic classifier rather than a bag-of-words or convolutional architecture.

## 2.4 RETRIEVAL-AUGMENTED GENERATION AND HALLUCINATION

     Lewis et al. [3] introduced Retrieval-Augmented Generation, demonstrating that RAG-based models outperform purely parametric models on knowledge-intensive NLP tasks by grounding outputs in retrieved, up-to-date documents. The original work used a dense retrieval component (DPR) over Wikipedia documents. AegisRAG applies the same principle locally: sentence-transformer embeddings computed over the user's own email history replace the dense retrieval index, and the evidence items retrieved are used both by the priority classifier and the explanation generator.

     Niu et al. [13] introduced RAGTruth, a hallucination corpus for evaluating RAG systems, showing that hallucinations occur even when relevant documents are retrieved successfully. The corpus categorizes hallucination types (word-level contradictions, sentence-level fabrications, and omissions) and demonstrates that standard RAG pipelines introduce them at non-trivial rates across multiple benchmarks. This directly motivates the claim-verification stage in AegisRAG: even when the system retrieves its own evidence items correctly, the LLM-generated explanation may introduce ungrounded or fabricated details not present in the evidence.

## 2.5 CLAIM VERIFICATION AND HALLUCINATION DETECTION

     Manakul et al. [14] proposed SelfCheckGPT, detecting hallucinations without external ground truth by checking consistency across multiple independently sampled model outputs. While AegisRAG uses a different approach — NLI-based verification against system-constructed evidence rather than self-consistency — SelfCheckGPT is a relevant baseline alternative and illustrates the same research problem of checking LLM outputs automatically.

     Min et al. [15] introduced FActScore, a framework for fine-grained evaluation of factual precision in long-form text generation. FActScore decomposes generated text into atomic facts and checks each against a knowledge source, producing a per-claim factual precision score. AegisRAG's pipeline follows the same structural pattern: Gemini decomposes the explanation into atomic claims (at most six), and MiniCheck checks each claim against the system's assembled evidence set. The key difference is that AegisRAG uses a closed, system-generated evidence set rather than an open-domain knowledge base.

     Dhuliawala et al. [16] proposed Chain-of-Verification, a prompting technique that reduces hallucination by having the model generate explicit verification questions about its own outputs and then answer those questions. The method demonstrated reduced hallucination rates on factual question answering tasks [VERIFY specific datasets and reduction figures]. AegisRAG does not use Chain-of-Verification directly, but the motivating insight is the same: LLM outputs should be subjected to a verification step before being presented to users as facts.

     Tang et al. [4] introduced MiniCheck, an efficient fact-checking model for grounding LLM outputs against supporting documents. MiniCheck is fine-tuned to check whether a claim is supported by a given document, using a RoBERTa-Large or DeBERTa-v3-Large backbone that runs substantially faster than full LLM-based verification while maintaining competitive performance on standard fact-checking benchmarks. AegisRAG uses the MiniCheck-RoBERTa-Large variant loaded directly via the Hugging Face Transformers library. Each claim is evaluated against the full evidence document and each individual evidence item in a single batched forward pass; the maximum of these probabilities is taken as the final confidence, and a claim is labelled "supported" if this confidence meets the configured threshold of 0.10.

     Devlin et al. [17] introduced BERT, the pre-training approach that underlies both the phishing classifier used in AegisRAG (`ealvaradob/bert-finetuned-phishing`) and the cross-encoder architecture used by MiniCheck and similar NLI models. BERT's bidirectional masked-language-model pre-training produces general-purpose representations that can be fine-tuned on downstream classification tasks with relatively small amounts of labeled data.

## 2.6 INDUSTRY CONTEXT

     The Anti-Phishing Working Group [18] publishes quarterly phishing activity trend reports documenting the volume and variety of active attacks. The APWG data consistently places phishing among the most common forms of cybercrime and records the growing use of AI-generated content in attack campaigns. This industry context establishes the problem scale that AegisRAG is designed to address: phishing is not a static or declining threat, and detection systems must reason semantically about email content rather than relying on static signatures.

## 2.7 GAP ANALYSIS

     Table 2.1 summarizes the principal gaps in the surveyed literature that AegisRAG is designed to address.

<!-- TABLE 2.1 -->
[Table 2.1: Literature Survey: Problem, Method, Key Finding, Limitation, and Relevance to AegisRAG]

| Ref | Problem | Method | Key Finding | Limitation | Relevance |
|---|---|---|---|---|---|
| [1] | LLM phishing gen/detect | LLM prompting on 112-employee dataset | LLM attacks match human attacks; LLM detection matches rules | Evaluation bias; same LLM family for gen and detect | Motivates Gemini social layer |
| [5] | Email phishing detection | LLM prompting (ChatSpamDetector) | Viable prompt-based classification [VERIFY metrics] | API cost; no fusion with other signals | Related to Layer 4 design |
| [6] | LLM phishing detection | Multiple LLMs compared [VERIFY] | Feasible but cost-sensitive [VERIFY] | No local deployment path | Motivates conditional LLM trigger |
| [7] | Phishing identification | Enhanced LLM prompting [VERIFY] | Improved accuracy [VERIFY] | [VERIFY] | Informs structured JSON prompt design |
| [8] | Real-time phishing | Deep learning, URL+content features | URL features are strong discriminators [VERIFY accuracy] | Dataset specificity | Informs Layer 2 (URL heuristics) |
| [9] | Phishing webpage detect | Multimodal LLM | Multimodal > text-only [VERIFY] | Webpage-level only | Reinforces multi-signal fusion |
| [10] | Phishing email detect | Interpretable ML platform | Per-feature transparency valuable [VERIFY] | [VERIFY model] | Aligns with per-layer UI design |
| [11] | URL-based phishing | Hybrid ML + URL features | Competitive on benchmark [VERIFY] | URL-only | Informs Phase 1 per-layer evaluation |
| [12] | Email spam classify | Fine-tuned transformers vs CNN | Transformers outperform CNNs [VERIFY] | Spam, not targeted phishing | Supports BERT classifier choice |
| [2] | LLM spear-phishing | LLM-assisted attack generation | Attack cost reduced significantly | Detector generalization gap | Explains BERT limitation |
| [13] | RAG hallucination | Corpus analysis (RAGTruth) | Hallucinations persist after correct retrieval | Corpus size | Core motivation for Ch 6 verifier |
| [3] | Knowledge-intensive NLP | Dense retrieval + generative LM | RAG > parametric on knowledge tasks | Retrieval index required | Foundational architecture |
| [14] | LLM hallucination detect | Self-consistency sampling | Inconsistency ≈ hallucination | Multiple inference passes costly | Baseline alternative to NLI verify |
| [15] | Factual precision eval | Atomic fact decomposition (FActScore) | Per-claim precision measurable | Open-domain KB required | Template for Ch 5 pipeline |
| [16] | LLM hallucination | Chain-of-Verification prompting | Hallucination reduced [VERIFY exact figures] | Adds LLM inference overhead | Motivates verification step |
| [4] | LLM grounding | MiniCheck (RoBERTa-L / DeBERTa) | Fast, competitive fact-checking | Two-label output only | Core verifier in AegisRAG |
| [17] | NLP pre-training | BERT (masked LM, bidirectional) | Strong transfer learning for classification | Large fine-tuning data needed | Backbone of Layer 3 and NLI models |
| [18] | Phishing trends | APWG quarterly reports | Sustained phishing growth | Aggregate statistics only | Problem scale and context |

     The gap that AegisRAG addresses is the intersection of these themes. No published system simultaneously (a) unifies priority triage with phishing detection so that the same retrieved evidence feeds both paths, and (b) decomposes the system's own explanation into atomic claims and checks each claim against that evidence using a local NLI model before presenting the explanation to the user. AegisRAG is the first known implementation of this combined pipeline in a self-hosted, evaluation-backed form.

     It is important to state what AegisRAG does not claim. The "supported" label means that a claim is consistent with the system's own assembled evidence — it does not mean the claim is independently true. The evidence set is constructed by the system from header parsing, rule-based features, and retrieved email snippets, and may be incomplete. The system's contribution is therefore to prevent the LLM from adding claims that go beyond what the evidence records contain, not to guarantee the factual accuracy of the underlying evidence.
