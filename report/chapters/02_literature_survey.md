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

     **Natural Language Inference and Claim Verification.** Natural language inference (NLI) is the task of determining whether one text (a hypothesis) is entailed by, contradicts, or is neutral with respect to a second text (a premise). Fine-tuned transformer models for NLI are standard components in fact-checking pipelines. In the claim-verification context relevant to this project, the premise is an evidence document assembled by the system and the hypothesis is an atomic claim extracted from the LLM-generated explanation. MiniCheck [4] uses this formulation with a specialized encoder to predict a single grounded probability for each (claim, evidence) pair.

     **Email Authentication Protocols.** SPF (Sender Policy Framework), DKIM (DomainKeys Identified Mail), and DMARC (Domain-based Message Authentication, Reporting, and Conformance) are three complementary DNS-based protocols for authenticating the source of an email. SPF verifies that the sending mail server is authorized by the domain's DNS record. DKIM verifies a cryptographic signature added by the sending domain. DMARC specifies the policy to apply when SPF and DKIM fail. Gmail evaluates these protocols before delivery and records the results in the `Authentication-Results` header. AegisRAG parses this header rather than re-running DNS queries.

     **Evaluation Metrics.** The standard binary classification metrics used in this project are: precision (the fraction of flagged emails that are true phishing), recall (the fraction of phishing emails that are flagged), F1 (the harmonic mean of precision and recall), accuracy (the fraction of all emails correctly classified), and false-positive rate (FPR, the fraction of legitimate emails incorrectly flagged). For claim verification, precision and recall are defined over the set of unsupported claims: precision is the fraction of claims labeled unsupported by the verifier that are genuinely unsupported; recall is the fraction of genuinely unsupported claims that the verifier identifies.

## 2.2 LLM-BASED PHISHING DETECTION

     Heiding et al. [1] investigated the dual potential of large language models for creating and detecting phishing emails. In an experimental evaluation, the authors sent phishing emails to 112 recruited participants, comparing generic control emails, emails generated automatically using GPT-4, emails designed manually using cognitive heuristics (the V-Triad), and a combined GPT-4 and V-Triad approach. The GPT-4 emails achieved a 30–44% click-through rate, outperforming the generic control group (19–28%), while emails combining GPT-4 with V-Triad heuristics reached 43–81%. To evaluate defensive capabilities, four language models (GPT, Claude, PaLM, and LLaMA) were prompted to detect malicious intent in phishing emails; while the models demonstrated strong detection capability and sometimes exceeded human detection, they were often slightly less accurate than human evaluators. Their economic analysis concluded that LLMs increase phishing incentives by drastically lowering generation costs.

     Koide et al. [5] introduced ChatSpamDetector, a system that transforms email data into prompts for large language models to perform phishing email classification and provide natural-language reasoning for its decisions. Evaluating the method on a comprehensive phishing email dataset, the authors confirmed that ChatSpamDetector using GPT-4 achieved 99.70% accuracy, leveraging contextual interpretation to identify sophisticated impersonation and social-engineering tactics while supplying users with explanatory justifications to resolve ambiguity.

     Chataut et al. [6] conducted a study on large language models for phishing detection ("Can AI Keep You Safe? A Study of Large Language Models for Phishing Detection"), examining whether current AI models can effectively safeguard users against evolving phishing campaigns [VERIFY specific models and dataset from full proceedings].

     Lee [7] studied the efficacy of large language models for identifying phishing emails, showing that LLMs can achieve high detection accuracy at high precision while providing interpretable evidence to support classification decisions.

     Hazell [2] examined the malicious use of LLMs for spear-phishing, demonstrating that models can assist with both reconnaissance and personalized message generation. The author generated unique spear-phishing messages targeting over 600 British Members of Parliament using GPT-3.5 and GPT-4, establishing that LLMs can produce realistic, highly targeted messages at a cost of less than a fraction of a cent per email. The work demonstrated that basic prompt engineering can circumvent safety guardrails and explored LLM-based defensive systems as a countermeasure.

