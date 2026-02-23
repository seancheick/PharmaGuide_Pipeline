#!/usr/bin/env python3
"""
Guard tests for cross-database term contamination.

These checks enforce explicit routing policy boundaries so future JSON updates
cannot silently introduce overlaps between banned/harmful and scoring maps.
"""

import json
import re
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (text or "").lower())).strip()


def _load_json(name: str):
    return json.loads((DATA_DIR / name).read_text())


def _collect_iqm_terms(iqm: dict) -> set[str]:
    terms: set[str] = set()
    for key, entry in iqm.items():
        if key.startswith("_") or not isinstance(entry, dict):
            continue
        forms = entry.get("forms") or {}
        if not isinstance(forms, dict):
            continue
        for form_name, form_data in forms.items():
            names = [form_name]
            aliases = form_data.get("aliases") if isinstance(form_data, dict) else []
            if isinstance(aliases, list):
                names.extend(aliases)
            for n in names:
                nn = _norm(str(n))
                if nn:
                    terms.add(nn)
    return terms


def _collect_standard_alias_terms(entries: list[dict]) -> set[str]:
    terms: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        names = [entry.get("standard_name", "")]
        aliases = entry.get("aliases")
        if isinstance(aliases, list):
            names.extend(aliases)
        for n in names:
            nn = _norm(str(n))
            if nn:
                terms.add(nn)
    return terms


def _collect_allowlisted_harmful_iqm_terms() -> set[str]:
    allow = _load_json("cross_db_overlap_allowlist.json").get("allowed_overlaps", [])
    allowed = set()
    for row in allow:
        if not isinstance(row, dict):
            continue
        pairs = row.get("db_pairs") or []
        if "harmful:iqm" in pairs:
            term = _norm(str(row.get("term_normalized", "")))
            if term:
                allowed.add(term)
    return allowed


def test_banned_terms_do_not_overlap_scoring_or_identity_maps():
    banned = _load_json("banned_recalled_ingredients.json").get("banned_recalled_ingredients", [])
    iqm = _load_json("ingredient_quality_map.json")
    botanicals = _load_json("botanical_ingredients.json").get("botanical_ingredients", [])
    other = _load_json("other_ingredients.json").get("other_ingredients", [])

    banned_terms = _collect_standard_alias_terms(banned)
    iqm_terms = _collect_iqm_terms(iqm)
    botanical_terms = _collect_standard_alias_terms(botanicals)
    other_terms = _collect_standard_alias_terms(other)

    assert not (banned_terms & iqm_terms), "Banned terms overlap IQM terms."
    assert not (banned_terms & botanical_terms), "Banned terms overlap botanical terms."
    assert not (banned_terms & other_terms), "Banned terms overlap other-ingredients terms."


def test_harmful_iqm_overlap_is_explicitly_allowlisted():
    harmful = _load_json("harmful_additives.json").get("harmful_additives", [])
    iqm = _load_json("ingredient_quality_map.json")
    botanicals = _load_json("botanical_ingredients.json").get("botanical_ingredients", [])

    harmful_terms = _collect_standard_alias_terms(harmful)
    iqm_terms = _collect_iqm_terms(iqm)
    botanical_terms = _collect_standard_alias_terms(botanicals)
    allowlisted = _collect_allowlisted_harmful_iqm_terms()

    harmful_iqm_overlap = harmful_terms & iqm_terms
    unknown = harmful_iqm_overlap - allowlisted

    assert not (harmful_terms & botanical_terms), "Harmful additives overlap botanical map terms."
    assert not unknown, (
        "New harmful↔IQM overlap terms found without explicit allowlist review: "
        f"{sorted(unknown)}"
    )
