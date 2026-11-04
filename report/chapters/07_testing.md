# CHAPTER 7: SOFTWARE TESTING

## 7.1 TYPE OF TESTING

Software testing for AegisRAG was conducted at three levels: unit testing, integration testing, and manual system testing. This staged approach aligns with the incremental, evaluation-driven development methodology described in Sections 1.5 and 3.6. The testing strategy was designed with two priorities: first, every core algorithmic module must be independently verifiable without requiring API keys or network access; second, the complete HTTP interface must be verified end-to-end to ensure that the JSON and UI layers correctly expose the underlying pipeline.

### 7.1.1 Unit Testing

Unit tests verify the behaviour of individual functions and classes in isolation. The project uses the pytest framework. All unit tests are collected under the `tests/` directory. Running `pytest -m "not slow"` collects 114 tests and executes 113 fast tests; one test in `tests/test_verify_real.py` is marked with the `@pytest.mark.slow` decorator because it loads the MiniCheck RoBERTa-Large model and requires substantial memory. The fast suite runs without any API keys or network access, using the built-in demo emails and monkeypatched dependencies.

The test runner is invoked as follows:

    uv run pytest -m "not slow" -q

All 113 fast tests pass. The test suite is organised into one file per application module, so failures are immediately localised to a single module. This structure also makes it straightforward to add new tests as the pipeline evolves.

Each test file uses the demo email fixtures defined in `app/ingest/demo_emails.py` rather than live Gmail data. Gemini API calls are monkeypatched to return deterministic responses. The MiniCheck model is tested only in the slow suite; the fast suite tests the verifier interface by mocking the model. This design ensures that the fast suite runs without any external dependencies and without loading any large neural network models.

### 7.1.2 Static Analysis

Static analysis is performed with Ruff, the Python linter and formatter. Running `uv run ruff check app tests` reports zero violations. Ruff checks are equivalent to Flake8, isort, and a subset of pylint rules. The configuration is stored in `pyproject.toml`. Enforcing a clean Ruff check as part of the development workflow prevents common bugs such as undefined variables, unused imports, and inconsistent whitespace that can obscure logic errors during a viva or code review.

### 7.1.3 Integration Testing

Integration tests verify that multiple modules work together correctly through the application's HTTP interface. The files `tests/test_api.py` and `tests/test_ui.py` use pytest with the FastAPI `TestClient` to issue real HTTP requests and assert on status codes, JSON structure, and HTML content. These tests exercise the complete request-response cycle including database reads and demo-email handling.

The JSON API tests (7 tests in `test_api.py`) verify every endpoint defined in `app/api/`: the email list endpoint, the email detail endpoint, the open-email POST endpoint, and the settings endpoint. Each test checks both the HTTP status code and the structure of the returned JSON body. The UI tests (12 tests in `test_ui.py`) verify that all five tabs (Priority, Previous Messages, Feed, Flagged, Settings) return HTTP 200 and contain the expected HTML landmarks. HTMX panel endpoints are also tested to ensure that lazy-loaded content is rendered correctly on the first expansion of an email row.

A deliberate design decision separates concerns between the JSON API and the UI routes. The JSON API is tested for correctness of data (field names, types, values) and the UI routes are tested for correctness of structure (presence of expected HTML elements). This separation keeps the tests readable and ensures that a change to the HTML template does not require modifying the API tests.

### 7.1.4 Manual and Demo-Mode Testing

Manual testing was performed by running the full application stack (`uv run uvicorn app.main:app --reload --reload-dir app`) and exercising every UI tab and HTMX panel with the twenty built-in demo emails. Each demo email carries realistic Authentication-Results headers and a set of pre-computed placeholder scores. The Priority, Flagged, Feed, and Previous Messages tabs were verified to display the correct subsets, row colours, badges, and collapsible panels.

The manual test procedure for each UI component followed a fixed checklist:
- Priority tab: confirms unread emails are displayed sorted by priority score, highest first; the "N flagged" banner appears when fraudulent emails are present; newsletters are excluded.
- Previous Messages tab: confirms opened emails (those with a non-null `opened_at` value in the DB) are shown, sorted by date descending.
- Feed tab: confirms that only emails bearing the `List-Unsubscribe` header or a `CATEGORY_PROMOTIONS` / `CATEGORY_UPDATES` Gmail label are shown.
- Flagged tab: confirms that only emails with a fraud confidence at or above the threshold appear, sorted by fraud confidence descending.
- Email expansion: confirms that the HTMX panel loads on the first click, the inner tabs (Summary, Verified Explanation, Detection Layers, Headers, Body) render correctly, and the `opened_at` field is set after expansion.

The application was also tested against a real Gmail inbox containing 86 emails (fraud\_version v3). Of these, 2 were flagged above the fraud threshold (0.50) — both were deliberate test messages sent by the authors. Zero emails fell in the suspicious range (0.30–0.50). The Priority tab correctly displayed unread emails sorted by priority score, and the Feed tab correctly identified the newsletter emails in the inbox.

### 7.1.5 Slow and Model Tests

`tests/test_verify_real.py` contains one slow integration test that loads the MiniCheck verifier, runs it on a sample of real email claims from the SQLite database, and asserts that the returned labels are one of {supported, unsupported}. This test is excluded from the fast suite and is run separately:

    uv run pytest tests/test_verify_real.py -v

The slow test serves as an end-to-end validation that the verifier module correctly interfaces with the MiniCheck model, that the `verify_claims_list` method accepts the expected input format, and that the model's output is properly mapped to the application's two-label schema.

### 7.1.6 Regression Testing