## 2.3 TRADITIONAL AND HYBRID PHISHING DETECTION

     Asiri et al. [8] developed PhishingRTDS, proposing a real-time detection architecture for phishing attacks based on deep learning over structural features [VERIFY specific model architecture and dataset from publication].

     Lee et al. [9] investigated the application of multimodal large language models for phishing webpage detection. Noting that computer-vision brand-matching techniques require maintaining large reference lists of logos and frequent retraining, the authors evaluated multimodal LLMs in recognizing brand visual cues (logos, page themes, and favicons) to detect deceptive pages by comparing visual elements with reference domain metadata.

     Al-Subaiey et al. [10] presented an interpretable, robust web-based AI platform for phishing email detection. The work addresses the reliance of existing detectors on proprietary, closed datasets and black-box classifiers by combining open data with interpretable feature contributions, providing human-understandable justifications alongside email risk classifications.

     Karim et al. [11] investigated URL-based phishing detection using machine learning, evaluating multiple classifiers and proposing a hybrid model combining logistic regression, support vector machines, and decision trees (the LSD model) with soft and hard voting. Evaluated on an extracted dataset of over 11,000 website URL feature vectors using canopy feature selection and hyperparameter optimization, the hybrid architecture outperformed individual baseline classifiers across accuracy, precision, recall, and F1-score.

     Roumeliotis et al. [12] performed a comparative fine-tuning evaluation of large language models (GPT-4) and transformer NLP models (BERT, RoBERTa) against traditional Convolutional Neural Networks (CNNs) for email spam and phishing classification. The experimental results demonstrated that fine-tuned transformer models significantly outperformed CNN architectures, effectively identifying spam and phishing attacks while minimizing false positives.

## 2.4 RETRIEVAL-AUGMENTED GENERATION AND HALLUCINATION

     Lewis et al. [3] introduced Retrieval-Augmented Generation (RAG), combining pre-trained parametric memory (a sequence-to-sequence model) with non-parametric memory (a dense vector index of Wikipedia accessed via a neural retriever). Evaluated across knowledge-intensive NLP tasks including open-domain question answering, RAG models established state-of-the-art results, generating more factual and specific outputs than purely parametric models while allowing non-parametric knowledge to be updated without retraining.

     Niu et al. [13] introduced RAGTruth, a benchmark corpus comprising nearly 18,000 naturally generated responses from diverse LLMs in standard RAG pipelines, manually annotated at word and passage levels for hallucination intensity. The study showed that language models frequently generate unsupported or contradictory statements even when relevant source documents are retrieved, and demonstrated that fine-tuning a small model on high-quality annotation data can achieve hallucination detection performance competitive with GPT-4.

## 2.5 CLAIM VERIFICATION AND HALLUCINATION DETECTION

     Manakul et al. [14] proposed SelfCheckGPT, a zero-resource, black-box hallucination detection method for generative models. Operating without external databases or token probability distributions, SelfCheckGPT generates multiple stochastic response samples from the model and measures consistency across samples; hallucinated facts diverge across stochastic draws while supported facts remain consistent. Evaluated on GPT-3 generated passages from WikiBio, SelfCheckGPT outperformed grey-box baselines in sentence-level hallucination detection and passage factuality ranking.

     Min et al. [15] introduced FActScore, an evaluation framework that breaks long-form text generations into atomic factual claims and measures the percentage of claims supported by a reliable knowledge source. Evaluating commercial LLMs (including InstructGPT, ChatGPT, and PerplexityAI) on biography generation, the authors documented that even advanced commercial models exhibit non-trivial error rates (e.g., ChatGPT scoring 58%), demonstrating that coarse whole-response metrics obscure factual errors and that atomic decomposition is necessary for accurate factuality assessment.

     Dhuliawala et al. [16] developed Chain-of-Verification (CoVe), a deliberation framework that reduces hallucination by prompting an LLM to draft an initial response, formulate verification questions to check its claims, answer those questions independently without context bias, and synthesize a final verified response. CoVe demonstrated consistent hallucination reductions across Wikidata question answering, MultiSpanQA, and long-form text generation.

     Tang et al. [4] introduced MiniCheck, an efficient fact-checking framework designed to verify whether LLM generations are grounded in source evidence. By generating synthetic training instances of factual errors with GPT-4 and training a specialized lightweight encoder, MiniCheck-FT5 (770M parameters) achieved GPT-4-level factuality evaluation accuracy at 400x lower inference cost on the aggregated LLM-AggreFact benchmark. AegisRAG integrates this formulation to evaluate each atomic explanation claim against the retrieved evidence set.

     Devlin et al. [17] introduced BERT (Bidirectional Encoder Representations from Transformers), pre-training deep bidirectional representations from unlabeled text by jointly conditioning on left and right context across all layers. BERT established state-of-the-art performance across eleven NLP benchmarks (including GLUE, MultiNLI, and SQuAD) with simple task-specific output layers, providing the underlying architecture used by both AegisRAG's local semantic classifier and modern NLI cross-encoders.

## 2.6 INDUSTRY CONTEXT

     The Anti-Phishing Working Group (APWG) [18] publishes quarterly phishing activity trend reports documenting aggregate metrics on global phishing attack volume, targeted economic sectors, and evolving attacker techniques. These industry reports emphasize that email-based deception remains one of the primary vectors for organizational compromise, underlining the necessity for email assistants to evaluate semantic manipulation alongside technical authentication.

## 2.7 GAP ANALYSIS

     Table 2.1 summarizes the principal gaps in the surveyed literature that AegisRAG is designed to address.

