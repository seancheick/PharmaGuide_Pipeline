from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import time
import urllib.error
from pathlib import Path

import pytest
from PIL import Image


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _payload() -> dict:
    return {
        "brandName": "Example Labs",
        "fullName": "Example Vitamin D3",
        "ingredientRows": [
            {
                "category": "vitamin",
                "forms": [{"name": "Cholecalciferol"}],
                "ingredientGroup": "Vitamin D",
                "name": "Vitamin D",
                "nestedRows": [],
                "quantity": [{"quantity": 25, "unit": "mcg"}],
            }
        ],
        "offMarket": 0,
        "otherIngredients": "",
        "otherIngredientsDisclosure": "declared_none",
        "physicalState": {"langualCode": "", "name": "Capsule"},
        "productType": {
            "langualCode": "",
            "name": "Single-ingredient Dietary Supplement",
        },
        "servingSizes": [
            {
                "maxDailyServings": 1,
                "maxQuantity": 1,
                "minDailyServings": 1,
                "minQuantity": 1,
                "unit": "Capsule(s)",
            }
        ],
    }


def _export(payload: dict | None = None, **overrides: object) -> dict:
    canonical = _canonical(payload or _payload())
    row = {
        "approval_revision": 1,
        "approved_at": "2026-07-30T20:00:00Z",
        "approved_payload_canonical": canonical,
        "kind": "missing_product",
        "normalized_upc": "050428381397",
        "payload_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "reviewer_id": "3f276b64-0836-4bea-9453-1c8db4d1f8dd",
        "schema_version": "manual_label_v1",
        "submission_id": "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
    }
    row.update(overrides)
    return row


def test_newer_approval_revision_replaces_promoted_revision_and_rejects_mutation(
    tmp_path: Path,
):
    from product_submission_import import SubmissionImportError, materialize_approved_submissions

    first = _export()
    materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / ".product_submission_import_receipts"
    receipts = json.loads(receipt_path.read_text())
    receipt = receipts["submissions"][first["submission_id"]]
    receipt["promoted_catalog_version"] = "release-1"
    receipt["promoted_approval_revision"] = 1
    receipt_path.write_text(json.dumps(receipts))

    corrected_payload = _payload()
    corrected_payload["fullName"] = "Corrected Example Vitamin D3"
    corrected = _export(corrected_payload, approval_revision=2)
    result = materialize_approved_submissions([corrected], output_dir=tmp_path)
    assert result.imported_submission_ids == [first["submission_id"]]
    current = json.loads(result.output_paths[0].read_text())
    assert current["fullName"] == "Corrected Example Vitamin D3"
    updated = json.loads(receipt_path.read_text())
    current_receipt = updated["submissions"][first["submission_id"]]
    assert current_receipt["approval_revision"] == 2
    assert current_receipt["promoted_approval_revision"] == 1

    materialize_approved_submissions([], output_dir=tmp_path, authoritative=True)
    restored = json.loads(result.output_paths[0].read_text())
    assert restored["fullName"] == "Example Vitamin D3"
    restored_receipt = json.loads(receipt_path.read_text())["submissions"][
        first["submission_id"]
    ]
    assert restored_receipt["approval_revision"] == 1
    assert restored_receipt["promoted_approval_revision"] == 1

    materialize_approved_submissions([corrected], output_dir=tmp_path)

    mutated_payload = _payload()
    mutated_payload["fullName"] = "Same revision changed"
    with pytest.raises(SubmissionImportError, match="same approval revision changed"):
        materialize_approved_submissions(
            [_export(mutated_payload, approval_revision=2)], output_dir=tmp_path
        )


def test_withdrawn_cross_submission_replacement_restores_promoted_owner(tmp_path: Path):
    from product_submission_import import materialize_approved_submissions

    first = _export(
        kind="label_mismatch", normalized_upc=None, target_dsld_id="278454"
    )
    materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / ".product_submission_import_receipts"
    receipts = json.loads(receipt_path.read_text())
    owner = receipts["submissions"][first["submission_id"]]
    owner["promoted_catalog_version"] = "release-1"
    owner["promoted_approval_revision"] = 1
    receipt_path.write_text(json.dumps(receipts))

    replacement_payload = _payload()
    replacement_payload["fullName"] = "Replacement submission"
    replacement = _export(
        replacement_payload,
        kind="label_mismatch",
        normalized_upc=None,
        target_dsld_id="278454",
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
    )
    materialize_approved_submissions([replacement], output_dir=tmp_path)
    shared = tmp_path / "278454.json"
    assert json.loads(shared.read_text())["fullName"] == "Replacement submission"

    materialize_approved_submissions([first], output_dir=tmp_path, authoritative=True)
    assert json.loads(shared.read_text())["fullName"] == "Example Vitamin D3"
    final_receipts = json.loads(receipt_path.read_text())["submissions"]
    assert replacement["submission_id"] not in final_receipts
    assert first["submission_id"] in final_receipts


def test_schema_one_receipt_migrates_exact_approval_without_reimport(tmp_path: Path):
    from product_submission_import import build_manual_label, materialize_approved_submissions

    row = _export()
    label = build_manual_label(row)
    label["manual_product_provenance"].pop("approval_revision")
    label["manual_product_provenance"].pop("approval_payload_sha256")
    label["label_record_metadata"].pop("approval_revision")
    label["label_record_metadata"].pop("approval_payload_sha256")
    serialized = json.dumps(label, ensure_ascii=False, indent=2) + "\n"
    output = tmp_path / f"{label['id']}.json"
    output.write_text(serialized)
    (tmp_path / ".product_submission_import_receipts").write_text(json.dumps({
        "schema_version": 1,
        "submissions": {
            row["submission_id"]: {
                "label_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
                "output_file": output.name,
                "product_id": label["id"],
                "upc": label["upcSku"],
                "promoted_catalog_version": "release-1",
            },
        },
    }))

    result = materialize_approved_submissions([row], output_dir=tmp_path)
    assert result.imported_submission_ids == [row["submission_id"]]
    receipt = json.loads((tmp_path / ".product_submission_import_receipts").read_text())
    assert receipt["schema_version"] == 2
    assert receipt["submissions"][row["submission_id"]]["approval_payload_sha256"] == row["payload_sha256"]


def test_authoritative_export_removes_withdrawn_unpromoted_but_retains_promoted(
    tmp_path: Path,
):
    from product_submission_import import materialize_approved_submissions

    unpromoted = _export()
    promoted = _export(
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
        normalized_upc="01234565",
    )
    materialize_approved_submissions([unpromoted, promoted], output_dir=tmp_path)
    receipt_path = tmp_path / ".product_submission_import_receipts"
    receipts = json.loads(receipt_path.read_text())
    promoted_receipt = receipts["submissions"][promoted["submission_id"]]
    promoted_receipt["promoted_catalog_version"] = "release-1"
    promoted_receipt["promoted_approval_revision"] = 1
    receipt_path.write_text(json.dumps(receipts))

    materialize_approved_submissions([], output_dir=tmp_path, authoritative=True)
    current = json.loads(receipt_path.read_text())
    assert unpromoted["submission_id"] not in current["submissions"]
    assert promoted["submission_id"] in current["submissions"]
    assert not (tmp_path / "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11.json").exists()
    assert (tmp_path / "PG_SUB_028F4C797C7E4C709D627FC3B9CE6A22.json").exists()


def test_final_release_fence_checks_exact_unpromoted_revision(tmp_path: Path):
    from product_submission_import import materialize_approved_submissions, verify_current_approval_revisions

    row = _export()
    materialize_approved_submissions([row], output_dir=tmp_path)
    calls = []
    assert verify_current_approval_revisions(
        output_dir=tmp_path,
        rpc=lambda name, payload: calls.append((name, payload)) or True,
    ) == 1
    assert calls == [(
        "assert_product_submission_approval_revision",
        {
            "p_submission_id": row["submission_id"],
            "p_approval_revision": 1,
            "p_payload_sha256": row["payload_sha256"],
        },
    )]


def test_release_checks_exact_submission_revision_before_cloud_sync():
    release = Path("scripts/release_full.sh").read_text()
    fence = release.index("product_submission_import.py --verify-current-approvals")
    cloud_sync = release.index("scripts/sync_to_supabase.py \"$DIST_DIR\"")
    assert fence < cloud_sync
    assert '--submission-output-dir "$SUBMISSION_OUTPUT_DIR"' in release


def test_builds_pipeline_owned_identity_and_honest_private_provenance():
    from product_submission_import import build_manual_label

    label = build_manual_label(_export())

    assert label["id"] == "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11"
    assert label["upcSku"] == "050428381397"
    assert label["source_type"] == "external_manual"
    assert label["src"].endswith(label["id"])
    assert label["manual_product_provenance"] == {
        "approval_revision": 1,
        "approval_payload_sha256": _export()["payload_sha256"],
        "label_verified_at": "2026-07-30",
        "review_status": "verified",
        "reviewer": "PharmaGuide Clinical Team",
        "source_kind": "private_product_submission",
        "source_record_id": "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
    }
    assert label["label_record_metadata"]["source_record_id"] == row_id(
        _export()
    )
    serialized = json.dumps(label).lower()
    assert "user_id" not in serialized
    assert "object_path" not in serialized
    # The label ships in a public repository and into the catalog. It records
    # that a named human verified it, never the reviewer's account id: nothing
    # reads that id, and an account identifier is not label provenance.
    assert _export()["reviewer_id"] not in serialized


@pytest.mark.parametrize("crash_after_label", [False, True])
def test_legacy_reviewer_id_redaction_preserves_receipt_and_retries(
    tmp_path, monkeypatch, crash_after_label
):
    import product_submission_import as importer

    original = importer.build_manual_label

    def legacy(row):
        label = original(row)
        label["manual_product_provenance"]["reviewer_record_id"] = row["reviewer_id"]
        return label

    row = _export()
    monkeypatch.setattr(importer, "build_manual_label", legacy)
    result = importer.materialize_approved_submissions([row], output_dir=tmp_path)
    path = result.output_paths[0]
    receipt_path = tmp_path / importer.RECEIPT_FILE
    receipts = json.loads(receipt_path.read_text())
    receipts["submissions"][row["submission_id"]]["promoted_catalog_version"] = "existing-release"
    receipt_path.write_text(json.dumps(receipts))
    monkeypatch.setattr(importer, "build_manual_label", original)
    if crash_after_label:
        path.write_text(json.dumps(original(row), ensure_ascii=False, indent=2) + "\n")
    importer.materialize_approved_submissions([row], output_dir=tmp_path)
    assert row["reviewer_id"] not in path.read_text()
    updated_receipt = json.loads(receipt_path.read_text())["submissions"][row["submission_id"]]
    assert updated_receipt["promoted_catalog_version"] == "existing-release"
    retry = importer.materialize_approved_submissions([row], output_dir=tmp_path)
    assert retry.already_imported_submission_ids == [row["submission_id"]]


