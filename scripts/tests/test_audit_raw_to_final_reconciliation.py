from __future__ import annotations

import sys

import pytest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_raw_to_final import (  # noqa: E402
    ProductRecord,
    _check_blend_children,
    _check_branded_tokens,
    _check_display_label_collapse,
    _check_plant_part,
    _check_raw_actives_present_in_blob,
    _check_standardization,
    audit_product,
)


def _record() -> ProductRecord:
    return ProductRecord(
        dsld_id="fixture",
        archetype=None,
        product_name="Fixture",
        upc=None,
    )


def _cleaned() -> dict:
    return {
        "activeIngredients": [
            {
                "name": "Magnesium Glycinate",
                "raw_source_path": "ingredientRows[0]",
            }
        ]
    }


def test_aggregate_drop_reason_cannot_amnesty_a_missing_active() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "inactive_ingredients": [],
        "display_ingredients": [],
        "ingredients_dropped_reasons": ["DROPPED_AS_INACTIVE"],
    }

    _check_raw_actives_present_in_blob(record, _cleaned(), blob)

    assert [finding.code for finding in record.findings] == [
        "RAW_ACTIVE_MISSING_FROM_BLOB"
    ]


def test_display_ledger_destination_reconciles_a_non_scoring_source_row() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "inactive_ingredients": [],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "Magnesium Glycinate",
                "display_disposition": "label_context",
            }
        ],
        "ingredients_dropped_reasons": [],
    }

    _check_raw_actives_present_in_blob(record, _cleaned(), blob)

    assert record.findings == []


def test_explicit_gate_quarantine_is_a_reconciled_final_destination(
    tmp_path: Path,
) -> None:
    record = audit_product(
        dsld_id="quarantined",
        archetype="fixture",
        blob_dir=tmp_path / "detail_blobs",
        products_root=None,
        db_path=None,
        stage_index=None,
        excluded_by_gate={
            "quarantined": ["review_queue: assessment readiness incomplete"]
        },
    )

    assert record.findings == []
    assert record.stages["final_destination"] == {
        "kind": "quarantined",
        "reasons": ["review_queue: assessment readiness incomplete"],
    }


def test_label_fidelity_checks_use_the_app_display_ledger() -> None:
    record = _record()
    blob = {
        # The legacy scoring analysis canonicalizes the title. The app renders
        # the canonical display ledger whenever it is present.
        "ingredients": [
            {
                "name": "KSM-66",
                "raw_source_text": "KSM-66",
                "display_label": "Ashwagandha",
                "standard_name": "Ashwagandha",
                "forms": [{"name": "Ashwagandha Root Extract"}],
            }
        ],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "KSM-66",
                "label_display_name": "KSM-66",
                "label_display_form": "Ashwagandha Root Extract",
                "display_type": "mapped_ingredient",
                "score_included": True,
                "analysis": {
                    "canonical_id": "ashwagandha",
                    "display_label": "Ashwagandha",
                    "standard_name": "Ashwagandha",
                    "form_note": "KSM-66 is made from ashwagandha root.",
                },
            }
        ],
    }

    _check_display_label_collapse(record, blob)
    _check_branded_tokens(record, blob)
    _check_plant_part(record, blob)

    assert record.findings == []


def test_label_fidelity_still_flags_loss_from_the_app_display_surface() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "KSM-66 Ashwagandha root extract",
                "label_display_name": "Ashwagandha",
                "display_type": "mapped_ingredient",
                "score_included": True,
                "analysis": {
                    "canonical_id": "ashwagandha",
                    "display_label": "Ashwagandha",
                    "standard_name": "Ashwagandha",
                },
            }
        ],
    }

    _check_display_label_collapse(record, blob)
    _check_branded_tokens(record, blob)
    _check_plant_part(record, blob)

    assert {finding.code for finding in record.findings} == {
        "DISPLAY_LABEL_COLLAPSES_TO_CANONICAL",
        "BRANDED_TOKEN_DROPPED",
        "PLANT_PART_DROPPED",
    }


def test_display_collapse_allows_an_explicit_reciprocal_source_correction() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "Magnesium",
                "label_display_name": "Magtein Magnesium L-Threonate",
                "display_type": "mapped_ingredient",
                "canonical_id": "magnesium",
                "mapped_to": {
                    "raw_source_path": "ingredientRows[0].nestedRows[0]",
                },
                "analysis": {
                    "display_label": "Magtein Magnesium L-Threonate",
                    "standard_name": "Magnesium",
                },
            },
            {
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "raw_source_text": "Magtein Magnesium L-Threonate",
                "label_display_name": "Magnesium",
                "display_type": "mapped_ingredient",
                "canonical_id": "magnesium",
                "mapped_to": {"raw_source_path": "ingredientRows[0]"},
                "analysis": {
                    "display_label": "Magnesium",
                    "standard_name": "Magnesium",
                },
            },
        ],
    }

    _check_display_label_collapse(record, blob)

    assert record.findings == []


