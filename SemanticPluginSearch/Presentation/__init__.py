"""Qt widgets for the semantic search window.

The views hold no business logic: they translate Qt events into controller
calls and controller updates into widget state, through the structural
SearchWindowView protocol.
"""
from __future__ import annotations

from .SearchDialog import SearchDialog

__all__ = ["SearchDialog"]
