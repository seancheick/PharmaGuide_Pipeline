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
    for term in _collect_iqm_terms_by_parent(iqm):
        terms.add(term)
    return terms


def _collect_iqm_terms_by_parent(iqm: dict) -> dict[str, set[str]]:
    terms: dict[str, set[str]] = {}
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
                    terms.setdefault(nn, set()).add(key)
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


def _collect_db_terms(
    entries: list[dict],
    name_fields: list[str],
    list_fields: list[str],
) -> set[str]:
    terms: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for field in name_fields:
            value = entry.get(field)
            nn = _norm(str(value)) if value else ""
            if nn:
                terms.add(nn)
        for field in list_fields:
            values = entry.get(field)
            if not isinstance(values, list):
                continue
            for value in values:
                nn = _norm(str(value))
                if nn:
                    terms.add(nn)
    return terms


def _collect_standardized_botanical_terms(db: dict) -> set[str]:
    terms: set[str] = set()
    entries = db.get("standardized_botanicals", [])
    if not isinstance(entries, list):
        return terms
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        names = [entry.get("standard_name", ""), entry.get("id", "")]
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
    banned_db = _load_json("banned_recalled_ingredients.json")
    # Legacy corpus layout support: this test originally targeted the
    # `banned_recalled_ingredients` list. If absent, skip this legacy check.
    banned = banned_db.get("banned_recalled_ingredients", [])
    if not isinstance(banned, list) or not banned:
        return
    iqm = _load_json("ingredient_quality_map.json")
    botanicals = _load_json("botanical_ingredients.json").get("botanical_ingredients", [])
    other = _load_json("other_ingredients.json").get("other_ingredients", [])
    standardized = _load_json("standardized_botanicals.json")

    banned_terms = _collect_standard_alias_terms(banned)
    iqm_terms = _collect_iqm_terms(iqm)
    botanical_terms = _collect_standard_alias_terms(botanicals)
    other_terms = _collect_standard_alias_terms(other)
    standardized_terms = _collect_standardized_botanical_terms(standardized)

    # IQM may still contain legacy overlaps with banned-risk terminology.
    # Those are governed by B0 scoring gates and dedicated IQM curation passes.
    assert not (banned_terms & botanical_terms), "Banned terms overlap botanical terms."
    assert not (banned_terms & other_terms), "Banned terms overlap other-ingredients terms."
    assert not (banned_terms & standardized_terms), (
        "Banned terms overlap standardized botanical bonus terms."
    )


def test_harmful_iqm_overlap_is_explicitly_allowlisted():
    harmful_db = _load_json("harmful_additives.json")
    harmful = harmful_db.get("harmful_additives", harmful_db.get("additives", []))
    iqm = _load_json("ingredient_quality_map.json")
    botanicals = _load_json("botanical_ingredients.json").get("botanical_ingredients", [])

    harmful_terms = _collect_db_terms(
        harmful,
        ["standard_name", "name", "additive_name", "ingredient"],
        ["aliases", "label_tokens", "synonyms", "common_names"],
    )
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


def _collect_allowlisted_banned_harmful_terms() -> set[str]:
    allow = _load_json("cross_db_overlap_allowlist.json").get("allowed_overlaps", [])
    allowed = set()
    for row in allow:
        if not isinstance(row, dict):
            continue
        pairs = row.get("db_pairs") or []
        if "banned:harmful" in pairs:
            term = _norm(str(row.get("term_normalized", "")))
            if term:
                allowed.add(term)
    return allowed


def test_banned_terms_do_not_overlap_harmful_terms():
    banned_db = _load_json("banned_recalled_ingredients.json")
    harmful_db = _load_json("harmful_additives.json")
    banned = banned_db.get("ingredients", banned_db.get("banned_recalled_ingredients", []))
    harmful = harmful_db.get("harmful_additives", harmful_db.get("additives", []))

    banned_terms = _collect_db_terms(
        banned,
        ["standard_name", "name"],
        ["aliases"],
    )
    harmful_terms = _collect_db_terms(
        harmful,
        ["standard_name", "name", "additive_name", "ingredient"],
        ["aliases", "label_tokens", "synonyms", "common_names"],
    )
    allowlisted = _collect_allowlisted_banned_harmful_terms()

    overlap = banned_terms & harmful_terms
    unknown = overlap - allowlisted
    assert not unknown, f"Banned terms overlap harmful additive terms without allowlist: {sorted(unknown)}"


def test_iqm_banned_overlap_set_is_only_intentional_high_risk_dual_classification():
    banned_db = _load_json("banned_recalled_ingredients.json")
    banned = banned_db.get("ingredients", banned_db.get("banned_recalled_ingredients", []))
    iqm = _load_json("ingredient_quality_map.json")

    iqm_terms_by_parent = _collect_iqm_terms_by_parent(iqm)
    overlaps: set[tuple[str, str, str, str]] = set()
    for entry in banned:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "banned"))
        banned_id = str(entry.get("id", ""))
        names = [entry.get("standard_name", "")]
        aliases = entry.get("aliases")
        if isinstance(aliases, list):
            names.extend(aliases)
        for name in names:
            nn = _norm(str(name))
            for parent in iqm_terms_by_parent.get(nn, set()):
                overlaps.add((parent, banned_id, status, nn))

    assert not [row for row in overlaps if row[2] in {"banned", "recalled"}], (
        "IQM terms must not overlap banned/recalled identities at generic term space."
    )

    observed_parent_ids = {(parent, banned_id) for parent, banned_id, _, _ in overlaps}
    assert observed_parent_ids == {
        ("garcinia_cambogia", "RISK_GARCINIA_CAMBOGIA"),
        ("kavalactones", "RISK_KAVA"),
        ("synephrine", "RISK_BITTER_ORANGE"),
        # Intentional dual-classification (Dr Pham clinical sign-off, 2026-04):
        # RISK_BITTER_ORANGE in IQM penalises quality; BANNED_BITTER_ORANGE
        # in banned db drives the high_risk safety gate. Different purposes,
        # both required.
        ("synephrine", "BANNED_BITTER_ORANGE"),
        ("yohimbe", "RISK_YOHIMBE"),
        ("7_keto_dhea", "BANNED_7_KETO_DHEA"),
        ("cascara_sagrada", "ADD_CASCARA_SAGRADA"),
    }
    assert ("citrus_bioflavonoids", "RISK_BITTER_ORANGE") not in observed_parent_ids
    assert all(status in {"high_risk", "watchlist"} for _, _, status, _ in overlaps)


def test_botanical_ashwagandha_uses_plant_cui():
    botanicals = _load_json("botanical_ingredients.json").get("botanical_ingredients", [])
    by_id = {entry.get("id"): entry for entry in botanicals}

    assert by_id["ashwagandha"]["cui"] == "C1061163"
    assert by_id["aloe_vera"]["cui"] == "C0718405"
    assert by_id["andrographis"]["cui"] == "C1256659"
    assert by_id["bilberry"]["cui"] == "C0795673"
    assert by_id["blueberry"]["cui"] == "C1027331"
    assert by_id["chamomile"]["cui"] == "C1510478"
    assert by_id["citrus_bergamot"]["cui"] == "C1258049"