@pytest.mark.parametrize("tamper", ["label", "approval", "reviewer", "receipt"])
def test_privacy_migration_refuses_any_other_change(tmp_path, monkeypatch, tamper):
    import product_submission_import as importer

    original = importer.build_manual_label

    def legacy(row):
        label = original(row)
        label["manual_product_provenance"]["reviewer_record_id"] = row["reviewer_id"]
        return label

    row = _export()
    monkeypatch.setattr(importer, "build_manual_label", legacy)
    result = importer.materialize_approved_submissions([row], output_dir=tmp_path)
    path = result.output_paths[0]
    receipt_path = tmp_path / importer.RECEIPT_FILE
    monkeypatch.setattr(importer, "build_manual_label", original)
    if tamper == "label":
        label = json.loads(path.read_text())
        label["fullName"] = "Changed product"
        path.write_text(json.dumps(label, ensure_ascii=False, indent=2) + "\n")
    elif tamper == "approval":
        payload = _payload()
        payload["ingredientRows"][0]["quantity"][0]["quantity"] = 100
        row = _export(payload)
    elif tamper == "reviewer":
        row["reviewer_id"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    else:
        receipts = json.loads(receipt_path.read_text())
        receipts["submissions"][row["submission_id"]]["label_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(receipts))
    before = (path.read_bytes(), receipt_path.read_bytes())
    with pytest.raises(importer.SubmissionImportError, match="changed after approval"):
        importer.materialize_approved_submissions([row], output_dir=tmp_path)
    assert (path.read_bytes(), receipt_path.read_bytes()) == before


def test_generated_private_provenance_passes_canonical_manual_validator():
    import dsld_api_sync
    from product_submission_import import build_manual_label

    # A private user-submission record has no honest public URL. The canonical
    # validator accepts its typed private source record instead of forcing a
    # fabricated web address.
    dsld_api_sync._validate_external_manual_label(build_manual_label(_export()))


@pytest.mark.parametrize("target_id", [None, "12345"])
@pytest.mark.parametrize("explicit_null", [False, True])
def test_verified_private_submission_without_nih_taxonomy_passes_clean(target_id, explicit_null):
    from dsld_validator import DSLDValidator
    from product_submission_import import build_manual_label

    payload = _payload()
    payload.pop("productType")
    if explicit_null:
        payload["productType"] = None
    overrides = {} if target_id is None else {
        "correction_target_dsld_id": target_id,
    }
    label = build_manual_label(_export(payload, **overrides))
    status, missing, details = DSLDValidator().validate_product(label)
    assert status == "success"
    assert "productType" not in missing
    assert label.get("productType") is None  # No invented NIH taxonomy.
    assert details["critical_fields_complete"] is True


@pytest.mark.parametrize("mutation", [
    "nih", "unverified", "no_provenance", "bad_private_id", "bad_private_id_with_url",
    "no_reviewer", "public_manual", "no_physical_state", "no_name",
])
def test_optional_nih_taxonomy_never_bypasses_other_source_guards(mutation):
    from dsld_validator import DSLDValidator
    from product_submission_import import build_manual_label

    payload = _payload()
    payload.pop("productType")
    label = build_manual_label(_export(payload))
    provenance = label["manual_product_provenance"]
    if mutation == "nih":
        label["id"] = 12345
        label["source_type"] = "nih_dsld"
    elif mutation == "unverified":
        provenance["review_status"] = "pending"
    elif mutation == "no_provenance":
        label.pop("manual_product_provenance")
    elif mutation in {"bad_private_id", "bad_private_id_with_url"}:
        provenance["source_record_id"] = "not-a-uuid"
        if mutation == "bad_private_id_with_url":
            provenance["source_url"] = "https://example.com/label"
    elif mutation == "no_reviewer":
        provenance.pop("reviewer")
    elif mutation == "public_manual":
        provenance["source_kind"] = "external_label"
        provenance["source_url"] = "https://example.com/label"
    elif mutation == "no_physical_state":
        label.pop("physicalState")
    else:
        label.pop("fullName")
    status, missing, details = DSLDValidator().validate_product(label)
    assert status != "success"
    if mutation not in {"no_physical_state", "no_name"}:
        assert "productType" in missing
    elif mutation == "no_physical_state":
        assert "physicalState" in missing
    else:
        assert "fullName" in missing
        assert details["critical_fields_complete"] is False


@pytest.mark.parametrize("taxonomy", [{}, [], ""])
def test_empty_populated_taxonomy_retains_the_normal_clean_requirement(taxonomy):
    from dsld_validator import DSLDValidator
    from product_submission_import import build_manual_label

    label = build_manual_label(_export())
    label["productType"] = taxonomy
    status, missing, _ = DSLDValidator().validate_product(label)
    assert status == "needs_review"
    assert "productType" in missing


def test_committed_submission_labels_keep_reviewer_accounts_private():
    labels_dir = Path(__file__).resolve().parents[2] / "manual_labels/product_submissions"
    labels = list(labels_dir.glob("*.json"))
    assert labels, "The committed submission labels are the privacy regression corpus"
    for path in labels:
        label = json.loads(path.read_text(encoding="utf-8"))
        assert "reviewer_record_id" not in label["manual_product_provenance"], path.name


def test_october_submitted_labels_preserve_photo_verified_details():
    labels_dir = Path(__file__).resolve().parents[2] / "manual_labels/product_submissions"
    ids = {
        "align": "PG_SUB_4ACB39B94D394C19815F63B0A783EF08",
        "trader_joes_vitamin_c": "PG_SUB_3D5877FE66FA423F9AC3C90EE52EF8CA",
        "just_ingredients": "PG_SUB_5E4D136A84A8485F98E1F3C0BCF49A73",
        "pure": "PG_SUB_6AFDA9855BFA449BB235FCFE6ECBAF96",
        "trader_joes_d3": "PG_SUB_5EB9F9D6F38C4648A6560B489E0E4916",
        "sports_research": "PG_SUB_8F025E8FFB164793B3B68B15EED2CD31",
        "trader_joes_melatonin": "PG_SUB_21B7F5A0D3414040948D242FB03DD01B",
        "santo_remedio": "PG_SUB_4D246163F6CD468CA82B5E023468B9C1",
        "nutricost": "PG_SUB_2E7000A890174F10BAA7870FE5EAD7F3",
        "trader_joes_probiotic": "PG_SUB_1A28723DBDAF4AC1897AA5FF156FACA1",
    }
    labels = {
        key: json.loads((labels_dir / f"{product_id}.json").read_text(encoding="utf-8"))
        for key, product_id in ids.items()
    }

    # Raw imported files remain immutable approval bytes. The existing correction
    # owner supplies the reviewed view consumed by Clean.
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    normalizer = EnhancedDSLDNormalizer()
    for key, raw in labels.items():
        reviewed = deepcopy(normalizer._apply_reviewed_serving_basis(raw))
        normalizer._stamp_raw_source_paths(reviewed["ingredientRows"], "ingredientRows")
        reviewed["ingredientRows"] = normalizer._apply_label_corrections(
            reviewed["ingredientRows"], reviewed["id"])
        labels[key] = reviewed

    expected_forms = {
        "align": "Capsule",
        "trader_joes_vitamin_c": "Tablet or Pill",
        "just_ingredients": "Capsule",
        "pure": "Capsule",
        "trader_joes_d3": "Softgel Capsule",
        "sports_research": "Capsule",
        "trader_joes_melatonin": "Tablet or Pill",
        "santo_remedio": "Capsule",
        "nutricost": "Capsule",
        "trader_joes_probiotic": "Capsule",
    }
    for key, expected_form in expected_forms.items():
        assert labels[key]["physicalState"] == {
            "langualCodeDescription": expected_form,
            "name": expected_form,
        }
        serving = labels[key]["servingSizes"][0]
        assert serving["minDailyServings"] == 1
        assert serving["maxDailyServings"] == (2 if key == "sports_research" else 1)

    align_rows = labels["align"]["ingredientRows"]
    assert align_rows[0]["name"] == "Bifidobacterium longum subsp. longum 35624™"
    assert [row["name"] for row in align_rows[1]["nestedRows"]] == [
        "Lactobacillus acidophilus La-14®",
        "Lacticaseibacillus rhamnosus HN001™",
    ]

    assert labels["sports_research"]["ingredientRows"][0]["notes"] == "38% Daily Value"
    assert labels["trader_joes_melatonin"]["ingredientRows"][0]["notes"] == (
        "Daily Value not established"
    )
    assert labels["santo_remedio"]["ingredientRows"][0]["notes"] == (
        "Daily Value not established"
    )
    assert all(
        row["notes"] == "Daily Value not established"
        for row in labels["nutricost"]["ingredientRows"]
    )
    assert labels["trader_joes_probiotic"]["ingredientRows"][0]["notes"].endswith(
        "Daily Value not established."
    )

    santo_inactive = {
        row["name"]
        for row in labels["santo_remedio"]["otherIngredients"]["ingredients"]
    }
    assert santo_inactive == {
        "Gelatin (capsule)",
        "Microcrystalline Cellulose",
        "Magnesium Stearate",
        "Silica",
    }
    pure_label_text = json.dumps(labels["pure"]).lower()
    assert all(term not in pure_label_text for term in ("lanolin", "geraniol", "farnesol"))


def test_present_other_ingredients_become_supported_pipeline_rows():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from product_submission_import import build_manual_label

    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = (
        "Vegetarian capsule (hypromellose, water), microcrystalline cellulose, "
        "vegetable magnesium stearate, silicon dioxide."
    )

    label = build_manual_label(_export(payload))

    assert label["otherIngredients"] == {
        "ingredients": [
            {"name": "Vegetarian capsule (hypromellose, water)"},
            {"name": "microcrystalline cellulose"},
            {"name": "vegetable magnesium stearate"},
            # The sentence's closing period is not part of the name.
            {"name": "silicon dioxide"},
        ]
    }
    cleaned = EnhancedDSLDNormalizer().normalize_product(label)
    assert cleaned["label_ledger_audit"]["support_status"] == "supported"
    assert all(
        row.get("omission_reason") != "unsupported_source_structure"
        for row in cleaned["label_ledger_omissions"]
    )


def test_present_other_ingredients_fail_closed_on_unbalanced_grouping():
    from product_submission_import import SubmissionImportError, build_manual_label

    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = "Capsule (hypromellose, silica"

    with pytest.raises(SubmissionImportError, match="unbalanced grouping"):
        build_manual_label(_export(payload))


def test_quantified_disclosure_preserves_ingredients_and_their_qualifier():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from product_submission_import import build_manual_label

    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = (
        "Microcrystalline cellulose; Less than 2% of: magnesium stearate, "
        "silicon dioxide."
    )
    label = build_manual_label(_export(payload))
    assert label["otherIngredients"]["ingredients"][1] == {
        "name": "Less than 2% of:",
        "forms": [{"name": "magnesium stearate"}, {"name": "silicon dioxide"}],
    }
    cleaned = EnhancedDSLDNormalizer().normalize_product(label)
    assert any(
        row.get("canonical_id") and "magnesium stearate" in row["name"].lower()
        for row in cleaned["inactiveIngredients"]
    )
    assert any(
        row.get("raw_source_text") == "Less than 2% of:"
        and "magnesium stearate" in row.get("children", [])
        for row in cleaned["display_ingredients"]
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "May contain: milk, soy; cellulose",
            [
                {"name": "May contain:", "forms": [{"name": "milk"}, {"name": "soy"}]},
                {"name": "cellulose"},
            ],
        ),
        (
            "Less than 2% of: capsule (hypromellose, water), silica",
            [{"name": "Less than 2% of:", "forms": [
                {"name": "capsule (hypromellose, water)"}, {"name": "silica"},
            ]}],
        ),
        (
            "Does not contain: milk; color (vegetable juice)",
            [{"name": "Does not contain: milk"}, {"name": "color (vegetable juice)"}],
        ),
        (
            "Less than 2% of: silica; Less than 1% of: carnauba wax",
            [
                {"name": "Less than 2% of:", "forms": [{"name": "silica"}]},
                {"name": "Less than 1% of:", "forms": [{"name": "carnauba wax"}]},
            ],
        ),
        # The sentence ends the list; its period is not part of the last name.
        (
            "Gelatin; Less than 2% of: magnesium stearate, silicon dioxide.",
            [
                {"name": "Gelatin"},
                {"name": "Less than 2% of:", "forms": [
                    {"name": "magnesium stearate"}, {"name": "silicon dioxide"},
                ]},
            ],
        ),
        # Printed abbreviations and numbers keep their full stop.
        (
            "Rice flour, grape seed (Vitis vinifera L.)",
            [{"name": "Rice flour"}, {"name": "grape seed (Vitis vinifera L.)"}],
        ),
        (
            "Cellulose, Vitis vinifera L.",
            [{"name": "Cellulose"}, {"name": "Vitis vinifera L."}],
        ),
        (
            "Cellulose, pectin (ACME Ingredients Inc.)",
            [{"name": "Cellulose"}, {"name": "pectin (ACME Ingredients Inc.)"}],
        ),
    ],
)
def test_disclosure_grouping_preserves_scope_and_never_strips_negation(text, expected):
    from product_submission_import import build_manual_label

    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = text
    assert build_manual_label(_export(payload))["otherIngredients"]["ingredients"] == expected