<!-- TABLE 2.1 -->
[Table 2.1: Literature Survey: Problem, Method, Key Finding, Limitation, and Relevance to AegisRAG]

| Ref | Problem | Method | Key Finding | Limitation | Relevance |
|---|---|---|---|---|---|
| [1] | LLM phishing creation and detection | GPT-4 vs V-Triad on 112 recruited participants; 4 LLMs for intent detection | GPT-4 emails achieved 30–44% click-through; LLMs detect intent but slightly lag humans | LLM detection slightly less accurate than human evaluators | Motivates Gemini social engineering layer |
| [5] | Email phishing classification | Prompt-based LLM classification (ChatSpamDetector) | 99.70% accuracy with GPT-4 and natural-language explanations | Cost of LLM inference per email | Informs explainable threat layer design |
| [6] | LLM phishing detection capability | Empirical LLM evaluation for phishing detection [VERIFY] | Explores LLM defense viability [VERIFY] | [VERIFY] | Motivates threshold-gated LLM invocation |
| [7] | Phishing email identification | LLM detection with evidence extraction | High accuracy with interpretable decision evidence | Generative API latency | Informs structured JSON evidence format |
| [8] | Real-time phishing defense | Deep learning on URL and content features (PhishingRTDS) | Real-time phishing attack detection [VERIFY] | [VERIFY] | Informs Layer 2 (URL heuristics) |
| [9] | Phishing webpage identification | Multimodal LLMs evaluating logos, themes, and favicons | Multimodal reasoning eliminates costly visual reference retraining | Webpage-level analysis, not raw email headers | Reinforces multi-signal evidence fusion |
| [10] | Interpretable phishing detection | Feature-interpretable web platform | Transparent feature-level justifications for classifications | Relies on feature engineering | Aligns with multi-layer dashboard display |
| [11] | URL-based phishing detection | Hybrid ML (LSD: LR+SVC+DT) on 11,000+ website URL dataset | Hybrid model outperforms individual classifiers across accuracy and F1 | URL-only analysis without email text or headers | Informs URL heuristics and layer evaluation |
| [12] | Email spam and phishing filtering | Fine-tuning LLMs (GPT-4) and transformers (BERT, RoBERTa) vs CNNs | Fine-tuned transformers outperform CNNs while minimizing false positives | Computational footprint of transformer models | Supports pre-trained BERT provider |
| [2] | LLM spear-phishing risks | LLM targeting 600+ UK MPs; prompt injection analysis | Realistic messages generated at fraction-of-a-cent cost; prompts bypass guards | Demonstrates vulnerability of purely static filters | Motivates defense against novel LLM attacks |
| [13] | Hallucination in RAG pipelines | RAGTruth: 18,000 response corpus with word-level annotations | LLMs frequently hallucinate despite retrieved context; small models can detect it | Benchmark corpus, not an inline mitigation engine | Direct motivation for explanation verification |
| [3] | Knowledge-intensive NLP | Pre-trained seq2seq + dense Wikipedia vector retrieval | RAG outperforms purely parametric models on open-domain QA | Dense retrieval index maintenance | Architectural foundation for inbox RAG |
| [14] | Black-box hallucination detection | SelfCheckGPT: stochastic sampling consistency on WikiBio | Detects non-factual sentences without external database access | Multiple stochastic generation passes costly | Alternative baseline to NLI cross-encoder |
| [15] | Long-form factual precision | FActScore: atomic claim decomposition and verification | Commercial LMs exhibit high error rates (ChatGPT 58% factuality) | Requires reference knowledge source | Structural template for claim decomposition |
| [16] | LLM hallucination reduction | Chain-of-Verification (CoVe) deliberation prompting | Generates verification questions to decrease hallucinations across tasks | Adds multiple LLM inference rounds | Emphasizes verification before output |
| [4] | Efficient claim grounding | MiniCheck: lightweight encoder trained on synthetic errors | Matches GPT-4 factuality accuracy at 400x lower cost on LLM-AggreFact | Two-label classification only | Core NLI verifier in AegisRAG pipeline |
| [17] | Deep bidirectional representations | BERT masked-language-model pre-training | State-of-the-art transfer learning across 11 NLP benchmarks | Requires fine-tuning data for target domain | Backbone for semantic layer and NLI models |
| [18] | Global phishing trends | APWG quarterly threat reports | Sustained growth in attack volume and AI-assisted social engineering | Aggregate statistics without inline defense | Demonstrates real-world problem scale |

     The gap that AegisRAG addresses is the intersection of these themes. No published system simultaneously (a) unifies priority triage with phishing detection so that the same retrieved evidence feeds both paths, and (b) decomposes the system's own explanation into atomic claims and checks each claim against that evidence using a local NLI model before presenting the explanation to the user. AegisRAG is the first known implementation of this combined pipeline in a self-hosted, evaluation-backed form.