def test_standardization_audit_uses_the_exporters_exact_claim_contract() -> None:
    record = _record()
    blob = {
        "ingredients": [
            {
                "name": "Saw Palmetto",
                "notes": (
                    "Generic listing without specifying the extraction method "
                    "or standardization level. Could be standardized to "
                    "85-95% fatty acids depending on the source."
                ),
                "standardization_note": None,
            },
            {
                "name": "Cranberry",
                "notes": "Standardized to 25% A-type proanthocyanidins.",
                "standardization_note": None,
            },
            {
                "name": "Ashwagandha",
                "notes": "Root extract standardized to 5% withanolides.",
                "standardization_note": None,
            },
        ]
    }

    _check_standardization(record, blob)

    assert [(finding.code, finding.ingredient) for finding in record.findings] == [
        ("STANDARDIZATION_NOTE_DROPPED", "Ashwagandha")
    ]


def test_partial_blend_allows_named_children_without_individual_amounts() -> None:
    record = _record()
    blob = {
        "proprietary_blend_detail": {
            "blends": [
                {
                    "name": "Daily Botanical Blend",
                    "disclosure_level": "partial",
                    "total_weight": 500,
                    "unit": "mg",
                    "hidden_count": 2,
                    "child_ingredients": [
                        {"name": "Ashwagandha", "amount": None, "unit": ""},
                        {"name": "Rhodiola", "amount": None, "unit": ""},
                    ],
                }
            ]
        }
    }

    _check_blend_children(record, blob)

    assert record.findings == []


def test_full_blend_requires_every_child_amount() -> None:
    record = _record()
    blob = {
        "proprietary_blend_detail": {
            "blends": [
                {
                    "name": "Fully Disclosed Blend",
                    "disclosure_level": "full",
                    "total_weight": 500,
                    "unit": "mg",
                    "child_ingredients": [
                        {"name": "Ashwagandha", "amount": 300, "unit": "mg"},
                        {"name": "Rhodiola", "amount": None, "unit": ""},
                    ],
                }
            ]
        }
    }

    _check_blend_children(record, blob)

    assert [finding.code for finding in record.findings] == [
        "BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE"
    ]


# --- Line integrity: raw DSLD row -> exported row (ADR-0005) -----------------

from audit_raw_to_final import _check_export_identity, _check_line_integrity  # noqa: E402


def _line_fixture():
    raw = {
        "ingredientRows": [
            {"name": "Vitamin C", "quantity": [{"quantity": 250, "unit": "mg"}, {"quantity": 500, "unit": "mg"}]},
            {"name": "Herbal Blend", "quantity": [{"quantity": 0, "unit": "NP"}],
             "nestedRows": [{"name": "organic Wheat Grass", "quantity": [{"quantity": 0, "unit": "NP"}]}]},
        ],
        "otheringredients": {"ingredients": [{"name": "Cellulose"}]},
    }
    cleaned = {"activeIngredients": [
        {"raw_source_path": "ingredientRows[0]", "quantityVariants": [
            {"quantity": 250, "unit": "mg"}, {"quantity": 500, "unit": "mg", "selected_for_analysis": True}]},
    ]}
    enriched = {"ingredient_quality_data": {"ingredients": [
        {"raw_source_path": "ingredientRows[0]", "canonical_id": "vitamin_c"},
        {"raw_source_path": "ingredientRows[1].nestedRows[0]", "canonical_id": "wheatgrass"},
    ]}}
    blob = {
        "row_ledger": [
            {"row_ref": "ingredientRows[0]", "source_label": "Vitamin C"},
            {"row_ref": "ingredientRows[1]", "source_label": "Herbal Blend"},
            {"row_ref": "ingredientRows[1].nestedRows[0]", "source_label": "organic  Wheat Grass"},
            {"row_ref": "otheringredients.ingredients[0]", "source_label": "Cellulose"},
        ],
        "ingredients": [
            {"raw_source_path": "ingredientRows[0]", "canonical_id": "vitamin_c", "quantity": 500.0, "unit": "mg"},
        ],
        "display_ingredients": [
            {"raw_source_path": "ingredientRows[1].nestedRows[0]", "canonical_id": "wheatgrass",
             "analysis": {"canonical_id": "wheatgrass"}},
        ],
    }
    return raw, cleaned, enriched, blob


