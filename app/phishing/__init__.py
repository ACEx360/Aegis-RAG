"""Phishing detection package (§7, §16, Stage 4)."""

from app.phishing.detector import detect_phishing_for_email
from app.phishing.fusion import FusionResult, fuse_phishing_layers

__all__ = [
    "FusionResult",
    "detect_phishing_for_email",
    "fuse_phishing_layers",
]

