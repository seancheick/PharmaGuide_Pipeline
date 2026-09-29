"""A plain alfalfa extract is not ZyloFresh.

BRAND_ZYLOFRESH (backed_clinical_studies.json, evidence level preclinical, no
human trials) carried the generic alias "alfalfa extract", so every alfalfa
extract collected the branded clinically-studied form credit through
`botanical_profile`'s alias-keyed brand set, since replaced by the enricher's brand check (BulkSupplements 253578: Formulation
20 of 20 with +3 "branded clinically studied" and full standardization). A
brand's aliases name the brand; the plant's own names stay on the botanical
and IQM alfalfa identities.
"""
import json
import logging
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data"


def _zylofresh():
    entries = json.loads((DATA / "backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    return next(e for e in entries if e.get("id") == "BRAND_ZYLOFRESH")


def test_zylofresh_aliases_name_only_the_brand():
    aliases = {a.lower() for a in _zylofresh().get("aliases") or []}
    assert "alfalfa extract" not in aliases
    assert "zylofresh" in aliases


def test_plain_alfalfa_extract_earns_no_branded_form_credit():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / "zylofresh_alias_253578_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    artifact = build_scored_artifact(enriched)
    formulation = artifact["_v4_module_breakdown"]["dimensions"]["formulation"]
    botanical = (formulation.get("metadata") or {}).get("botanical_formulation") or {}
    assert botanical.get("recognized_botanical_identity")  # still read as alfalfa
    assert "branded_clinically_studied_extract" not in botanical


def test_plain_alfalfa_keeps_its_own_identity():
    iqm = json.loads((DATA / "ingredient_quality_map.json").read_text())
    aliases = {a.lower() for form in iqm["alfalfa"]["forms"].values() for a in form.get("aliases") or []}
    assert "alfalfa extract" in aliases
