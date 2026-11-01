"""Real-model verification test using lytang/MiniCheck-RoBERTa-Large.

Marked as @pytest.mark.slow so it does not slow down normal fast test runs.
Run explicitly with: uv run pytest tests/test_verify_real.py -v
"""

from __future__ import annotations

import os

# Enforce offline mode and disable thread parallelism
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import os

# Enforce offline mode and disable thread parallelism
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import pytest

from app.verify.minicheck_verifier import MiniCheckVerifier


@pytest.mark.slow
def test_real_minicheck_model_three_pairs():
    """Verify real MiniCheck model on 3 hand-picked pairs: 1 supported, 2 unsupported (contradiction + trap)."""
    verifier = MiniCheckVerifier(model_name="roberta-large")
    assert verifier.is_available() is True, "MiniCheck model should be available from local cache"

    # Pair 1: Clearly supported
    doc1 = "[1] The SPF authentication check for sender alice@company.com passed successfully."
    claim1 = "The sender passed SPF authentication."
    res1 = verifier.verify_single_claim(claim1, [doc1], threshold=0.5)

    assert res1["label"] == "supported"
    assert res1["confidence"] >= 0.5
    assert res1["evidence_index"] == 1

    # Pair 2: Contradiction (unsupported)
    doc2 = "[1] The SPF authentication check for sender alice@company.com passed successfully."
    claim2 = "The SPF check for alice@company.com failed with hard fail."
    res2 = verifier.verify_single_claim(claim2, [doc2], threshold=0.5)

    assert res2["label"] == "unsupported"
    assert res2["confidence"] < 0.5

    # Pair 3: Ungrounded hallucination trap (unsupported)
    doc3 = "[1] Sprint planning meeting is scheduled for tomorrow at 10 AM in Conference Room B."
    claim3 = "alice@company.com instructed employees to send fifty thousand dollars via Western Union."
    res3 = verifier.verify_single_claim(claim3, [doc3], threshold=0.5)

    assert res3["label"] == "unsupported"
    assert res3["confidence"] < 0.5