def test_disclosure_heading_without_a_child_fails_closed():
    from product_submission_import import SubmissionImportError, build_manual_label

    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = "Less than 2% of:"
    with pytest.raises(SubmissionImportError, match="heading without an ingredient"):
        build_manual_label(_export(payload))


@pytest.mark.parametrize("source_shape", ["text", "inline_row", "structured_header"])
def test_native_pipeline_and_submission_use_the_same_disclosure_cleaning(source_shape):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from product_submission_import import build_manual_label

    text = "Less than 2% of: magnesium stearate, silicon dioxide"
    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = text
    imported = build_manual_label(_export(payload))
    native = json.loads(json.dumps(imported))
    if source_shape == "text":
        native["otherIngredients"] = text
    elif source_shape == "inline_row":
        native["otherIngredients"] = {"ingredients": [{"name": text}]}
    normalizer = EnhancedDSLDNormalizer()
    expected = normalizer.normalize_product(imported)
    actual = normalizer.normalize_product(native)
    assert actual["inactiveIngredients"] == expected["inactiveIngredients"]
    assert actual["display_ingredients"] == expected["display_ingredients"]
    assert actual["label_ledger_audit"] == expected["label_ledger_audit"]


def test_native_standalone_heading_keeps_existing_structural_handling():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = _payload()
    raw["id"] = "standalone-heading"
    raw["otherIngredients"] = {"ingredients": [{"name": "Less than 2% of:"}]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    assert cleaned["activeIngredients"]
    assert not cleaned["inactiveIngredients"]
    assert any(
        row["omission_reason"] == "decorative_or_header_text"
        for row in cleaned["label_ledger_omissions"]
    )


def test_native_and_submission_routes_have_identical_enrichment_and_v4_score():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from product_submission_import import build_manual_label
    from scoring_v4.scored_artifact import build_scored_artifact

    text = "Less than 2% of: magnesium stearate, silicon dioxide"
    payload = _payload()
    payload["otherIngredientsDisclosure"] = "present"
    payload["otherIngredients"] = text
    imported = build_manual_label(_export(payload))
    native = json.loads(json.dumps(imported))
    native["otherIngredients"] = {"ingredients": [{"name": text}]}
    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()
    results = []
    for raw in (imported, native):
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        results.append((enriched, build_scored_artifact(enriched)))

    first, second = results
    for field in ("ingredient_quality_data", "harmful_additives", "allergen_hits"):
        assert first[0][field] == second[0][field]
    for field in ("quality_score_v4_100", "quality_score_status", "quality_pillars_v4"):
        assert first[1][field] == second[1][field]


def row_id(row: dict) -> str:
    return str(row["submission_id"])


@pytest.mark.parametrize("name,group,source,form_id", [
    ("Inositol", "Inositol", "inositol niacinate", "inositol from inositol hexanicotinate"),
    ("Tributyrin", "Butyric Acid", "CoreBiome tributyrin", "tributyrin"),
])
def test_source_compound_forms_share_native_and_submission_pipeline(name, group, source, form_id):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from product_submission_import import build_manual_label
    from scoring_v4.scored_artifact import build_scored_artifact

    payload = _payload()
    payload["ingredientRows"][0].update({
        "name": name, "ingredientGroup": group,
        "forms": [{"name": source}],
        "quantity": [{"quantity": 1, "unit": "mg"}],
    })
    imported = build_manual_label(_export(payload))
    native = dict(payload, id="native-source-form")
    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()
    outputs = []
    for raw in (native, imported):
        enriched, errors = enricher.enrich_product(normalizer.normalize_product(raw))
        assert not errors
        rows = enriched["ingredient_quality_data"]["ingredients"]
        assert rows[0]["form_id"] == form_id
        assert rows[0]["quantity"] == 1
        outputs.append((rows, build_scored_artifact(enriched)))
    assert outputs[0][0] == outputs[1][0]
    for field in ("quality_score_v4_100", "quality_score_status", "quality_pillars_v4"):
        assert outputs[0][1][field] == outputs[1][1][field]


def test_admin_headers_support_secret_keys_without_fabricating_a_bearer_jwt(
    monkeypatch: pytest.MonkeyPatch,
):
    from product_submission_import import _supabase_admin_headers

    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_pipeline_key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-key")

    headers = _supabase_admin_headers()

    assert headers["apikey"] == "sb_secret_pipeline_key"
    assert "authorization" not in headers


def test_admin_headers_keep_legacy_service_role_compatibility(
    monkeypatch: pytest.MonkeyPatch,
):
    from product_submission_import import _supabase_admin_headers

    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "eyJlegacy.jwt")

    headers = _supabase_admin_headers()

    assert headers["apikey"] == "eyJlegacy.jwt"
    assert headers["authorization"] == "Bearer eyJlegacy.jwt"


def test_approved_export_uses_stable_cursor_pagination(
    monkeypatch: pytest.MonkeyPatch,
):
    from product_submission_import import fetch_approved_submissions

    first = _export(
        submission_id="018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
        approved_at="2026-07-30T10:00:00+00:00",
    )
    second = _export(
        submission_id="118f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
        approved_at="2026-07-30T10:00:01+00:00",
    )
    payloads: list[dict[str, object]] = []
    pages = [[first, second], []]

    class _Response:
        def __init__(self, body: list[dict[str, object]]) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self._body).encode("utf-8")

    def _urlopen(request, timeout):
        assert timeout == 30
        payloads.append(json.loads(request.data))
        return _Response(pages.pop(0))

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_pipeline_key")
    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    rows = fetch_approved_submissions(limit=2)

    assert rows == [first, second]
    assert payloads == [
        {
            "p_after_approved_at": None,
            "p_after_submission_id": None,
            "p_limit": 2,
        },
        {
            "p_after_approved_at": second["approved_at"],
            "p_after_submission_id": second["submission_id"],
            "p_limit": 2,
        },
    ]


def test_approved_export_retries_a_transient_network_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    from product_submission_import import fetch_approved_submissions

    attempts = 0
    retry_delays: list[float] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return b"[]"

    def _urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise urllib.error.URLError("temporary connection failure")
        return _Response()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_pipeline_key")
    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    monkeypatch.setattr(time, "sleep", retry_delays.append)

    assert fetch_approved_submissions() == []
    assert attempts == 2
    assert retry_delays == [0.5]


def test_approved_export_reports_permanent_http_failure_without_retry(
    monkeypatch: pytest.MonkeyPatch,
):
    from product_submission_import import (
        SubmissionImportError,
        fetch_approved_submissions,
    )

    attempts = 0
    retry_delays: list[float] = []

    def _urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError(
            "https://example.supabase.co/rest/v1/rpc/export",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"message":"secret server detail"}'),
        )

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_pipeline_key")
    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    monkeypatch.setattr(time, "sleep", retry_delays.append)

    with pytest.raises(SubmissionImportError, match=r"failed: HTTP 401") as exc:
        fetch_approved_submissions()

    assert "secret server detail" not in str(exc.value)
    assert attempts == 1
    assert retry_delays == []


def test_approved_export_fails_closed_if_cursor_does_not_advance(
    monkeypatch: pytest.MonkeyPatch,
):
    from product_submission_import import (
        SubmissionImportError,
        fetch_approved_submissions,
    )

    row = _export()

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps([row]).encode("utf-8")

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_pipeline_key")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(),
    )

    with pytest.raises(SubmissionImportError, match="cursor did not advance"):
        fetch_approved_submissions(limit=1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "future_schema"),
        ("submission_id", "../escape"),
        ("reviewer_id", ""),
        ("normalized_upc", "12345678"),
        ("kind", "unknown"),
    ],
)
def test_rejects_invalid_export_envelope(field: str, value: object):
    from product_submission_import import SubmissionImportError, build_manual_label

    with pytest.raises(SubmissionImportError):
        build_manual_label(_export(**{field: value}))


def test_rejects_hash_mismatch_and_noncanonical_payload():
    from product_submission_import import SubmissionImportError, build_manual_label

    with pytest.raises(SubmissionImportError, match="hash"):
        build_manual_label(_export(payload_sha256="0" * 64))

    noncanonical = json.dumps(_payload(), ensure_ascii=False)
    with pytest.raises(SubmissionImportError, match="canonical"):
        build_manual_label(
            _export(
                approved_payload_canonical=noncanonical,
                payload_sha256=hashlib.sha256(noncanonical.encode()).hexdigest(),
            )
        )


@pytest.mark.parametrize(
    "forbidden",
    [
        "id",
        "upcSku",
        "src",
        "source_type",
        "manual_product_provenance",
        "label_record_metadata",
        "user_id",
        "notes",
    ],
)
def test_reviewer_payload_cannot_override_identity_or_provenance(forbidden: str):
    from product_submission_import import SubmissionImportError, build_manual_label

    payload = _payload()
    payload[forbidden] = "untrusted"
    with pytest.raises(SubmissionImportError, match="field"):
        build_manual_label(_export(payload))


def test_materialization_is_atomic_idempotent_and_rejects_upc_collision(
    tmp_path: Path,
):
    from product_submission_import import (
        SubmissionImportError,
        materialize_approved_submissions,
    )

    first = _export()
    result = materialize_approved_submissions([first], output_dir=tmp_path)
    assert result.imported_submission_ids == [first["submission_id"]]
    assert len(
        [path for path in tmp_path.glob("*.json") if not path.name.startswith("_")]
    ) == 1
    assert (tmp_path / ".product_submission_import_receipts").exists()

    retry = materialize_approved_submissions([first], output_dir=tmp_path)
    assert retry.imported_submission_ids == []
    assert retry.already_imported_submission_ids == [first["submission_id"]]

    second = _export(
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
    )
    with pytest.raises(SubmissionImportError, match="UPC"):
        materialize_approved_submissions([second], output_dir=tmp_path)


def test_materialization_recovers_exact_label_after_receipt_write_interruption(
    tmp_path: Path,
):
    from product_submission_import import materialize_approved_submissions

    row = _export()
    first = materialize_approved_submissions([row], output_dir=tmp_path)
    label_path = first.output_paths[0]
    original_bytes = label_path.read_bytes()
    (tmp_path / ".product_submission_import_receipts").unlink()

    recovered = materialize_approved_submissions([row], output_dir=tmp_path)

    assert recovered.imported_submission_ids == [row["submission_id"]]
    assert label_path.read_bytes() == original_bytes
    assert (tmp_path / ".product_submission_import_receipts").exists()


