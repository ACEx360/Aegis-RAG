"""Base dataclass and protocols for phishing detection providers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LayerResult:
    """Standard contract returned by each phishing detection layer (§7)."""

    name: str
    score: float
    reason: str
    evidence: list[str] = field(default_factory=list)
    available: bool = True
    has_strong_signal: bool = False
    is_fully_clean: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert LayerResult to dictionary representation."""
        return asdict(self)

