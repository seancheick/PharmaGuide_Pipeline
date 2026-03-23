import json
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"
BANNED_STATUS_CODES = {"banned", "not_lawful", "illegal", "adulterant"}


def load_entries():
    return json.loads(DATA_PATH.read_text())["harmful_additives"]


def test_match_rules_populated():
    for entry in load_entries():
        mr = entry.get("match_rules")
        assert mr, f"{entry['id']} missing match_rules"
        assert mr.get("match_mode"), f"{entry['id']} needs match_mode"
        assert entry.get("aliases"), f"{entry['id']} needs aliases"


def test_references_structured_exists():
    for entry in load_entries():
        refs = entry.get("references_structured") or []
        assert refs, f"{entry['id']} missing references_structured"


def test_review_metadata():
    for entry in load_entries():
        review = entry.get("review")
        assert review, f"{entry['id']} missing review"
        assert review.get("status"), f"{entry['id']} review missing status"
        assert review.get("reviewed_by"), f"{entry['id']} review missing reviewer"


def test_jurisdiction_status_codes():
    allowed = {"approved", "permitted_with_limit", "restricted", "warning_issued", "banned", "not_evaluated"}
    for entry in load_entries():
        codes = []
        for status in entry.get("jurisdictional_statuses", []):
            code = status.get("status_code")
            assert code, f"{entry['id']} status missing code"
            assert code in allowed, f"{entry['id']} uses disallowed code {code}"
            codes.append(code)
        # Entry banned in ALL jurisdictions should be in banned_recalled, not here
        if codes:
            assert not all(c == "banned" for c in codes), (
                f"{entry['id']} is banned in all jurisdictions — migrate to banned_recalled_ingredients.json"
            )


def test_cui_uniqueness():
    seen = {}
    for entry in load_entries():
        cui = entry.get("cui")
        if not cui:
            continue
        assert cui not in seen, f"{entry['id']} shares CUI {cui} with {seen[cui]}"
        seen[cui] = entry["id"]


def test_entity_relationships_present():
    relationships = {
        "ADD_CALCIUM_ALUMINUM_PHOSPHATE": "ADD_SODIUM_ALUMINUM_PHOSPHATE",
    }
    entries = {e["id"]: e for e in load_entries()}
    for eid, target in relationships.items():
        entry = entries.get(eid)
        assert entry, f"{eid} missing from dataset"
        rels = entry.get("entity_relationships", [])
        assert any(r.get("target_id") == target for r in rels), f"{eid} missing relation to {target}"


def test_all_entries_have_aliases():
    """Every harmful additive must have aliases for matching."""
    missing = []
    for entry in load_entries():
        if not entry.get("aliases"):
            missing.append(entry["id"])
    assert missing == [], f"Entries missing aliases: {missing}"


def test_external_ids_key_casing():
    """external_ids keys must be lowercase."""
    for entry in load_entries():
        ext = entry.get("external_ids")
        if not ext:
            continue
        for key in ext:
            assert key == key.lower(), f"{entry['id']} has non-lowercase external_ids key '{key}'"


def test_references_structured_schema():
    """All references_structured entries must have the canonical field set."""
    required = {"type", "authority", "title", "citation", "url", "published_date", "evidence_grade", "supports_claims"}
    for entry in load_entries():
        for i, ref in enumerate(entry.get("references_structured", [])):
            missing = required - set(ref.keys())
            assert not missing, f"{entry['id']} ref[{i}] missing fields: {missing}"
            extra = set(ref.keys()) - required
            assert not extra, f"{entry['id']} ref[{i}] has extra fields: {extra}"


def test_severity_levels_valid():
    """severity_level must be high, moderate, or low — no critical (use banned_recalled for that)."""
    valid = {"high", "moderate", "low"}
    for entry in load_entries():
        sev = entry.get("severity_level")
        assert sev, f"{entry['id']} missing severity_level"
        assert sev in valid, f"{entry['id']} has invalid severity_level '{sev}' (valid: {valid})"


def test_no_banned_prefix_in_ids():
    """IDs should use ADD_ prefix, not BANNED_ADD_ (those belong in banned_recalled)."""
    for entry in load_entries():
        assert not entry["id"].startswith("BANNED_"), (
            f"{entry['id']} has BANNED_ prefix — should use ADD_ or migrate to banned_recalled"
        )


def test_no_top_level_cui():
    """CUI should be top-level 'cui', not inside external_ids."""
    for entry in load_entries():
        assert "CUI" not in entry, f"{entry['id']} has deprecated top-level CUI field"
        ext = entry.get("external_ids", {})
        assert "umls_cui" not in ext, f"{entry['id']} has umls_cui in external_ids — use top-level 'cui'"


def test_no_dead_weight_fields():
    """Removed fields should not be present."""
    for entry in load_entries():
        assert "exposure_context" not in entry, f"{entry['id']} has removed field exposure_context"
        assert "class_tags" not in entry, f"{entry['id']} has removed field class_tags"
        mr = entry.get("match_rules", {})
        assert "label_tokens" not in mr, f"{entry['id']} has removed field match_rules.label_tokens"
        assert "regex" not in mr, f"{entry['id']} has removed field match_rules.regex"