@pytest.mark.parametrize("same_export", [False, True])
@pytest.mark.parametrize(
    ("first_upc", "second_upc"),
    [
        ("01234565", "00000001234565"),
        ("050428381397", "0050428381397"),
        ("0050428381397", "00050428381397"),
        ("00050428381397", "050428381397"),
    ],
)
def test_equivalent_gtin_widths_cannot_materialize_two_submission_identities(
    tmp_path: Path, same_export: bool, first_upc: str, second_upc: str,
):
    from product_submission_import import (
        SubmissionImportError,
        materialize_approved_submissions,
    )

    first = _export(normalized_upc=first_upc)
    second = _export(
        normalized_upc=second_upc,
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
    )
    if not same_export:
        imported = materialize_approved_submissions([first], output_dir=tmp_path)
        label = json.loads(imported.output_paths[0].read_text())
        assert label["upcSku"] == first_upc
        before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
        retry = materialize_approved_submissions([first], output_dir=tmp_path)
        assert retry.already_imported_submission_ids == [first["submission_id"]]
        assert retry.imported_submission_ids == []
    else:
        before = {}

    with pytest.raises(SubmissionImportError, match="UPC"):
        materialize_approved_submissions(
            [first, second] if same_export else [second], output_dir=tmp_path,
        )

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


@pytest.mark.parametrize("same_export", [False, True])
@pytest.mark.parametrize(
    ("first_upc", "second_upc"),
    [("01234565", "012345000065"), ("012345000065", "01234565")],
)
def test_established_ean8_identity_does_not_own_ambiguous_upce_candidate(
    tmp_path: Path, same_export: bool, first_upc: str, second_upc: str,
):
    from product_submission_import import materialize_approved_submissions

    first = _export(normalized_upc=first_upc)
    second = _export(
        normalized_upc=second_upc,
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
    )
    if same_export:
        result = materialize_approved_submissions([first, second], output_dir=tmp_path)
        assert result.imported_submission_ids == [
            first["submission_id"], second["submission_id"],
        ]
    else:
        materialize_approved_submissions([first], output_dir=tmp_path)
        result = materialize_approved_submissions([second], output_dir=tmp_path)
        assert result.imported_submission_ids == [second["submission_id"]]

    assert {
        json.loads(path.read_text())["upcSku"] for path in tmp_path.glob("*.json")
    } == {first_upc, second_upc}
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    retry = materialize_approved_submissions([first, second], output_dir=tmp_path)
    assert retry.imported_submission_ids == []
    assert retry.already_imported_submission_ids == [
        first["submission_id"], second["submission_id"],
    ]
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_new_correction_replaces_only_a_previously_promoted_correction(
    tmp_path: Path,
):
    from product_submission_import import materialize_approved_submissions

    first = _export(
        kind="label_mismatch",
        normalized_upc="050428381397",
        target_dsld_id="278454",
    )
    materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / ".product_submission_import_receipts"
    receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipts["submissions"][first["submission_id"]][
        "promoted_catalog_version"
    ] = "2026.07.30.220000"
    receipt_path.write_text(json.dumps(receipts), encoding="utf-8")

    second_payload = _payload()
    second_payload["fullName"] = "Clinically reviewed second correction"
    second = _export(
        second_payload,
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
        kind="label_mismatch",
        normalized_upc="050428381397",
        target_dsld_id="278454",
    )
    result = materialize_approved_submissions([second], output_dir=tmp_path)

    assert result.imported_submission_ids == [second["submission_id"]]
    current = json.loads((tmp_path / "278454.json").read_text(encoding="utf-8"))
    assert current["fullName"] == "Clinically reviewed second correction"
    assert (
        current["label_record_metadata"]["source_record_id"]
        == second["submission_id"]
    )


def test_new_correction_cannot_replace_an_unpromoted_correction(tmp_path: Path):
    from product_submission_import import (
        SubmissionImportError,
        materialize_approved_submissions,
    )

    first = _export(
        kind="label_mismatch",
        normalized_upc=None,
        target_dsld_id="278454",
    )
    materialize_approved_submissions([first], output_dir=tmp_path)
    second_payload = _payload()
    second_payload["fullName"] = "Conflicting correction"
    second = _export(
        second_payload,
        submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
        kind="label_mismatch",
        normalized_upc=None,
        target_dsld_id="278454",
    )

    with pytest.raises(SubmissionImportError, match="unpromoted"):
        materialize_approved_submissions([second], output_dir=tmp_path)


def test_materialized_label_enters_existing_import_local_path(tmp_path: Path):
    import dsld_api_sync
    from product_submission_import import materialize_approved_submissions

    manual_dir = tmp_path / "manual"
    materialize_approved_submissions([_export()], output_dir=manual_dir)
    canonical_root = tmp_path / "forms"
    state_file = tmp_path / "state.json"
    args = type(
        "Args",
        (),
        {
            "canonical_root": str(canonical_root),
            "dated_delta": False,
            "delta_output_dir": None,
            "force_refetch": False,
            "input_dir": str(manual_dir),
            "report_dir": None,
            "state_file": str(state_file),
        },
    )()

    assert dsld_api_sync._cmd_import_local(args) == 0
    imported = list(canonical_root.rglob("PG_SUB_*.json"))
    assert len(imported) == 1
    label = json.loads(imported[0].read_text(encoding="utf-8"))
    assert label["manual_product_provenance"]["review_status"] == "verified"


def test_approved_product_picture_is_webp_indexed_and_bound_to_catalog(
    tmp_path: Path,
):
    from product_submission_import import (
        copy_approved_product_images,
        materialize_approved_submissions,
    )

    row = _export()
    manual_dir = tmp_path / "manual"
    materialize_approved_submissions([row], output_dir=manual_dir)
    product_id = "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11"

    catalog = tmp_path / "pharmaguide_core.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "create table products_core "
            "(dsld_id text primary key, image_thumbnail_url text)"
        )
        connection.execute(
            "insert into products_core values (?, null)",
            (product_id,),
        )
    (tmp_path / "export_manifest.json").write_text(json.dumps({
        "db_version": "release-2",
    }))
    image_dir = tmp_path / "product_images"
    image_dir.mkdir()
    (image_dir / "product_image_index.json").write_text("{}\n")

    source = io.BytesIO()
    Image.new("RGB", (1800, 1200), "#183b3f").save(source, format="PNG")
    source_bytes = source.getvalue()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    calls: list[tuple[str, dict[str, object]]] = []

    result = copy_approved_product_images(
        output_dir=manual_dir,
        catalog_db=catalog,
        product_images_dir=image_dir,
        rpc=lambda name, payload: calls.append((name, payload)) or [{
            "bucket_id": "product-submission-photos",
            "object_path": "user/submission/front.jpg",
            "content_type": "image/png",
            "content_sha256": source_hash,
        }],
        download=lambda bucket, path: source_bytes,
    )

    assert result == {"copied": 1, "failed": 0, "skipped": 0}
    assert calls == [(
        "get_approved_product_submission_image",
        {
            "p_submission_id": row["submission_id"],
            "p_approval_revision": 1,
            "p_payload_sha256": row["payload_sha256"],
        },
    )]
    webp_path = image_dir / f"{product_id}.webp"
    assert webp_path.is_file()
    with Image.open(webp_path) as rendered:
        assert rendered.format == "WEBP"
        assert rendered.size == (900, 600)
    index = json.loads((image_dir / "product_image_index.json").read_text())
    assert index[product_id]["filename"] == f"{product_id}.webp"
    assert index[product_id]["remote_path"] == f"vrelease-2/{product_id}.webp"
    assert index[product_id]["sha256"] == hashlib.sha256(
        webp_path.read_bytes()
    ).hexdigest()
    with sqlite3.connect(catalog) as connection:
        assert connection.execute(
            "select image_thumbnail_url from products_core where dsld_id = ?",
            (product_id,),
        ).fetchone() == (f"product-images/vrelease-2/{product_id}.webp",)


def test_label_mismatch_preserves_existing_dsld_identity():
    from product_submission_import import build_manual_label

    row = _export(
        kind="label_mismatch",
        normalized_upc=None,
        target_dsld_id="278454",
    )

    label = build_manual_label(row)

    assert label["id"] == "278454"
    assert label["upcSku"] == ""
    assert label["label_record_metadata"]["lineage_key"] == "dsld:278454"
    assert (
        label["label_record_metadata"]["source_record_id"]
        == row["submission_id"]
    )
    assert (
        label["manual_product_provenance"]["source_record_id"]
        == row["submission_id"]
    )


def test_label_mismatch_rejects_unverified_upc_metadata():
    from product_submission_import import SubmissionImportError, build_manual_label

    row = _export(
        kind="label_mismatch",
        normalized_upc="12345678",
        target_dsld_id="278454",
    )

    with pytest.raises(SubmissionImportError, match="valid GTIN"):
        build_manual_label(row)


def test_marks_promoted_only_after_product_exists_in_released_catalog(
    tmp_path: Path,
):
    from product_submission_import import (
        SubmissionImportError,
        mark_released_submissions_promoted,
        materialize_approved_submissions,
    )

    manual_dir = tmp_path / "manual"
    row = _export()
    materialize_approved_submissions([row], output_dir=manual_dir)
    catalog = tmp_path / "pharmaguide_core.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "create table products_core "
            "(dsld_id text primary key, detail_blob_sha256 text)"
        )
        connection.execute("create table export_manifest (key text, value text)")
        connection.execute(
            "insert into products_core values (?, null)",
            ("PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11",),
        )
        connection.execute(
            "insert into export_manifest values ('db_version', '2026.07.30.220000')"
        )
    detail_blobs = tmp_path / "detail_blobs"
    detail_blobs.mkdir()

    calls: list[tuple[str, dict]] = []
    with pytest.raises(SubmissionImportError, match="detail-blob hash"):
        mark_released_submissions_promoted(
            output_dir=manual_dir,
            catalog_db=catalog,
            detail_blobs_dir=detail_blobs,
            rpc=lambda name, payload: calls.append((name, payload)) or True,
        )
    assert calls == []

    product_id = "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11"
    detail_bytes = json.dumps(
        {
            "label_record": {
                "source_record_id": row["submission_id"],
                "lineage_key": "pharmaguide_submission:" + row["submission_id"],
                "approval_revision": 1,
                "approval_payload_sha256": row["payload_sha256"],
            }
        }
    ).encode()
    (detail_blobs / f"{product_id}.json").write_bytes(detail_bytes)
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "update products_core set detail_blob_sha256 = ? where dsld_id = ?",
            (hashlib.sha256(detail_bytes).hexdigest(), product_id),
        )
    promoted = mark_released_submissions_promoted(
        output_dir=manual_dir,
        catalog_db=catalog,
        detail_blobs_dir=detail_blobs,
        rpc=lambda name, payload: calls.append((name, payload)) or True,
    )

    assert promoted == [row["submission_id"]]
    assert calls == [
        (
            "mark_product_submission_promoted",
            {
                "p_catalog_version": "2026.07.30.220000",
                "p_resolved_dsld_id": product_id,
                "p_submission_id": row["submission_id"],
                "p_approval_revision": 1,
                "p_payload_sha256": row["payload_sha256"],
            },
        )
    ]
    receipts = json.loads(
        (manual_dir / ".product_submission_import_receipts").read_text()
    )
    assert (
        receipts["submissions"][row["submission_id"]]["promoted_catalog_version"]
        == "2026.07.30.220000"
    )
    assert receipts["submissions"][row["submission_id"]]["promoted_approval_revision"] == 1

    corrected_payload = _payload()
    corrected_payload["fullName"] = "Corrected after release"
    corrected = _export(corrected_payload, approval_revision=2)
    materialize_approved_submissions([corrected], output_dir=manual_dir)
    corrected_bytes = json.dumps(
        {
            "label_record": {
                "source_record_id": row["submission_id"],
                "lineage_key": "pharmaguide_submission:" + row["submission_id"],
                "approval_revision": 2,
                "approval_payload_sha256": corrected["payload_sha256"],
            }
        }
    ).encode()
    (detail_blobs / f"{product_id}.json").write_bytes(corrected_bytes)
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "update products_core set detail_blob_sha256 = ? where dsld_id = ?",
            (hashlib.sha256(corrected_bytes).hexdigest(), product_id),
        )
    assert mark_released_submissions_promoted(
        output_dir=manual_dir,
        catalog_db=catalog,
        detail_blobs_dir=detail_blobs,
        rpc=lambda name, payload: calls.append((name, payload)) or True,
    ) == [row["submission_id"]]
    assert calls[-1][1]["p_approval_revision"] == 2
    assert calls[-1][1]["p_payload_sha256"] == corrected["payload_sha256"]