def _line_codes(raw, cleaned, enriched, blob):
    record = _record()
    _check_line_integrity(record, raw, cleaned, enriched, blob)
    return sorted(finding.code for finding in record.findings)


def test_line_integrity_passes_a_straight_line_with_a_recorded_serving_column():
    assert _line_codes(*_line_fixture()) == []


def test_line_integrity_blocks_a_raw_row_lost_from_the_ledger():
    raw, cleaned, enriched, blob = _line_fixture()
    blob["row_ledger"] = [e for e in blob["row_ledger"] if e["row_ref"] != "otheringredients.ingredients[0]"]
    assert _line_codes(raw, cleaned, enriched, blob) == ["RAW_ROW_MISSING_FROM_LEDGER"]


def test_line_integrity_blocks_an_invented_row():
    raw, cleaned, enriched, blob = _line_fixture()
    blob["row_ledger"].append({"row_ref": "ingredientRows[7]", "source_label": "Ghost"})
    blob["ingredients"].append({"raw_source_path": "ingredientRows[8]", "canonical_id": "x"})
    assert _line_codes(raw, cleaned, enriched, blob) == ["LEDGER_ROW_NOT_IN_RAW", "LEDGER_ROW_NOT_IN_RAW"]


def test_line_integrity_blocks_a_renamed_source_row():
    raw, cleaned, enriched, blob = _line_fixture()
    blob["row_ledger"][2]["source_label"] = "Couch Grass"
    assert _line_codes(raw, cleaned, enriched, blob) == ["LEDGER_NAME_DIFFERS_FROM_RAW"]


def test_line_integrity_blocks_an_export_identity_the_enricher_never_decided():
    raw, cleaned, enriched, blob = _line_fixture()
    blob["display_ingredients"][0]["analysis"]["canonical_id"] = "couch_grass"
    blob["ingredients"][0]["canonical_id"] = "ascorbic_acid"
    assert _line_codes(raw, cleaned, enriched, blob) == [
        "EXPORT_IDENTITY_NOT_FROM_ENRICHER", "EXPORT_IDENTITY_NOT_FROM_ENRICHER"]


def test_line_integrity_treats_unresolved_as_one_state():
    raw, cleaned, enriched, blob = _line_fixture()
    enriched["ingredient_quality_data"]["ingredients"][1]["canonical_id"] = None
    blob["display_ingredients"][0]["analysis"]["canonical_id"] = ""
    assert _line_codes(raw, cleaned, enriched, blob) == []


@pytest.mark.parametrize("amount,unit", [(750.0, "mg"), (500.0, "mcg")])
def test_line_integrity_blocks_an_amount_or_unit_change_without_evidence(amount, unit):
    raw, cleaned, enriched, blob = _line_fixture()
    blob["ingredients"][0].update(quantity=amount, unit=unit)
    assert _line_codes(raw, cleaned, enriched, blob) == ["AMOUNT_CHANGE_WITHOUT_EVIDENCE"]


def test_line_integrity_accepts_a_reviewer_signed_unit_correction():
    raw, cleaned, enriched, blob = _line_fixture()
    raw["ingredientRows"][0]["quantity"] = [{"quantity": 1, "unit": "g"}]
    cleaned["activeIngredients"][0] = {"raw_source_path": "ingredientRows[0]", "quantity": 1.0,
        "source_correction": {"corrected_quantity_unit": "mg", "original_quantity_unit": "g"}}
    blob["ingredients"][0].update(quantity=1.0, unit="mg")
    assert _line_codes(raw, cleaned, enriched, blob) == []


def test_line_integrity_accepts_a_daily_value_dose_correction():
    raw, cleaned, enriched, blob = _line_fixture()
    raw["ingredientRows"][0]["quantity"] = [{"quantity": 110, "unit": "NP"}]
    cleaned["activeIngredients"][0] = {"raw_source_path": "ingredientRows[0]", "dose_data_quality": {
        "status": "corrected", "corrected_amount": 110.0, "corrected_unit": "mg"}}
    blob["ingredients"][0].update(quantity=110.0, unit="mg")
    assert _line_codes(raw, cleaned, enriched, blob) == []


