#!/usr/bin/env python3
"""Text extraction helpers for PubMed E-utilities XML.

Deliberately stdlib-only so every PubMed consumer can share one implementation
without pulling in HTTP machinery or ``env_loader``'s ``.env`` side effect.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import html
import re
import unicodedata


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


def _normalized_source_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text or "")).casefold()
    return text.translate(str.maketrans({"−": "-", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"'}))


def normalized_source_quote(text: str) -> str:
    """Ignore formatting whitespace, never dose decimals, signs or negation."""
    return re.sub(r"\s+", "", _normalized_source_text(text))


def source_quote_matches(quote: str, source: str) -> bool:
    normalized = normalized_source_quote(quote)
    if not normalized:
        return False
    text = _normalized_source_text(source)
    # A literal quote must not mine 32 mg out of 132 mg or 5 mg out of 3.5 mg.
    # Retain whitespace tolerance without weakening the numeric boundaries.
    # Keep the source's word/sentence boundaries: removing its spaces would
    # make "... weeks. 1.6 g ..." look like a decimal substring at the edge.
    pattern = r"\s*".join(re.escape(char) for char in normalized)
    if normalized[0].isdigit():
        pattern = r"(?<![0-9.+-])" + pattern
    if normalized[-1].isdigit():
        pattern += r"(?![0-9]|\.[0-9])"
    return re.search(pattern, text) is not None


def bound_pmc_text(raw: bytes, pmid: str) -> str:
    """Read the requested paper, not a similarly named PMC article or its refs.

    PMID must be the article's own front-matter identifier. Finding the PMID
    in its reference list does not bind the paper to the requested citation.
    """
    root = ET.fromstring(raw)
    identifiers = {element_text(node) for node in root.findall("./front/article-meta/article-id")
                   if node.get("pub-id-type") == "pmid"}
    if identifiers != {str(pmid)}:
        raise ValueError(f"PMC article PMID mismatch: expected {pmid}, got {sorted(identifiers)}")
    # JATS tables/paragraphs often have no literal whitespace between nodes.
    # Preserve their boundaries without splitting inline emphasis/superscripts.
    for node in root.iter():
        if node.tag in {"p", "title", "td", "th", "tr", "list-item"}:
            node.tail = " " + (node.tail or "")
    return " ".join(element_text(node) for node in (root.find("front"), root.find("body"), root.find("floats-group")))


__all__ = ["clean_text", "element_text", "normalized_source_quote", "source_quote_matches", "bound_pmc_text"]