def test_existing_dsld_identity_does_not_falsely_prove_correction_release(
    tmp_path: Path,
):
    from product_submission_import import (
        SubmissionImportError,
        mark_released_submissions_promoted,
        materialize_approved_submissions,
    )

    manual_dir = tmp_path / "manual"
    row = _export(
        kind="label_mismatch",
        normalized_upc=None,
        target_dsld_id="278454",
    )
    materialize_approved_submissions([row], output_dir=manual_dir)
    catalog = tmp_path / "pharmaguide_core.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "create table products_core "
            "(dsld_id text primary key, detail_blob_sha256 text)"
        )
        connection.execute("create table export_manifest (key text, value text)")
        connection.execute(
            "insert into export_manifest values ('db_version', '2026.07.30.220000')"
        )
    detail_blobs = tmp_path / "detail_blobs"
    detail_blobs.mkdir()
    detail_bytes = json.dumps(
        {
            "label_record": {
                "source_record_id": "278454",
                "lineage_key": "dsld:278454",
            }
        }
    ).encode()
    (detail_blobs / "278454.json").write_bytes(detail_bytes)
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "insert into products_core values (?, ?)",
            ("278454", hashlib.sha256(detail_bytes).hexdigest()),
        )

    calls: list[tuple[str, dict]] = []
    with pytest.raises(SubmissionImportError, match="does not carry submission"):
        mark_released_submissions_promoted(
            output_dir=manual_dir,
            catalog_db=catalog,
            detail_blobs_dir=detail_blobs,
            rpc=lambda name, payload: calls.append((name, payload)) or True,
        )
    assert calls == []


def test_release_train_marks_receipts_only_after_cloud_and_bundle_steps():
    release = Path("scripts/release_full.sh").read_text(encoding="utf-8")

    cloud_sync = release.index("scripts/sync_to_supabase.py")
    bundle_parity = release.index('"Flutter bundle parity"')
    promotion = release.index("product_submission_import.py --mark-promoted")
    assert promotion > cloud_sync
    assert promotion > bundle_parity


def test_release_train_runs_approved_submissions_through_existing_pipeline():
    release = Path("scripts/release_full.sh").read_text(encoding="utf-8")

    fetch = release.index("product_submission_import.py --fetch")
    pipeline = release.index(
        'scripts/run_pipeline.py --raw-dir "$SUBMISSION_OUTPUT_DIR"'
    )
    snapshot = release.index("bash scripts/rebuild_dashboard_snapshot.sh")

    assert fetch < pipeline < snapshot
    assert "--strict-release-gates" in release[pipeline : pipeline + 500]
    assert "scripts/score_products_v4.py" not in release[fetch:snapshot]


def test_release_train_refreshes_submissions_after_reference_data_change():
    release = Path("scripts/release_full.sh").read_text(encoding="utf-8")

    freshness_start = release.index("submission_pipeline_needs_run() {")
    freshness_function = release[
        freshness_start : release.index("\n}\n", freshness_start)
    ]
    assert "pipeline_freshness.py" in freshness_function
    assert "check-stage-manifests" in freshness_function
    assert 'SUBMISSION_ENRICH_MANIFEST=' in release


@pytest.mark.parametrize("explicit_hold", [False, True])
def test_submission_image_copy_distinguishes_review_hold_from_lost_catalog_row(tmp_path, explicit_hold):
    from product_submission_import import copy_approved_product_images, materialize_approved_submissions

    manual_dir = tmp_path / "manual"
    materialize_approved_submissions([_export()], output_dir=manual_dir)
    catalog = tmp_path / "pharmaguide_core.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute("CREATE TABLE products_core (dsld_id TEXT, image_thumbnail_url TEXT)")
    if explicit_hold:
        (tmp_path / "export_manifest.json").write_text(json.dumps({
            "excluded_by_gate": [{
                "dsld_id": "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11",
                "error": "review_queue: NOT_SCORED",
            }],
        }))
    result = copy_approved_product_images(
        output_dir=manual_dir, catalog_db=catalog, product_images_dir=tmp_path / "images",
        rpc=lambda *_: pytest.fail("A missing catalog row must not fetch an image"),
    )
    assert result == {"copied": 0, "failed": 0 if explicit_hold else 1, "skipped": 1 if explicit_hold else 0}


def test_release_train_registers_submission_images_before_cloud_sync():
    release = Path("scripts/release_full.sh").read_text(encoding="utf-8")

    snapshot = release.index("bash scripts/rebuild_dashboard_snapshot.sh")
    copy_images = release.index("product_submission_import.py --copy-images")
    preflight = release.index('scripts/sync_to_supabase.py" --preflight-only')
    # A read-only access probe is not an upload. Match the actual candidate
    # argument, covering both dry-run and live upload branches in their order.
    cloud_sync = release.index('scripts/sync_to_supabase.py "$DIST_DIR"')

    assert preflight < snapshot < copy_images < cloud_sync


def test_dashboard_snapshot_applies_reviewed_submission_corrections_last():
    snapshot = Path("scripts/rebuild_dashboard_snapshot.sh").read_text(
        encoding="utf-8"
    )

    enriched_append = snapshot.index('ENR+=("$SUBMISSION_ENRICHED_DIR")')
    scored_append = snapshot.index('SCR+=("$SUBMISSION_SCORED_DIR")')
    build = snapshot.index('--enriched-dir "${ENR[@]}"')

    assert enriched_append < build
    assert scored_append < build


# ---------------------------------------------------------------------------
# A barcode already in the catalog: correction or separate edition
#
# Same barcode, different label, two different truths. Correcting rewrites the
# catalog record in place and keeps its id, so a stack that points at it keeps
# the same product. An edition leaves that record alone and becomes its own
# product, so nobody's bottle silently changes contents.
# ---------------------------------------------------------------------------


def test_a_correction_rewrites_the_catalog_record_it_names():
    from product_submission_import import build_manual_label

    label = build_manual_label(_export(correction_target_dsld_id="178392"))

    assert label["id"] == "178392"
    assert label["label_record_metadata"]["lineage_key"] == "dsld:178392"
    # The submission stays the source record, as it does for every manual label.
    assert label["label_record_metadata"]["source_record_id"] == (
        "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"
    )
    assert "edition_of_dsld_id" not in label["label_record_metadata"]


def test_an_edition_becomes_its_own_product_and_names_its_sibling():
    from product_submission_import import build_manual_label

    label = build_manual_label(_export(edition_of_dsld_id="178392"))

    assert label["id"] == "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11"
    assert label["label_record_metadata"]["lineage_key"] == (
        "pharmaguide_submission:018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"
    )
    assert label["label_record_metadata"]["edition_of_dsld_id"] == "178392"


def test_a_submission_cannot_be_a_correction_and_an_edition_at_once():
    from product_submission_import import (
        SubmissionImportError,
        build_manual_label,
    )

    with pytest.raises(SubmissionImportError):
        build_manual_label(
            _export(correction_target_dsld_id="178392", edition_of_dsld_id="1")
        )


@pytest.mark.parametrize("field", ["correction_target_dsld_id", "edition_of_dsld_id"])
def test_a_catalog_relation_must_name_a_catalog_id(field):
    from product_submission_import import (
        SubmissionImportError,
        build_manual_label,
    )

    for value in ("PG_SUB_1", "17-8392", "", "178392x", 178392, None if False else "1e5"):
        with pytest.raises(SubmissionImportError):
            build_manual_label(_export(**{field: value}))
    # Surrounding whitespace is normalized away, as every other id on this
    # path is: the value still has to be a catalog id.
    assert build_manual_label(_export(**{field: " 178392 "}))


@pytest.mark.parametrize("field", ["correction_target_dsld_id", "edition_of_dsld_id"])
def test_a_correction_submission_carries_no_second_relation(field):
    from product_submission_import import (
        SubmissionImportError,
        build_manual_label,
    )

    with pytest.raises(SubmissionImportError):
        build_manual_label(_export(
            kind="label_mismatch", target_dsld_id="299239", **{field: "178392"},
        ))


# A barcode may name more than one product, but only by a reviewed decision.
# The collision rule exists to stop the same product being imported twice
# under two ids; an edition or a correction is the reviewer saying, with a
# recorded catalog match behind it, that a second record on this barcode is
# intended.

_EDITION_ID = "11111111-2222-4333-8444-555555555555"
_CORRECTION_ID = "22222222-3333-4444-8555-666666666666"


def test_an_edition_may_share_a_barcode_with_an_imported_product(tmp_path):
    from product_submission_import import materialize_approved_submissions

    materialize_approved_submissions([_export()], output_dir=tmp_path)
    result = materialize_approved_submissions(
        [_export(submission_id=_EDITION_ID, edition_of_dsld_id="178392")],
        output_dir=tmp_path,
    )

    assert result.imported_submission_ids == [_EDITION_ID]
    assert (tmp_path / "PG_SUB_11111111222243338444555555555555.json").exists()


