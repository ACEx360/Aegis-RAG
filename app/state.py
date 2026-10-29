"""Mutable runtime state that can differ from the initial .env values.

Why separate from settings.py: Settings is a frozen Pydantic model read once
at import time.  Runtime toggles (like switching to demo mode from the login
page) live here so the rest of the app has a single source of truth for
"what mode are we in right now?"
"""

from __future__ import annotations

from app.settings import settings


class _AppState:
    """Lightweight container for runtime-mutable state."""

    def __init__(self) -> None:
        self._demo_mode: bool = settings.demo_mode
        # Background Priority Analysis worker state (§Stage 3)
        self.analysis_running: bool = False
        self.analysis_interrupted: bool = False
        self.analysis_current: int = 0
        self.analysis_total: int = 0
        self.analysis_message: str = ""

    @property
    def demo_mode(self) -> bool:
        return self._demo_mode

    @demo_mode.setter
    def demo_mode(self, value: bool) -> None:
        self._demo_mode = value

    @property
    def mode(self) -> str:
        """Return 'demo' or 'real' — used for filtering and display."""
        return "demo" if self._demo_mode else "real"


app_state = _AppState()