Regressions were detected and fixed at several points during development. The most significant regressions arose from changes to the SQLite schema (adding columns without migrations), changes to the Gemini client caching logic (altering the prompt\_version key), and changes to the verification threshold. After each such change, the full fast test suite was re-run to confirm that no existing functionality had regressed. The tests for `test_db.py`, `test_gemini_client.py`, and `test_verify.py` are specifically designed to catch these categories of regression.

## 7.2 TEST CASES AND TEST RESULTS

Table 7.1 lists every test file, the module it covers, the number of tests it contains, and a brief description. Table 7.2 presents representative test cases with inputs, expected outputs, actual outputs, and pass/fail status.

**Table 7.1: Test File Summary (pytest --collect-only)**

| Test File | Module Covered | Tests | Description |
|---|---|---|---|
| test_normalizer.py | ingest/normalizer | 12 | Email normalisation: headers, body text, link extraction, display-name parsing |
| test_phishing_url_heuristics.py | phishing/providers/url\_heuristics | 13 | URL-based signals: IP URLs, lookalike domains, shorteners, link-text mismatch |
| test_phishing_fusion.py | phishing/fusion | 10 | Weight normalisation, known-bad URL floor, unavailable-provider drop-and-renorm |
| test_phishing_categories.py | phishing/categories | 8 | Phishing-category taxonomy assigned to scored emails |
| test_ui.py | api/ui routes | 12 | HTML responses for all UI tabs and HTMX panel endpoints |
| test_api.py | api/json routes | 7 | JSON endpoints: email list, detail, open, settings |
| test_demo_emails.py | ingest/demo | 7 | Demo email content, labels, and score placeholders |
| test_phishing_sender_auth.py | phishing/providers/sender\_auth | 7 | SPF/DKIM/DMARC header parsing: pass, fail, none, missing |
| test_priority.py | priority/classifier | 6 | Rule score, Gemini score blending, threshold labels |
| test_explain.py | explain/generator | 6 | Explanation generation: evidence construction, prompt structure |
| test_phishing_bert.py | phishing/providers/bert | 4 | BERT phishing-model wrapper: output range, graceful unavailability |
| test_gemini_client.py | llm/client | 4 | Cache hit/miss, 429 retry logic, prompt-version keying |
| test_db.py | db/session, db/models | 4 | DB session lifecycle, schema creation, CRUD on Email model |
| test_demo_phishing.py | ingest/demo (phishing) | 4 | Demo phishing emails: fraud scores, header anomalies |
| test_verify.py | verify/verifier | 5 | Verifier availability check, claim-list API, label set |
| test_verify_real.py | verify/verifier (real model) | 1 (slow) | End-to-end MiniCheck run on live DB claims |
| **Total** | | **114** | **113 fast + 1 slow** |

**Table 7.2: Representative Test Cases**

| Test ID | Description | Input | Expected Output | Actual Output | Result |
|---|---|---|---|---|---|
| TC-01 | Normalise plain-text email | Raw RFC 5322 message string | Populated Email model with body\_text, sender, subject fields | Email model correctly populated | PASS |
| TC-02 | Detect IP-literal URL | URL "http://192.168.1.1/login" | is\_ip\_url=True, heuristic score contribution > 0 | is\_ip\_url=True, score incremented | PASS |
| TC-03 | Detect lookalike domain | Link target "paypa1-login.net" | lookalike flag raised | Flag present in feature dict | PASS |
| TC-04 | SPF fail scoring | Authentication-Results: spf=fail | sender\_auth score 0.80 | Score 0.80 | PASS |
| TC-05 | SPF pass scoring | Authentication-Results: spf=pass | sender\_auth score 0.0 | Score 0.0 | PASS |
| TC-06 | DMARC none raises signal | Authentication-Results: dmarc=none | dmarc\_none flag set | Flag set correctly | PASS |
| TC-07 | Fusion: known-bad URL floor | url\_heuristics flags known-bad URL | Fused score floored at 0.90 | Score 0.90 | PASS |
| TC-08 | Fusion: unavailable provider renorm | BERT unavailable | Weights for remaining providers renormalised to sum 1.0 | Weights sum to 1.0 | PASS |
| TC-09 | LLM cache hit | Same (gmail\_id, task\_type, prompt\_version) called twice | Second call returns cached result; Gemini API not invoked | Cached result returned, API call count unchanged | PASS |
| TC-10 | Priority label: High | Blended score 80 | label = "High" | label = "High" | PASS |
| TC-11 | Priority label: Medium | Blended score 50 | label = "Medium" | label = "Medium" | PASS |
| TC-12 | Priority label: Low | Blended score 20 | label = "Low" | label = "Low" | PASS |
| TC-13 | Demo email count | No API keys, DEMO\_MODE=1 | 20 demo emails in DB | 20 emails present | PASS |
| TC-14 | UI Priority tab returns HTML | GET /ui/ | HTTP 200, HTML with email rows | HTTP 200, correct HTML | PASS |
| TC-15 | POST open sets opened\_at | POST /api/emails/{id}/open | opened\_at field becomes non-null | opened\_at updated | PASS |
| TC-16 | Verify: claim label in valid set | Sample claim + evidence via MiniCheck | label in {"supported", "unsupported"} | label "supported" or "unsupported" | PASS |
| TC-17 | Verifier unavailable gracefully | MiniCheck not loaded | is\_available() returns False; no exception | Returns False | PASS |
| TC-18 | Feed tab shows newsletters only | GET /ui/feed | Emails with List-Unsubscribe or CATEGORY\_PROMOTIONS label only | Only newsletter emails shown | PASS |

All 113 fast test cases pass without API keys. The slow test (TC-16 variant using real DB data) passes when the MiniCheck model is present. The test suite provides confidence in the correctness of each module and ensures that the application can be set up and run by following the four-step procedure in the README without manual debugging.