def test_an_imported_product_remains_replayable_after_an_edition(tmp_path):
    from product_submission_import import materialize_approved_submissions

    original = _export()
    edition = _export(submission_id=_EDITION_ID, edition_of_dsld_id="178392")
    materialize_approved_submissions([original, edition], output_dir=tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = materialize_approved_submissions([original, edition], output_dir=tmp_path)
    assert result.imported_submission_ids == []
    assert result.already_imported_submission_ids == [original['submission_id'], _EDITION_ID]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_a_correction_may_follow_an_edition_on_the_same_barcode(tmp_path):
    from product_submission_import import materialize_approved_submissions

    materialize_approved_submissions(
        [_export(submission_id=_EDITION_ID, edition_of_dsld_id="178392")],
        output_dir=tmp_path,
    )
    result = materialize_approved_submissions(
        [_export(submission_id=_CORRECTION_ID, correction_target_dsld_id="178392")],
        output_dir=tmp_path,
    )

    assert result.imported_submission_ids == [_CORRECTION_ID]
    assert (tmp_path / "178392.json").exists()


def test_an_unrelated_second_product_on_a_barcode_is_still_a_collision(tmp_path):
    from product_submission_import import (
        SubmissionImportError,
        materialize_approved_submissions,
    )

    materialize_approved_submissions(
        [_export(submission_id=_EDITION_ID, edition_of_dsld_id="178392")],
        output_dir=tmp_path,
    )
    with pytest.raises(SubmissionImportError, match="already owned"):
        materialize_approved_submissions(
            [_export(submission_id=_CORRECTION_ID)], output_dir=tmp_path,
        )


def test_reviewed_submission_sources_stay_byte_bound_to_approval():
    # Revision provenance migrations are receipt-bound; label facts and approvals stay unchanged.
    approved_hashes = {
        "PG_SUB_1A28723DBDAF4AC1897AA5FF156FACA1": "6b2854a01c924b05ce1744f1a79ee01173c9e94027152e2a4e608b4f678dd9d2",
        "PG_SUB_21B7F5A0D3414040948D242FB03DD01B": "12f929950e41c377ebfd88eee19ab75068ddafa502b744f4f9f36af8cc9d60b5",
        "PG_SUB_2E7000A890174F10BAA7870FE5EAD7F3": "ed7628016a7cd22477ce118062619e858483a03ca913259f0248b989c1005e55",
        "PG_SUB_3D5877FE66FA423F9AC3C90EE52EF8CA": "69135753f77609739f74b4a7cc49401dc19187320fc28cd0af86f6b597abb45d",
        "PG_SUB_4ACB39B94D394C19815F63B0A783EF08": "1772953c57fe21532d6cefdf87ca2e6a2a0a4a4b41b3a8ee05ace61d27c902d4",
        "PG_SUB_4D246163F6CD468CA82B5E023468B9C1": "3d9b34abecea2f0f581eea8c2e3b0a79ac129aaaacab2edc7c11994c1aef2c96",
        "PG_SUB_5E4D136A84A8485F98E1F3C0BCF49A73": "175287980db228bccace2f32bc44b6ab7f32a484ffc1917bba6b86f4299a061d",
        "PG_SUB_5EB9F9D6F38C4648A6560B489E0E4916": "e4ab80f78cb72f5e5bb9a121758dc6be951cec977e7f405ecf7e66e3bc095e4c",
        "PG_SUB_6AFDA9855BFA449BB235FCFE6ECBAF96": "28e223146e594b8beaaa959d1bd4199b419897df4c980397786d16707461b066",
        "PG_SUB_8F025E8FFB164793B3B68B15EED2CD31": "df781762a363a0ce96eebe31b8a4aacbcaae13bfb0af46ac5da76e18eb3e784f"
    }
    root = Path(__file__).resolve().parents[2] / "manual_labels/product_submissions"
    for product_id, expected in approved_hashes.items():
        assert hashlib.sha256((root / f"{product_id}.json").read_bytes()).hexdigest() == expected, product_id


def test_reviewed_physical_state_preserves_approved_source_and_fails_closed():
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = {"id": "fixture", "ingredientRows": [], "statements": [],
           "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "tablet"}],
           "physicalState": {"name": "Tablet"}}
    original = deepcopy(raw)
    source = {k: raw.get(k) for k in ("ingredientRows", "servingSizes", "statements")}
    digest = hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False,separators=(",", ":")).encode()).hexdigest()
    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_corrections_by_dsld_id["fixture"] = {"serving_basis_correction": {
        "raw_source_sha256": digest, "serving_sizes": deepcopy(raw["servingSizes"]),
        "raw_product_fields": {"physicalState": {"name": "Tablet"}},
        "corrected_product_fields": {"physicalState": {"name": "Tablet or Pill", "langualCodeDescription": "Tablet or Pill"}},
    }}
    result = normalizer._apply_reviewed_serving_basis(raw)
    assert result["physicalState"]["langualCodeDescription"] == "Tablet or Pill"
    assert raw == original
    raw["physicalState"]["name"] = "Liquid"
    with pytest.raises(ValueError, match="metadata changed"):
        normalizer._apply_reviewed_serving_basis(raw)

@pytest.mark.parametrize('promoted', [False, True])
def test_authoritative_revision_supersedes_unpublished_and_recovers_receipt(tmp_path, monkeypatch, promoted):
    import product_submission_import as importer
    row = _export()
    result = importer.materialize_approved_submissions([row], output_dir=tmp_path)
    receipt_path = tmp_path / importer.RECEIPT_FILE
    if promoted:
        receipts = json.loads(receipt_path.read_text())
        receipts['submissions'][row['submission_id']].update(promoted_catalog_version='old', promoted_approval_revision=1)
        receipt_path.write_text(json.dumps(receipts))
    payload = _payload()
    payload['fullName'] = 'Revision two'
    newer = _export(payload, approval_revision=2)
    old_write = importer._atomic_write_text
    def crash(path, content):
        if path == receipt_path:
            raise RuntimeError('receipt crash')
        old_write(path, content)
    monkeypatch.setattr(importer, '_atomic_write_text', crash)
    with pytest.raises(RuntimeError, match='receipt crash'):
        importer.materialize_approved_submissions([newer], output_dir=tmp_path, authoritative=True)
    monkeypatch.setattr(importer, '_atomic_write_text', old_write)
    importer.materialize_approved_submissions([newer], output_dir=tmp_path, authoritative=True)
    assert json.loads(result.output_paths[0].read_text())['fullName'] == 'Revision two'
    if promoted:
        importer.materialize_approved_submissions([], output_dir=tmp_path, authoritative=True)
        assert json.loads(result.output_paths[0].read_text())['fullName'] == 'Example Vitamin D3'


def test_authoritative_supersession_preserves_promoted_label_through_three_revisions(tmp_path):
    import product_submission_import as importer
    first = _export()
    result = importer.materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / importer.RECEIPT_FILE
    receipts = json.loads(receipt_path.read_text())
    receipts['submissions'][first['submission_id']].update(promoted_catalog_version='old', promoted_approval_revision=1)
    receipt_path.write_text(json.dumps(receipts))
    for revision in (2, 3):
        payload = _payload()
        payload['fullName'] = f'Revision {revision}'
        importer.materialize_approved_submissions([_export(payload, approval_revision=revision)], output_dir=tmp_path, authoritative=True)
    with pytest.raises(importer.SubmissionImportError, match='older approval'):
        importer.materialize_approved_submissions([first], output_dir=tmp_path, authoritative=True)
    changed = _payload()
    changed['fullName'] = 'same revision mutation'
    with pytest.raises(importer.SubmissionImportError, match='same approval revision'):
        importer.materialize_approved_submissions([_export(changed, approval_revision=3)], output_dir=tmp_path, authoritative=True)
    result.output_paths[0].write_text('manual mutation')
    with pytest.raises(importer.SubmissionImportError, match='manual label changed'):
        importer.materialize_approved_submissions([_export(changed, approval_revision=4)], output_dir=tmp_path, authoritative=True)

@pytest.mark.parametrize('promoted', [False, True])
def test_interrupted_revision_can_be_superseded_by_later_authoritative_approval(tmp_path, monkeypatch, promoted):
    import product_submission_import as importer
    first = _export()
    result = importer.materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / importer.RECEIPT_FILE
    if promoted:
        receipts = json.loads(receipt_path.read_text())
        receipts['submissions'][first['submission_id']].update(promoted_catalog_version='old', promoted_approval_revision=1)
        receipt_path.write_text(json.dumps(receipts))
    payload = _payload()
    payload['fullName'] = 'Interrupted revision two'
    second = _export(payload, approval_revision=2)
    write = importer._atomic_write_text
    def interrupt_after_label(path, content):
        write(path, content)
        if path == result.output_paths[0]:
            raise RuntimeError('crash after label')
    monkeypatch.setattr(importer, '_atomic_write_text', interrupt_after_label)
    with pytest.raises(RuntimeError, match='crash after label'):
        importer.materialize_approved_submissions([second], output_dir=tmp_path, authoritative=True)
    monkeypatch.setattr(importer, '_atomic_write_text', write)
    payload['fullName'] = 'Latest revision three'
    importer.materialize_approved_submissions([_export(payload, approval_revision=3)], output_dir=tmp_path, authoritative=True)
    assert json.loads(result.output_paths[0].read_text())['fullName'] == 'Latest revision three'
    if promoted:
        importer.materialize_approved_submissions([], output_dir=tmp_path, authoritative=True)
        assert json.loads(result.output_paths[0].read_text())['fullName'] == 'Example Vitamin D3'

@pytest.mark.parametrize('phase', ['before_label', 'after_label'])
@pytest.mark.parametrize('change', ['rollback', 'same_revision', 'manual'])
def test_pending_import_retains_revision_and_manual_edit_fences(tmp_path, monkeypatch, phase, change):
    import product_submission_import as importer
    first = _export()
    result = importer.materialize_approved_submissions([first], output_dir=tmp_path)
    output = result.output_paths[0]
    payload = _payload()
    payload['fullName'] = 'Second approved name'
    second = _export(payload, approval_revision=2)
    write = importer._atomic_write_text
    def interrupt(path, content):
        if path == output and phase == 'before_label':
            raise RuntimeError('interrupted')
        write(path, content)
        if path == output:
            raise RuntimeError('interrupted')
    monkeypatch.setattr(importer, '_atomic_write_text', interrupt)
    with pytest.raises(RuntimeError):
        importer.materialize_approved_submissions([second], output_dir=tmp_path, authoritative=True)
    monkeypatch.setattr(importer, '_atomic_write_text', write)
    if change == 'rollback':
        attempted, message = first, 'older approval revision'
    elif change == 'same_revision':
        payload['fullName'] = 'Mutated same approval'
        attempted, message = _export(payload, approval_revision=2), 'same approval revision'
    else:
        output.write_text('unexplained manual file change')
        attempted, message = second, 'manual label changed'
    with pytest.raises(importer.SubmissionImportError, match=message):
        importer.materialize_approved_submissions([attempted], output_dir=tmp_path, authoritative=True)

@pytest.mark.parametrize('phase', ['before_label', 'after_label'])
@pytest.mark.parametrize('tamper', [False, True])
def test_cross_submission_pending_import_recovers_only_verified_owner_bytes(tmp_path, monkeypatch, phase, tamper):
    import product_submission_import as importer
    first = _export(kind='label_mismatch', normalized_upc=None, target_dsld_id='278454')
    importer.materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / importer.RECEIPT_FILE
    receipts = json.loads(receipt_path.read_text())
    receipts['submissions'][first['submission_id']].update(promoted_catalog_version='old', promoted_approval_revision=1)
    receipt_path.write_text(json.dumps(receipts))
    payload = _payload()
    payload['fullName'] = 'Replacement submission'
    replacement = _export(payload, kind='label_mismatch', normalized_upc=None, target_dsld_id='278454', submission_id='028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22')
    output = tmp_path / '278454.json'
    write = importer._atomic_write_text
    def interrupt(path, content):
        if path == output and phase == 'before_label':
            raise RuntimeError('interrupted')
        write(path, content)
        if path == output:
            raise RuntimeError('interrupted')
    monkeypatch.setattr(importer, '_atomic_write_text', interrupt)
    with pytest.raises(RuntimeError):
        importer.materialize_approved_submissions([replacement], output_dir=tmp_path, authoritative=True)
    monkeypatch.setattr(importer, '_atomic_write_text', write)
    if tamper:
        output.write_text('unexplained file change')
        with pytest.raises(importer.SubmissionImportError, match='manual label changed'):
            importer.materialize_approved_submissions([replacement], output_dir=tmp_path, authoritative=True)
        return
    importer.materialize_approved_submissions([replacement], output_dir=tmp_path, authoritative=True)
    assert json.loads(output.read_text())['fullName'] == 'Replacement submission'
    importer.materialize_approved_submissions([first], output_dir=tmp_path, authoritative=True)
    assert json.loads(output.read_text())['fullName'] == 'Example Vitamin D3'


