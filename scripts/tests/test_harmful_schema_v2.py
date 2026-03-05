import json
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"
BANNED_STATUS_CODES = {"banned", "restricted", "not_lawful", "illegal", "adulterant"}


def load_entries():
    return json.loads(DATA_PATH.read_text())["harmful_additives"]


def test_match_rules_populated():
    for entry in load_entries():
        mr = entry.get("match_rules")
        assert mr, f"{entry['id']} missing match_rules"
        assert mr.get("match_mode"), f"{entry['id']} needs match_mode"
        # label_tokens optional for entries migrated from banned_recalled in v5.0
        if not mr.get("label_tokens"):
            assert entry.get("aliases"), f"{entry['id']} needs label_tokens or aliases"


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
    allowed = {"allowed", "monitored", "warning_required"}
    for entry in load_entries():
        for status in entry.get("jurisdictional_statuses", []):
            code = status.get("status_code")
            assert code, f"{entry['id']} status missing code"
            assert code in allowed, f"{entry['id']} uses disallowed code {code}"
            assert code not in BANNED_STATUS_CODES, f"{entry['id']} flagged as banned ({code})"


def test_cui_uniqueness():
    seen = {}
    for entry in load_entries():
        cui = entry.get("external_ids", {}).get("umls_cui")
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


def test_all_entries_have_match_tokens():
    """Every harmful additive with match_mode requiring tokens must have label_tokens or aliases."""
    missing = []
    for entry in load_entries():
        mr = entry.get("match_rules", {})
        mode = mr.get("match_mode", "")
        # Entries that rely on token matching need label_tokens or aliases
        if mode in ("token", "token_any", "token_all", "exact"):
            has_tokens = bool(mr.get("label_tokens"))
            has_aliases = bool(entry.get("aliases"))
            if not has_tokens and not has_aliases:
                missing.append(entry["id"])
    assert missing == [], f"Entries missing match tokens or aliases: {missing}"
