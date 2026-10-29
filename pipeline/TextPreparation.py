"""Text preparation: what exactly gets embedded for a plugin.

The embedded text is derived from the fields a user would search in: name,
description, about, tags and a size capped readme excerpt. Repetition is a
weighting device for static token embeddings: the name and the tags appear
twice and three times respectively, so they dominate the mean pooling.

This module must import neither qgis nor Qt; it is shared with the plugin.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.PluginCatalogue import PluginRecord  # noqa: E402

NAME_REPEATS = 2
TAGS_REPEATS = 3
DESCRIPTION_REPEATS = 1
ABOUT_REPEATS = 1
README_EXCERPT_CHARS = 4000

_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_EMPHASIS = re.compile(r"([*_]{1,3})")
_HTML_TAG = re.compile(r"<[^>]+>")
_CODE_BLOCK = re.compile(r"```[a-zA-Z0-9+-]*[^\n]*\n(?:.*?\n)?``` ?", re.DOTALL)
_UNCLOSED_CODE_BLOCK = re.compile(r"```[a-zA-Z0-9+-]*[^\n]*\n.*\Z", re.DOTALL)


def preparePluginText(record: PluginRecord, readmeText: str | None) -> str:
    """Return the text whose embedding represents the plugin."""
    parts: list[str] = []
    parts.extend([record.name] * NAME_REPEATS)
    if record.description:
        parts.extend([record.description] * DESCRIPTION_REPEATS)
    if record.about:
        parts.extend([record.about] * ABOUT_REPEATS)
    if record.tags:
        tagText = " ".join(record.tags)
        parts.extend([tagText] * TAGS_REPEATS)
    if readmeText:
        parts.append(stripMarkdownNoise(readmeText)[:README_EXCERPT_CHARS])
    return "\n".join(part for part in parts if part)


def stripMarkdownNoise(readmeText: str) -> str:
    """Remove the most noise prone markdown constructs, keep the words."""
    text = _CODE_BLOCK.sub(" ", readmeText)
    text = _UNCLOSED_CODE_BLOCK.sub(" ", text)
    text = _MARKDOWN_IMAGE.sub(" ", text)
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = _MARKDOWN_EMPHASIS.sub("", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