def test_promoted_legacy_privacy_rewrite_freezes_before_label_receipt_crash(tmp_path, monkeypatch):
    import product_submission_import as importer
    original = importer.build_manual_label
    def legacy(row):
        label = original(row)
        label['manual_product_provenance']['reviewer_record_id'] = row['reviewer_id']
        return label
    row = _export()
    monkeypatch.setattr(importer, 'build_manual_label', legacy)
    result = importer.materialize_approved_submissions([row], output_dir=tmp_path)
    output = result.output_paths[0]
    old_bytes = output.read_bytes()
    receipt_path = tmp_path / importer.RECEIPT_FILE
    receipts = json.loads(receipt_path.read_text())
    receipts['submissions'][row['submission_id']].update(promoted_catalog_version='old', promoted_approval_revision=1)
    receipt_path.write_text(json.dumps(receipts))
    monkeypatch.setattr(importer, 'build_manual_label', original)
    write = importer._atomic_write_text
    def interrupt(path, content):
        write(path, content)
        if path == output:
            raise RuntimeError('crash after label')
    monkeypatch.setattr(importer, '_atomic_write_text', interrupt)
    with pytest.raises(RuntimeError):
        importer.materialize_approved_submissions([row], output_dir=tmp_path)
    frozen = tmp_path / importer.PROMOTED_HISTORY_DIR / row['submission_id'] / '1.json'
    assert frozen.read_bytes() == old_bytes
    monkeypatch.setattr(importer, '_atomic_write_text', write)
    importer.materialize_approved_submissions([row], output_dir=tmp_path)
    assert row['reviewer_id'] not in output.read_text()

    corrected = _payload()
    corrected['fullName'] = 'Later correction'
    importer.materialize_approved_submissions([_export(corrected, approval_revision=2)], output_dir=tmp_path, authoritative=True)
    assert frozen.read_bytes() == old_bytes
    importer.materialize_approved_submissions([], output_dir=tmp_path, authoritative=True)
    assert output.read_bytes() == old_bytes


def _v2_export(**overrides):
    identity = {
        'observed': {'observed_code': 'X002FLZ3X7', 'code_type': 'other',
                     'issuer': None, 'brandName': 'Example Labs',
                     'fullName': 'Example Vitamin D3', 'listing_url': None, 'no_code': False},
        'decision': {'code_type': 'amazon_fnsku', 'issuer': 'Amazon',
                     'verified_gtin': None, 'package': '60 capsules',
                     'reason': 'Complete package photographs checked against current candidates.'},
        'identity_method': 'label_review', 'outcome': 'new_product_verified',
        'matched_dsld_id': None, 'correction_target_dsld_id': None,
        'edition_of_dsld_id': None, 'evidence_revision': 1,
        'evidence_manifest_sha256': 'a' * 64,
        'match_check_id': 42,
    }
    return _export({'label': _payload(), 'identity': identity},
                   schema_version='manual_label_v2', normalized_upc=None, **overrides)


def test_v2_private_identity_is_validated_then_excluded_from_public_label():
    from product_submission_import import build_manual_label
    label = build_manual_label(_v2_export())
    assert label['upcSku'] == ''
    assert label['id'].startswith('PG_SUB_')
    public = json.dumps(label)
    for private in ('X002FLZ3X7', 'amazon_fnsku', 'Complete package photographs', 'identity_method'):
        assert private not in public


def test_v2_verified_gtin_cannot_contradict_export_null():
    from product_submission_import import build_manual_label, SubmissionImportError
    row = _v2_export()
    envelope = json.loads(row['approved_payload_canonical'])
    envelope['identity']['decision']['verified_gtin'] = '050428381397'
    row['approved_payload_canonical'] = _canonical(envelope)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    with pytest.raises(SubmissionImportError):
        build_manual_label(row)


def test_existing_submission_correction_preserves_original_lineage():
    from product_submission_import import build_manual_label
    target = 'PG_SUB_11111111222233334444555555555555'
    label = build_manual_label(_export(correction_target_dsld_id=target))
    assert label['id'] == target
    assert label['label_record_metadata']['lineage_key'] == 'pharmaguide_submission:11111111-2222-3333-4444-555555555555'


def test_v2_two_unrelated_null_gtin_submissions_have_no_blank_collision(tmp_path):
    from product_submission_import import materialize_approved_submissions
    first = _v2_export()
    second = _v2_export(submission_id='11111111-2222-4333-8444-555555555555')
    materialize_approved_submissions([first, second], output_dir=tmp_path)
    labels = list(tmp_path.glob('PG_SUB_*.json'))
    assert len(labels) == 2
    assert all(json.loads(path.read_text())['upcSku'] == '' for path in labels)


@pytest.mark.parametrize('change', ['extra_private', 'observed_contradiction', 'bad_match', 'bad_url', 'unresolved'])
def test_v2_rejects_malformed_private_identity(change):
    from product_submission_import import build_manual_label, SubmissionImportError
    row = _v2_export()
    envelope = json.loads(row['approved_payload_canonical'])
    identity = envelope['identity']
    if change == 'extra_private': envelope['private'] = 'leak'
    elif change == 'observed_contradiction': identity['observed']['no_code'] = True
    elif change == 'bad_match': identity['match_check_id'] = True
    elif change == 'bad_url': identity['observed']['listing_url'] = 'file:///etc/passwd'
    elif change == 'unresolved': identity['outcome'] = 'identity_ambiguous'
    row['approved_payload_canonical'] = _canonical(envelope)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    with pytest.raises(SubmissionImportError): build_manual_label(row)


def test_no_gtin_label_traverses_real_clean_enrich_score_and_public_export():
    from product_submission_import import build_manual_label
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from score_supplements_v4 import score_product_v4
    from build_final_db import build_core_row, build_detail_blob, PRODUCTS_CORE_COLUMNS
    source = _v2_export()
    label = build_manual_label(source)
    cleaned = EnhancedDSLDNormalizer().normalize_product(label)
    enriched, _ = SupplementEnricherV3(config_path=str(Path(__file__).parents[1] / 'config/enrichment_config.json')).enrich_product(cleaned)
    enriched['dsld_id'] = label['id']
    scored = score_product_v4(enriched)
    blob = build_detail_blob(enriched, scored)
    core = dict(zip(PRODUCTS_CORE_COLUMNS, build_core_row(enriched, scored, '2026-10-26T00:00:00Z', detail_blob=blob)))
    assert core['dsld_id'] == label['id']
    assert not core['upc_sku']
    assert core['product_name'] == 'Example Vitamin D3'
    assert core['brand_name'] == 'Example Labs'
    public = json.dumps({'core': core, 'blob': blob})
    assert 'X002FLZ3X7' not in public
    assert 'Complete package photographs' not in public
    assert blob['label_record']['approval_payload_sha256'] == source['payload_sha256']


@pytest.mark.parametrize('method,outcome,matched,relation,kind', [
    ('label_review', 'catalog_match', None, None, 'missing_product'),
    ('label_review', 'catalog_match', '123', None, 'missing_product'),
    ('label_review', 'dsld_match', '123', None, 'missing_product'),
    ('label_review', 'dsld_match', '123', '123', 'missing_product'),
    ('gtin', 'new_product_verified', None, None, 'missing_product'),
    ('label_review', 'no_match_verified', None, None, 'missing_product'),
    ('gtin', 'no_match_verified', '123', None, 'missing_product'),
    ('gtin', 'no_match_verified', '123', '123', 'missing_product'),
    ('label_review', 'new_product_verified', None, None, 'label_mismatch'),
    ('gtin', 'no_match_verified', None, None, 'label_mismatch'),
])
def test_v2_rejects_contradictory_identity_decision_table(method, outcome, matched, relation, kind):
    from product_submission_import import build_manual_label, SubmissionImportError
    row = _v2_export(kind=kind)
    value = json.loads(row['approved_payload_canonical'])
    identity = value['identity']
    identity.update(identity_method=method, outcome=outcome, matched_dsld_id=matched)
    if relation:
        row['correction_target_dsld_id'] = relation
        identity['correction_target_dsld_id'] = relation
    if kind == 'label_mismatch': row['target_dsld_id'] = '123'
    if method == 'gtin' or outcome == 'no_match_verified':
        row['normalized_upc'] = '050428381397'
        identity['decision']['verified_gtin'] = row['normalized_upc']
    row['approved_payload_canonical'] = _canonical(value)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    with pytest.raises(SubmissionImportError): build_manual_label(row)


@pytest.mark.parametrize('kind,relation', [('missing_product', 'correction_target_dsld_id'), ('missing_product', 'edition_of_dsld_id'), ('label_mismatch', 'target_dsld_id')])
def test_v2_explicit_catalog_associations_preserve_the_selected_product(kind, relation):
    from product_submission_import import build_manual_label
    target = 'PG_SUB_11111111222243338444555555555555'
    row = _v2_export(kind=kind, **{relation: target})
    value = json.loads(row['approved_payload_canonical'])
    identity = value['identity']
    identity.update(outcome='catalog_match', matched_dsld_id=target)
    if relation != 'target_dsld_id': identity[relation] = target
    row['approved_payload_canonical'] = _canonical(value)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    label = build_manual_label(row)
    if relation == 'edition_of_dsld_id':
        assert label['id'] != target
        assert label['label_record_metadata']['edition_of_dsld_id'] == target
    else:
        assert label['id'] == target
        assert label['label_record_metadata']['lineage_key'] == 'pharmaguide_submission:11111111-2222-4333-8444-555555555555'


def test_v2_new_product_without_gtin_decision_cannot_skip_exact_check_after_learning_gtin():
    from product_submission_import import build_manual_label, SubmissionImportError
    row = _v2_export()
    value = json.loads(row['approved_payload_canonical'])
    row['normalized_upc'] = value['identity']['decision']['verified_gtin'] = '050428381397'
    row['approved_payload_canonical'] = _canonical(value)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    with pytest.raises(SubmissionImportError): build_manual_label(row)


@pytest.mark.parametrize('section,field', [
    ('observed', 'observed_code'), ('observed', 'issuer'),
    ('observed', 'brandName'), ('observed', 'fullName'), ('observed', 'listing_url'),
    ('decision', 'issuer'), ('decision', 'package'), ('decision', 'reason'),
])
def test_v2_private_identity_rejects_every_c0_and_c1_control(section, field):
    from product_submission_import import build_manual_label, SubmissionImportError
    for codepoint in (*range(32), *range(127, 160)):
        row = _v2_export()
        value = json.loads(row['approved_payload_canonical'])
        value['identity'][section][field] = 'X' + chr(codepoint) + 'Y'
        row['approved_payload_canonical'] = _canonical(value)
        row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
        with pytest.raises(SubmissionImportError): build_manual_label(row)


@pytest.mark.parametrize('section,field', [('observed', 'issuer'), ('observed', 'listing_url'), ('decision', 'issuer')])
@pytest.mark.parametrize('blank', ['', ' ', '\u00a0'])
def test_v2_frozen_optional_identity_metadata_requires_canonical_null(section, field, blank):
    from product_submission_import import build_manual_label, SubmissionImportError
    row = _v2_export()
    value = json.loads(row['approved_payload_canonical'])
    value['identity'][section][field] = blank
    row['approved_payload_canonical'] = _canonical(value)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    with pytest.raises(SubmissionImportError): build_manual_label(row)


@pytest.mark.parametrize('reason', [None, '', 'four'])
def test_v2_gtin_decision_requires_substantive_reviewed_reason(reason):
    from product_submission_import import build_manual_label, SubmissionImportError
    row = _v2_export()
    value = json.loads(row['approved_payload_canonical'])
    value['identity'].update(identity_method='gtin', outcome='no_match_verified')
    value['identity']['decision'].update(verified_gtin='050428381397', package=None, reason=reason)
    row['normalized_upc'] = '050428381397'
    row['approved_payload_canonical'] = _canonical(value)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    with pytest.raises(SubmissionImportError): build_manual_label(row)