def test_export_identity_reads_every_enricher_bucket_without_a_raw_label():
    # Approved submissions have no DSLD raw label; their identity is still checked.
    enriched = {"ingredient_quality_data": {"ingredients_recognized_non_scorable": [
        {"raw_source_path": "ingredientRows[2]", "canonical_id": "NHA_NATURAL_COLORS"}]}}
    blob = {"ingredients": [{"raw_source_path": "ingredientRows[2]", "canonical_id": "cabbage_extract"}]}
    record = _record()
    _check_export_identity(record, enriched, blob)
    assert [finding.code for finding in record.findings] == ["EXPORT_IDENTITY_NOT_FROM_ENRICHER"]
    blob["ingredients"][0]["canonical_id"] = "NHA_NATURAL_COLORS"
    record = _record()
    _check_export_identity(record, enriched, blob)
    assert record.findings == []


# --- Every gate finding names the product, raw row, field and both values ----

def _line_findings(raw, cleaned, enriched, blob):
    record = _record()
    _check_line_integrity(record, raw, cleaned, enriched, blob)
    return [finding.as_dict() for finding in record.findings]


def _broken_line_fixture():
    raw, cleaned, enriched, blob = _line_fixture()
    blob["row_ledger"] = [e for e in blob["row_ledger"] if e["row_ref"] != "otheringredients.ingredients[0]"]
    blob["row_ledger"].append({"row_ref": "ingredientRows[7]", "source_label": "Ghost"})
    blob["row_ledger"][2]["source_label"] = "Couch Grass"
    blob["display_ingredients"][0]["analysis"]["canonical_id"] = "couch_grass"
    blob["ingredients"][0].update(quantity=750.0)
    blob["ingredients"].append({"raw_source_path": "ingredientRows[8]", "name": "Phantom", "canonical_id": "x"})
    return raw, cleaned, enriched, blob


def test_every_line_finding_names_row_field_and_both_values():
    findings = _line_findings(*_broken_line_fixture())
    by_code = {}
    for finding in findings:
        by_code.setdefault(finding["code"], []).append(finding)
    assert set(by_code) == {
        "RAW_ROW_MISSING_FROM_LEDGER", "LEDGER_ROW_NOT_IN_RAW", "LEDGER_NAME_DIFFERS_FROM_RAW",
        "EXPORT_IDENTITY_NOT_FROM_ENRICHER", "AMOUNT_CHANGE_WITHOUT_EVIDENCE"}
    for finding in findings:
        assert finding["row_path"] and finding["field"], finding
        assert "source_value" in finding and "exported_value" in finding, finding
    assert by_code["RAW_ROW_MISSING_FROM_LEDGER"] == [{
        "severity": "BLOCKER", "code": "RAW_ROW_MISSING_FROM_LEDGER",
        "note": "raw row otheringredients.ingredients[0] has no row_ledger entry",
        "ingredient": "Cellulose", "stage": "blob", "row_path": "otheringredients.ingredients[0]",
        "field": "row_ledger.row_ref", "source_value": "Cellulose", "exported_value": None}]
    assert [(f["row_path"], f["field"], f["source_value"], f["exported_value"])
            for f in by_code["LEDGER_ROW_NOT_IN_RAW"]] == [
        ("ingredientRows[7]", "row_ledger.row_ref", None, "Ghost"),
        ("ingredientRows[8]", "ingredients.raw_source_path", None, "Phantom")]
    assert [(f["row_path"], f["field"], f["source_value"], f["exported_value"])
            for f in by_code["LEDGER_NAME_DIFFERS_FROM_RAW"]] == [
        ("ingredientRows[1].nestedRows[0]", "row_ledger.source_label", "organic Wheat Grass", "Couch Grass")]
    assert [(f["row_path"], f["field"], f["source_value"], f["exported_value"])
            for f in by_code["EXPORT_IDENTITY_NOT_FROM_ENRICHER"]] == [
        ("ingredientRows[1].nestedRows[0]", "display_ingredients.analysis.canonical_id",
         ["wheatgrass"], "couch_grass")]
    assert [(f["row_path"], f["field"], f["source_value"], f["exported_value"])
            for f in by_code["AMOUNT_CHANGE_WITHOUT_EVIDENCE"]] == [
        ("ingredientRows[0]", "quantity", "250 mg", "750.0 mg")]


