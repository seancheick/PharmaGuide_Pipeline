#!/usr/bin/env python3
"""Text extraction helpers for PubMed E-utilities XML.

Deliberately stdlib-only so every PubMed consumer can share one implementation
without pulling in HTTP machinery or ``env_loader``'s ``.env`` side effect.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


def clean_text(text: str | None) -> str:
    """Collapse PubMed's XML indentation whitespace into single spaces."""
    if not text:
        return ""
    return " ".join(text.split())


def element_text(node: ET.Element | None) -> str:
    """Full text of an element, including text after inline markup children.

    ``findtext()`` and ``node.text`` return only the text *before* the first
    child element. PubMed wraps species names in ``<i>`` and trademarks in
    ``<sup>``, so those accessors silently truncate titles and abstracts --
    ``<ArticleTitle>A Magtein<sup>(R)</sup>, ...</ArticleTitle>`` yields just
    "A Magtein". Route every PubMed prose field through this helper.
    """
    if node is None:
        return ""
    return clean_text("".join(node.itertext()))


__all__ = ["clean_text", "element_text"]