def test_v2_gtin_review_accepts_reviewed_reason_without_package():
    from product_submission_import import build_manual_label
    row = _v2_export()
    value = json.loads(row['approved_payload_canonical'])
    value['identity'].update(identity_method='gtin', outcome='no_match_verified')
    value['identity']['decision'].update(verified_gtin='050428381397', package=None, reason='Reviewer checked the manufacturer barcode and current exact candidates.')
    row['normalized_upc'] = '050428381397'
    row['approved_payload_canonical'] = _canonical(value)
    row['payload_sha256'] = hashlib.sha256(row['approved_payload_canonical'].encode()).hexdigest()
    assert build_manual_label(row)['upcSku'] == '050428381397'


@pytest.mark.parametrize("product_id, expected", [
    # "Adults take 2 capsules once daily"; Serving Size 2 capsules -> one serving a day.
    ("PG_SUB_8800C6CBB6F14B79A73D599B126C8636", [(1, 1)]),
    # "SUGGESTED USE: Take one softgel daily with food."
    ("PG_SUB_F580FBD60E574699B47D0982663F17DD", [(1, 1)]),
    # "Directions: Adults, take one softgel and one tablet daily with food."
    ("PG_SUB_7283A83B3FC7467F808C02667CCBFE06", [(1, 1), (1, 1)]),
])
def test_printed_daily_directions_reach_clean_as_label_sourced(product_id, expected):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    root = Path(__file__).resolve().parents[2] / "manual_labels/product_submissions"
    raw = json.loads((root / f"{product_id}.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    servings = sorted(cleaned["servingSizes"], key=lambda s: s["order"])
    assert [s["dailyServingsSource"] for s in servings] == ["label"] * len(expected)
    assert [(s["minDailyServings"], s["maxDailyServings"]) for s in servings] == expected


# ---------------------------------------------------------------------------
# Receipts written before the revision-aware importer (October 26) carry no
# approval payload hash. Their approvals are promoted and still verifiable on
# the server, which derives the exact revision and hash itself. The release of
# 2026-10-31 crashed on the first such receipt with a bare KeyError.
# ---------------------------------------------------------------------------


def _legacy_receipts(manual_dir: Path, *, promoted: bool) -> tuple[str, str, str, str]:
    from product_submission_import import RECEIPT_FILE, materialize_approved_submissions

    row = _export()
    materialize_approved_submissions([row], output_dir=manual_dir)
    legacy_submission = "35e0bd33-74bf-494b-80fe-abe87fc559e7"
    legacy_product = "PG_SUB_35E0BD3374BF494B80FEABE87FC559E7"
    receipt_path = manual_dir / RECEIPT_FILE
    receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
    legacy = {
        "approval_revision": 1,
        "label_sha256": "0" * 64,
        "output_file": f"{legacy_product}.json",
        "product_id": legacy_product,
        "promoted_approval_revision": 1 if promoted else 0,
        "upc": "0860340001620",
    }
    if promoted:
        legacy["promoted_catalog_version"] = "2026.09.03.151135"
    receipts["submissions"][legacy_submission] = legacy
    receipt_path.write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return row["submission_id"], "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11", legacy_submission, legacy_product


def _image_catalog(tmp_path: Path, product_ids: list[str]) -> tuple[Path, Path, bytes, str]:
    catalog = tmp_path / "pharmaguide_core.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "create table products_core (dsld_id text primary key, image_thumbnail_url text)"
        )
        connection.executemany(
            "insert into products_core values (?, null)", [(pid,) for pid in product_ids]
        )
    (tmp_path / "export_manifest.json").write_text(json.dumps({"db_version": "release-3"}))
    image_dir = tmp_path / "product_images"
    image_dir.mkdir()
    (image_dir / "product_image_index.json").write_text("{}\n")
    source = io.BytesIO()
    Image.new("RGB", (900, 600), "#183b3f").save(source, format="PNG")
    source_bytes = source.getvalue()
    return catalog, image_dir, source_bytes, hashlib.sha256(source_bytes).hexdigest()


def test_promoted_legacy_receipt_without_payload_hash_uses_server_derived_image_lookup(tmp_path):
    from product_submission_import import RECEIPT_FILE, copy_approved_product_images

    manual_dir = tmp_path / "manual"
    submission_id, product_id, legacy_submission, legacy_product = _legacy_receipts(
        manual_dir, promoted=True
    )
    catalog, image_dir, source_bytes, source_hash = _image_catalog(
        tmp_path, [product_id, legacy_product]
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def rpc(name: str, payload: dict[str, object]) -> object:
        calls.append((name, payload))
        return [{
            "bucket_id": "product-submission-photos",
            "object_path": f"user/{payload['p_submission_id']}/front.jpg",
            "content_type": "image/png",
            "content_sha256": source_hash,
        }]

    result = copy_approved_product_images(
        output_dir=manual_dir,
        catalog_db=catalog,
        product_images_dir=image_dir,
        rpc=rpc,
        download=lambda bucket, path: source_bytes,
    )

    assert result == {"copied": 2, "failed": 0, "skipped": 0}
    assert calls == [
        # The exact approval is the only acceptable lookup where the receipt
        # recorded it; the legacy promoted approval is derived by the server.
        (
            "get_approved_product_submission_image",
            {
                "p_submission_id": submission_id,
                "p_approval_revision": 1,
                "p_payload_sha256": _export()["payload_sha256"],
            },
        ),
        ("get_approved_product_submission_image", {"p_submission_id": legacy_submission}),
    ]
    receipts = json.loads((manual_dir / RECEIPT_FILE).read_text(encoding="utf-8"))["submissions"]
    assert receipts[legacy_submission]["image_approval_revision"] == 1
    assert receipts[legacy_submission]["image_source_sha256"] == source_hash
    assert "approval_payload_sha256" not in receipts[legacy_submission]
    with sqlite3.connect(catalog) as connection:
        urls = dict(connection.execute("select dsld_id, image_thumbnail_url from products_core"))
    assert urls == {
        product_id: f"product-images/vrelease-3/{product_id}.webp",
        legacy_product: f"product-images/vrelease-3/{legacy_product}.webp",
    }


def test_unpromoted_receipt_without_payload_hash_is_a_named_failure_not_a_crash(tmp_path, capsys):
    from product_submission_import import copy_approved_product_images

    manual_dir = tmp_path / "manual"
    submission_id, product_id, legacy_submission, legacy_product = _legacy_receipts(
        manual_dir, promoted=False
    )
    catalog, image_dir, source_bytes, source_hash = _image_catalog(
        tmp_path, [product_id, legacy_product]
    )
    calls: list[str] = []

    result = copy_approved_product_images(
        output_dir=manual_dir,
        catalog_db=catalog,
        product_images_dir=image_dir,
        rpc=lambda name, payload: calls.append(str(payload["p_submission_id"])) or [{
            "bucket_id": "product-submission-photos",
            "object_path": "user/submission/front.jpg",
            "content_type": "image/png",
            "content_sha256": source_hash,
        }],
        download=lambda bucket, path: source_bytes,
    )

    # An unpromoted approval without its recorded hash cannot be fetched
    # exactly, so it is reported by submission and left for the preflight
    # check to block; the other approved image still ships.
    assert result == {"copied": 1, "failed": 1, "skipped": 0}
    assert calls == [submission_id]
    assert f"{legacy_submission} has no approval payload hash" in capsys.readouterr().err


def test_check_receipts_reports_legacy_promoted_rows_and_refuses_unpromoted_hashless_rows(tmp_path):
    from product_submission_import import SubmissionImportError, check_import_receipts

    manual_dir = tmp_path / "manual"
    _, _, legacy_submission, legacy_product = _legacy_receipts(manual_dir, promoted=True)
    # The legacy label itself must exist and match its receipt like any other.
    (manual_dir / f"{legacy_product}.json").write_bytes(b"")
    receipt_path = manual_dir / ".product_submission_import_receipts"
    receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipts["submissions"][legacy_submission]["label_sha256"] = hashlib.sha256(b"").hexdigest()
    receipt_path.write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert check_import_receipts(output_dir=manual_dir) == {
        "rows": 2, "promoted": 1, "pending": 1, "legacy_without_payload_hash": 1,
    }

    receipts["submissions"][legacy_submission]["promoted_approval_revision"] = 0
    receipt_path.write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(SubmissionImportError, match=f"{legacy_submission}: unpromoted approval has no approval payload hash"):
        check_import_receipts(output_dir=manual_dir)


def test_check_receipts_accepts_a_promoted_owner_whose_file_its_correction_replaced(tmp_path):
    """A correction rewrites the promoted owner's file after freezing the owner's bytes."""
    from product_submission_import import (
        SubmissionImportError, check_import_receipts, materialize_approved_submissions,
    )

    first = _export(kind="label_mismatch", normalized_upc="050428381397", target_dsld_id="278454")
    materialize_approved_submissions([first], output_dir=tmp_path)
    receipt_path = tmp_path / ".product_submission_import_receipts"
    receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipts["submissions"][first["submission_id"]]["promoted_catalog_version"] = "2026.07.30.220000"
    receipt_path.write_text(json.dumps(receipts), encoding="utf-8")
    second_payload = _payload()
    second_payload["fullName"] = "Clinically reviewed second correction"
    second = _export(second_payload, submission_id="028f4c79-7c7e-4c70-9d62-7fc3b9ce6a22",
                     kind="label_mismatch", normalized_upc="050428381397", target_dsld_id="278454")
    materialize_approved_submissions([second], output_dir=tmp_path)

    assert check_import_receipts(output_dir=tmp_path) == {
        "rows": 2, "promoted": 1, "pending": 1, "legacy_without_payload_hash": 0,
    }

    shared = tmp_path / "278454.json"
    current = shared.read_bytes()
    shared.write_bytes(current + b" ")
    with pytest.raises(SubmissionImportError, match="changed after import"):
        check_import_receipts(output_dir=tmp_path)
    shared.write_bytes(current)

    owner = json.loads(receipt_path.read_text(encoding="utf-8"))["submissions"][first["submission_id"]]
    frozen = tmp_path / owner["promoted_label_artifact"]
    frozen_bytes = frozen.read_bytes()
    frozen.write_bytes(frozen_bytes + b" ")
    with pytest.raises(SubmissionImportError, match=f"{first['submission_id']}: label file 278454.json changed"):
        check_import_receipts(output_dir=tmp_path)


def test_check_receipts_refuses_a_label_that_drifted_from_its_receipt(tmp_path):
    from product_submission_import import SubmissionImportError, check_import_receipts, materialize_approved_submissions

    manual_dir = tmp_path / "manual"
    materialize_approved_submissions([_export()], output_dir=manual_dir)
    assert check_import_receipts(output_dir=manual_dir)["pending"] == 1
    label = manual_dir / "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11.json"
    label.write_text(label.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SubmissionImportError, match="changed after import"):
        check_import_receipts(output_dir=manual_dir)
    label.unlink()
    with pytest.raises(SubmissionImportError, match="is missing"):
        check_import_receipts(output_dir=manual_dir)


def test_release_preflight_checks_receipts_before_the_read_only_exit():
    release = Path("scripts/release_full.sh").read_text(encoding="utf-8")
    check = release.index("product_submission_import.py --check-receipts")
    assert release.index('SUBMISSION_RECEIPTS="') < check
    assert check < release.index("if (( PREFLIGHT_ONLY == 1 )); then")
    assert check < release.index("bash scripts/rebuild_dashboard_snapshot.sh")