def test_unit_only_change_names_the_unit_field():
    raw, cleaned, enriched, blob = _line_fixture()
    blob["ingredients"][0].update(quantity=250.0, unit="mcg")
    (finding,) = _line_findings(raw, cleaned, enriched, blob)
    assert (finding["field"], finding["source_value"], finding["exported_value"]) == (
        "unit", "250 mg", "250.0 mcg")
    blob["ingredients"][0].update(quantity=750.0)
    (finding,) = _line_findings(raw, cleaned, enriched, blob)
    assert finding["field"] == "quantity,unit"


def test_a_blocker_without_row_or_field_cannot_be_recorded():
    record = _record()
    with pytest.raises(ValueError, match="row_path and field"):
        record.add("RAW_ROW_MISSING_FROM_LEDGER", "no location")
    record.add("PLANT_PART_DROPPED", "advisory findings keep their free-text form")


def _audit_tree(tmp_path, blob, enriched, raw=None, cleaned=None):
    import json
    build = tmp_path / "build"
    (build / "detail_blobs").mkdir(parents=True)
    (build / "detail_blobs" / "100.json").write_text(json.dumps(blob))
    products = tmp_path / "products"
    (products / "output_Brand_enriched/enriched").mkdir(parents=True)
    (products / "output_Brand/cleaned").mkdir(parents=True)
    (products / "output_Brand_enriched/enriched/enriched_batch_1.json").write_text(
        json.dumps([{"id": 100, **enriched}]))
    (products / "output_Brand/cleaned/batch_1.json").write_text(json.dumps([{"id": 100, **(cleaned or {})}]))
    raw_root = tmp_path / "raw"
    (raw_root / "Brand").mkdir(parents=True)
    if raw is not None:
        (raw_root / "Brand" / "100.json").write_text(raw if isinstance(raw, str) else json.dumps(raw))
    return build, products, raw_root


def _run_audit(build, products, raw_root, out):
    import subprocess
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_raw_to_final.py"), "--build-dir", str(build),
         "--products-root", str(products), "--all", "--raw-root", str(raw_root), "--out", str(out)],
        capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("raw,code", [(None, "RAW_LABEL_NOT_FOUND"), ("{not json", "RAW_LABEL_UNREADABLE")])
def test_missing_or_unreadable_raw_label_blocks_with_its_path(tmp_path, raw, code):
    import json
    raw_fixture, cleaned, enriched, blob = _line_fixture()
    build, products, raw_root = _audit_tree(tmp_path, blob, enriched, raw=raw, cleaned=cleaned)
    result = _run_audit(build, products, raw_root, tmp_path / "out.json")
    assert result.returncode == 1, result.stdout + result.stderr
    (finding,) = [f for p in json.loads((tmp_path / "out.json").read_text())["products"]
                  for f in p["findings"] if f["code"] == code]
    assert finding["row_path"] == "label" and finding["field"] == "raw_label"
    assert str(raw_root) in finding["note"] and finding["exported_value"] == "detail_blobs/100.json"
    assert f"product=100 row=label field=raw_label" in result.stdout


def test_gate_verdict_prints_every_blocker_with_product_row_field_and_values(tmp_path):
    raw, cleaned, enriched, blob = _broken_line_fixture()
    build, products, raw_root = _audit_tree(tmp_path, blob, enriched, raw=raw, cleaned=cleaned)
    result = _run_audit(build, products, raw_root, tmp_path / "out.json")
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("BLOCKER LEDGER_NAME_DIFFERS_FROM_RAW product=100 row=ingredientRows[1].nestedRows[0] "
            "field=row_ledger.source_label source='organic Wheat Grass' exported='Couch Grass'") in result.stdout
    assert ("BLOCKER AMOUNT_CHANGE_WITHOUT_EVIDENCE product=100 row=ingredientRows[0] "
            "field=quantity source='250 mg' exported='750.0 mg'") in result.stdout


def test_gate_refuses_a_missing_raw_root_instead_of_skipping(tmp_path):
    raw, cleaned, enriched, blob = _line_fixture()
    build, products, raw_root = _audit_tree(tmp_path, blob, enriched, raw=raw, cleaned=cleaned)
    result = _run_audit(build, products, tmp_path / "absent", tmp_path / "out.json")
    assert result.returncode == 2
    assert f"raw DSLD root {tmp_path / 'absent'} missing" in result.stderr


def test_gate_has_no_environment_or_flag_bypass():
    import ast
    source = (SCRIPTS / "audit_raw_to_final.py").read_text()
    tree = ast.parse(source)
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "environ" not in names and "getenv" not in names
    # The only threshold flag can tighten the gate, never loosen it below BLOCKER.
    assert '"--severity-min", default="BLOCKER"' in source
