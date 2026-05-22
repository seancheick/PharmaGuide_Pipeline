import argparse
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / "scripts" / "audit_source_of_truth_contract.py"
MATRIX_PATH = REPO_ROOT / "scripts" / "contracts" / "source_of_truth_matrix.json"


spec = importlib.util.spec_from_file_location("audit_source_of_truth_contract", AUDIT_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_source_of_truth_matrix_is_complete():
    args = argparse.Namespace(matrix=str(MATRIX_PATH), strict_release=True)
    findings = audit.audit_matrix(args)
    assert findings == []


def test_source_of_truth_matrix_declares_enrichment_contract_concepts():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    required = {
        "ingredient_identity_resolution",
        "ingredient_quality_data_contract",
        "taxonomy_input_contract",
        "enriched_active_safety_contract",
        "enriched_inactive_safety_contract",
        "interaction_profile_contract",
        "enrichment_fallback_policy",
        "display_ingredient_contract",
    }
    assert required.issubset(set(matrix["required_concepts"]))
    assert required.issubset({concept["concept_id"] for concept in matrix["concepts"]})


def test_source_of_truth_matrix_rejects_dev_only_fallback_in_strict_release(tmp_path):
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    matrix["concepts"][0]["fallback_class"] = "dev_only_missing_vocab"
    path = tmp_path / "matrix.json"
    write_json(path, matrix)

    args = argparse.Namespace(matrix=str(path), strict_release=True)
    findings = audit.audit_matrix(args)

    assert "MATRIX_DEV_FALLBACK_RELEASE" in {finding.code for finding in findings}


def test_cleaner_iqd_contract_blocks_ineligible_inactive_and_display_roles(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "canary",
                "ingredient_quality_data": {
                    "ingredients": [
                        {
                            "name": "Proprietary Blend",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "blend_header_total",
                            "score_eligible_by_cleaner": False,
                            "dose_class": "blend_total_weight",
                        }
                    ],
                    "ingredients_scorable": [
                        {
                            "name": "Proprietary Blend",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "blend_header_total",
                            "score_eligible_by_cleaner": False,
                            "dose_class": "blend_total_weight",
                        },
                        {
                            "name": "Leucine",
                            "source_section": "inactive",
                            "raw_source_path": "otheringredients[2]",
                            "cleaner_row_role": "inactive",
                            "score_eligible_by_cleaner": False,
                            "dose_class": "none",
                        },
                    ],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_cleaner(args)}

    assert "IQD_SCORABLE_NOT_CLEANER_ELIGIBLE" in codes
    assert "IQD_BLOCKED_ROLE_SCORABLE" in codes
    assert "IQD_INACTIVE_PROMOTED" in codes


def test_cleaner_contract_rejects_source_rows_missing_cleaner_fields(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "missing-cleaner-source-contract",
                "activeIngredients": [{"name": "Vitamin C", "raw_source_path": "ingredientRows[0]"}],
                "ingredient_quality_data": {
                    "ingredients": [],
                    "ingredients_scorable": [],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_cleaner(args)}

    assert "CLEANER_SOURCE_ROW_FIELD_MISSING" in codes


def test_enrichment_contract_blocks_recognized_rows_in_scorable_and_iqd_fallback(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "enrichment-contract-canary",
                "supplement_taxonomy": {
                    "primary_type": "omega_3",
                    "classification_input_source": "ingredient_quality_data.ingredients_fallback",
                },
                "iqd_contract_diagnostics": {"iqd_ingredients_fallback_used": True},
                "ingredient_quality_data": {
                    "ingredients": [
                        {
                            "name": "Sunflower Oil",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "active_scorable",
                            "score_eligible_by_cleaner": True,
                            "score_exclusion_reason": None,
                            "dose_class": "therapeutic_mass",
                            "raw_taxonomy": {},
                            "canonical_id": "sunflower_oil",
                            "canonical_source_db": "other_ingredients",
                            "normalized_key": "sunflower_oil",
                            "match_tier": None,
                            "matched_alias": None,
                            "matched_target": None,
                            "identity_confidence": 1.0,
                            "identity_decision_reason": "recognized_non_scorable",
                            "mapped": True,
                            "mapped_identity": True,
                            "scoreable_identity": False,
                            "role_classification": "recognized_non_scorable",
                            "recognition_source": "other_ingredients",
                            "recognition_type": "carrier",
                            "recognition_reason": "recognized_non_scorable",
                            "form_id": None,
                            "form_source": None,
                            "form_unmapped": False,
                            "delivers_markers": [],
                        }
                    ],
                    "ingredients_scorable": [
                        {
                            "name": "Sunflower Oil",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "active_scorable",
                            "score_eligible_by_cleaner": True,
                            "score_exclusion_reason": None,
                            "dose_class": "therapeutic_mass",
                            "raw_taxonomy": {},
                            "canonical_id": "sunflower_oil",
                            "canonical_source_db": "other_ingredients",
                            "normalized_key": "sunflower_oil",
                            "match_tier": None,
                            "matched_alias": None,
                            "matched_target": None,
                            "identity_confidence": 1.0,
                            "identity_decision_reason": "recognized_non_scorable",
                            "mapped": True,
                            "mapped_identity": True,
                            "scoreable_identity": False,
                            "role_classification": "recognized_non_scorable",
                            "recognition_source": "other_ingredients",
                            "recognition_type": "carrier",
                            "recognition_reason": "recognized_non_scorable",
                            "form_id": None,
                            "form_source": None,
                            "form_unmapped": False,
                            "delivers_markers": [],
                        }
                    ],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_enrichment(args)}

    assert "ENRICHMENT_RECOGNIZED_IN_SCORABLE" in codes
    assert "ENRICHMENT_SCORABLE_NOT_SCOREABLE_IDENTITY" in codes
    assert "ENRICHMENT_SCORABLE_ROLE_NOT_ACTIVE" in codes
    assert "ENRICHMENT_FALLBACK_DIAGNOSTICS_MISSING" in codes
    assert "ENRICHMENT_TAXONOMY_USED_IQD_FALLBACK" in codes
    assert "ENRICHMENT_SCORING_USED_IQD_FALLBACK" in codes


def test_enrichment_contract_rejects_old_batch_cleaner_contract_defaults(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "old-batch-cleaner-default-canary",
                "ingredient_quality_data": {
                    "ingredients": [
                        {
                            "name": "Vitamin C",
                            "source_section": "active",
                            "raw_source_path": "activeIngredients",
                            "cleaner_row_role": "active_scorable",
                            "score_eligible_by_cleaner": True,
                            "score_exclusion_reason": None,
                            "dose_class": "therapeutic_mass",
                            "raw_taxonomy": {},
                            "canonical_id": "vitamin_c",
                            "canonical_source_db": "ingredient_quality_map",
                            "normalized_key": "vitamin_c",
                            "match_tier": "exact",
                            "matched_alias": None,
                            "matched_target": "Vitamin C",
                            "identity_confidence": 1.0,
                            "identity_decision_reason": "quality_map_match",
                            "mapped": True,
                            "mapped_identity": True,
                            "scoreable_identity": True,
                            "role_classification": "active_scorable",
                            "recognition_source": None,
                            "recognition_type": None,
                            "recognition_reason": None,
                            "form_id": None,
                            "form_source": None,
                            "form_unmapped": False,
                            "delivers_markers": [],
                            "cleaner_contract_fallback_used": True,
                            "cleaner_contract_missing_fields": ["source_section"],
                            "fallback_class": "old_batch_compatibility",
                            "fallback_reason": "missing_cleaner_contract_fields",
                        }
                    ],
                    "ingredients_scorable": [],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_enrichment(args)}

    assert "ENRICHMENT_CLEANER_CONTRACT_FALLBACK_USED" in codes


def test_clinical_drift_gates_catch_known_failure_shapes(tmp_path):
    product_file = tmp_path / "products.json"
    write_json(
        product_file,
        [
            {
                "id": "chromium",
                "name": "Multivitamin with Chromium",
                "banned_substances": {"substances": [{"rule_id": "HM_CHROMIUM_HEXAVALENT"}]},
                "ingredient_quality_data": {
                    "ingredients_scorable": [
                        {
                            "name": "Chromium",
                            "canonical_id": "chromium",
                            "score_eligible_by_cleaner": True,
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                        }
                    ]
                },
            },
            {
                "id": "omega-zyme",
                "name": "Omega-Zyme Enzyme Blend",
                "supplement_taxonomy": {"primary_type": "omega_3"},
                "ingredient_quality_data": {"ingredients_scorable": [{"name": "Protease", "canonical_id": "protease"}]},
            },
            {
                "id": "pm",
                "name": "Liver Cleanser PM",
                "supplement_taxonomy": {"primary_type": "sleep_support"},
                "ingredient_quality_data": {"ingredients_scorable": [{"name": "Milk Thistle", "canonical_id": "milk_thistle"}]},
            },
            {
                "id": "enzyme",
                "name": "Natto-Serra Serrapeptase 120000 SPU",
                "ingredient_quality_data": {
                    "ingredients": [{"name": "Serrapeptase", "unit": "SPU"}],
                    "ingredients_scorable": [{"name": "Calcium", "canonical_id": "calcium", "quantity": 20, "dose_class": "therapeutic_mass"}],
                },
            },
            {
                "id": "softgel",
                "name": "Softgel Product",
                "form_factor": "Softgel Capsule",
                "form_factor_canonical": "capsule",
                "ingredient_quality_data": {"ingredients_scorable": []},
            },
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_clinical(args)}

    assert "GENERIC_CHROMIUM_CRVI" in codes
    assert "PRODUCT_NAME_ONLY_OMEGA3" in codes
    assert "PM_ONLY_SLEEP_SUPPORT" in codes
    assert "ENZYME_ACTIVITY_NOT_DOSE_EVIDENCE" in codes
    assert "FORM_FACTOR_CANONICAL_NOT_SOFTGEL" in codes


def test_shadow_diff_requires_approval_for_taxonomy_verdict_safety_or_coverage_shift(tmp_path):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    write_json(
        old_dir / "products.json",
        [
            {
                "id": "shadow",
                "supplement_taxonomy": {"primary_type": "multivitamin"},
                "verdict": "SAFE",
                "banned_substances": {"substances": []},
                "mapped_coverage": 1.0,
            }
        ],
    )
    write_json(
        new_dir / "products.json",
        [
            {
                "id": "shadow",
                "supplement_taxonomy": {"primary_type": "omega_3"},
                "verdict": "UNSAFE",
                "banned_substances": {"substances": [{"rule_id": "x"}]},
                "mapped_coverage": 0.5,
            }
        ],
    )

    args = argparse.Namespace(
        old_dir=str(old_dir),
        new_dir=str(new_dir),
        max_taxonomy_shifts=0,
        max_verdict_shifts=0,
        max_safety_shifts=0,
        max_mapped_coverage_drop=0.0,
        manual_approval=False,
    )
    codes = {finding.code for finding in audit.audit_shadow_diff(args)}

    assert "SHADOW_TAXONOMY_SHIFT" in codes
    assert "SHADOW_VERDICT_SHIFT" in codes
    assert "SHADOW_SAFETY_SHIFT" in codes
    assert "SHADOW_MAPPED_COVERAGE_DROP" in codes

    args.manual_approval = True
    assert audit.audit_shadow_diff(args) == []


def test_interaction_and_flutter_parity_gates_accept_matching_artifacts(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "interaction_db.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE interactions (id TEXT, severity TEXT, retired_at TEXT, retired_reason TEXT)")
        conn.execute("INSERT INTO interactions VALUES ('i1', 'caution', NULL, NULL)")
        conn.execute("CREATE TABLE interaction_db_metadata (key TEXT, value TEXT)")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('version', '1.0.0')")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_drafts_count', '1')")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_suppai_count', '0')")
    write_json(
        dist / "interaction_db_manifest.json",
        {
            "checksum_sha256": sha256(db_path),
            "interaction_db_version": "1.0.0",
            "total_interactions": 1,
            "source_drafts_count": 1,
            "source_suppai_count": 0,
        },
    )
    source_rules = tmp_path / "rules.json"
    severity_vocab = tmp_path / "severity_vocab.json"
    write_json(source_rules, {"interaction_rules": [{"id": "r1"}]})
    write_json(severity_vocab, {"severities": [{"id": "caution"}]})

    args = argparse.Namespace(dist_dir=str(dist), source_rules=str(source_rules), severity_vocab=str(severity_vocab))
    assert audit.audit_interaction(args) == []

    catalog_db = dist / "pharmaguide_core.db"
    catalog_db.write_bytes(b"catalog")
    write_json(dist / "export_manifest.json", {"checksum_sha256": sha256(catalog_db)})
    flutter_assets = tmp_path / "flutter" / "assets" / "db"
    flutter_assets.mkdir(parents=True)
    for name in ("interaction_db.sqlite", "interaction_db_manifest.json", "pharmaguide_core.db", "export_manifest.json"):
        shutil.copy2(dist / name, flutter_assets / name)

    flutter_args = argparse.Namespace(dist_dir=str(dist), flutter_repo=str(tmp_path / "flutter"))
    assert audit.audit_flutter(flutter_args) == []


def test_export_contract_requires_stamped_manifest_when_requested(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "pharmaguide_core.db"
    db_path.write_bytes(b"catalog")
    write_json(dist / "export_manifest.json", {"schema_version": "1.0.0", "product_count": 1, "checksum_sha256": sha256(db_path)})

    args = argparse.Namespace(dist_dir=str(dist), require_stamped_manifest=True)
    codes = {finding.code for finding in audit.audit_export(args)}

    assert "EXPORT_MANIFEST_CONTRACT_FIELD" in codes
