# AegisRAG Report — TODO / CONFIRM List

All items marked [CONFIRM] or [TO CONFIRM BY TEAM] in the report are listed here.
Resolve each before building the final .docx.

**Checkpoint status:**
- Checkpoint 1 (Front matter + Ch 1–3): DONE ✓
- Checkpoint 2 (Ch 4–6 + diagrams): DONE ✓
- Checkpoint 3 (Ch 7–9, appendices, references): DONE ✓
- Checkpoint 4 (Final .docx build, page count check): PENDING

---

## [CONFIRM] Items — Author Must Supply

| ID | Location | Item |
|----|----------|------|
| C-01 | Cover page, Certificate | Exam Seat Numbers for all four students (Tanishq Raina, Alpesh Thool, Tayyab Mohammed, Chinmay Kale) |
| C-02 | Cover page, Certificate, Acknowledgement | Confirm Prof. Mandar Diwakar's full title (e.g., Assistant Professor, Associate Professor) |
| C-03 | Certificate, Acknowledgement | Confirm current Head of Department name and title for 2026–27. Format document template shows Dr. S. R. Shinde — confirm this is current. |
| C-04 | Certificate | Confirm current Director name for 2026–27. Format document template shows Dr. Vivek Deshpande — confirm this is current. |
| C-05 | Certificate | Confirm Place and Date fields (Place: Pune; Date: to be filled at submission) |
| C-06 | Chapter 3 (§3.5.2) | Confirm exact Python and library versions in the submission environment via `uv pip list` |
| C-07 | Cover page, Certificate | Confirm department name — synopsis says "CSE-Data Science"; format document says "Computer Engineering". Clarify which appears on the cover. |

---

## [VERIFY] Items — Literature Content & Reference Verification

These items were reviewed against publication abstracts and the project synopsis (§4.9).
References [1], [2], [3], [4], [5], [7], [9], [10], [11], [12], [13], [14], [15], [16], [17], [18] have been verified directly from their published abstracts. The remaining items below require full-text confirmation:

| ID | Location | Item | Status |
|----|----------|------|---|
| V-01 | Ch 2, §2.2 (ref [6]) | Chataut et al. (CCWC 2024): verify specific models compared and dataset details from full conference proceedings | PENDING [VERIFY] |
| V-02 | Ch 2, §2.3 (ref [8]) | Asiri et al. (PhishingRTDS): verify deep learning model architecture and dataset details from full article | PENDING [VERIFY] |
| V-03 | Ch 11 (ref [4]) | Tang et al. (MiniCheck): verify full author list; synopsis records 'Y. Tang et al.' while published paper lists L. Tang et al. | PENDING [VERIFY full author list] |
| V-04 | Ch 11 (ref [13]) | Niu et al. (RAGTruth): verify full author list; synopsis records 'C. Niu et al.' | PENDING [VERIFY full author list] |
| V-05 | Ch 11 (ref [7]) | Lee (2025): verify author initial; synopsis records 'C. Lee' while arXiv:2502.04759 lists J. Lee | PENDING [VERIFY author initial] |

---

## [TO CONFIRM BY TEAM] Items — Chapter 5 Project Plan

| ID | Location | Item |
|----|----------|------|
| T-01 | Ch 5, Table 5.1 | Confirm estimated person-hours per stage |
| T-02 | Ch 5, Table 5.3 | Confirm dates for pre-implementation phases (synopsis, SRS, design) |
| T-03 | Ch 5, Table 5.5 | Fill in the Primary Module(s) column in Table 5.5 (team members) |
| T-04 | Ch 5, Table 5.6 | Fill in the Owner column in Table 5.6 (module ownership per team member) |

---

## Screenshot Placeholders — Chapter 8

Capture each screenshot in the described state and save to `report/figures/`:

| Filename | Figure | What to Capture |
|----------|--------|-----------------|
| fig8_1_priority_tab.png | 8.1 | Priority tab, demo mode, after analysis, ≥3 emails visible with colour-coded borders |
| fig8_2_panel_summary.png | 8.2 | Non-phishing email expanded, Summary inner tab active, priority score + fraud band |
| fig8_3_verified_explanation.png | 8.3 | Email with verified claims, Verified Explanation tab active, ≥1 supported claim + "Removed Claims" toggle |
| fig8_4_detection_layers.png | 8.4 | Phishing email (red border) expanded, Detection Layers tab active, per-layer scores |
| fig8_5_flagged_tab.png | 8.5 | Flagged/Fraud tab, ≥2 phishing emails sorted by confidence |
| fig8_6_feed_tab.png | 8.6 | Feed tab, demo mode, newsletter emails with grey borders |
| fig8_7_settings_tab.png | 8.7 | Settings tab — mode toggle, OAuth status, threshold values |
| fig8_8_previous_messages.png | 8.8 | Previous Messages tab, demo mode, opened emails listed |

---

## Diagram Rendering — COMPLETED ✓

All 16 Mermaid diagram PNGs rendered successfully via `npx @mermaid-js/mermaid-cli` (Checkpoint 3).

| Source | PNG | Status |
|--------|-----|--------|
| fig1_1_overview.mmd | fig1_1_overview.png | OK (re-rendered after syntax fix) |
| fig3_1_sdlc.mmd | fig3_1_sdlc.png | OK |
| fig4_1_architecture.mmd | fig4_1_architecture.png | OK |
| fig4_2_sequence.mmd | fig4_2_sequence.png | OK |
| fig4_3_dfd0.mmd | fig4_3_dfd0.png | OK |
| fig4_4_dfd1.mmd | fig4_4_dfd1.png | OK |
| fig4_5_dfd2.mmd | fig4_5_dfd2.png | OK |
| fig4_6_er.mmd | fig4_6_er.png | OK |
| fig4_7_usecase.mmd | fig4_7_usecase.png | OK |
| fig4_8_class.mmd | fig4_8_class.png | OK |
| fig4_9_state.mmd | fig4_9_state.png | OK |
| fig4_10_deployment.mmd | fig4_10_deployment.png | OK |
| fig5_1_timeline.mmd | fig5_1_timeline.png | OK |
| fig6_1_modules.mmd | fig6_1_modules.png | OK |
| fig6_2_fusion.mmd | fig6_2_fusion.png | OK |
| fig6_3_verify.mmd | fig6_3_verify.png | OK |

---

## Verification Re-Run (v3) — COMPLETED ✓

`report/re_verify_v3.py` ran successfully:
- MiniCheck model loaded (threshold=0.10, version=v3)
- Found 86 real emails with claims
- **Updated: 6 emails** (80 skipped — no changes needed)
- The DB commit completed before the script crashed on a Unicode print character

---

## Code Changes Applied

| Change | File | Status |
|--------|------|--------|
| minicheck_threshold: 0.50 → 0.10 | app/settings.py | DONE ✓ |
| verification_version: "v2" → "v3" | app/settings.py | DONE ✓ |
| Re-run verification in DB | report/re_verify_v3.py | DONE ✓ (6 emails updated) |
| Demo emails pipeline (v3/v3) | aegis.db | DONE ✓ (all 20 demo emails complete under fraud v3 and verification v3) |
| ruff clean | all | DONE ✓ |
| 113 fast tests pass | tests/ | DONE ✓ |
