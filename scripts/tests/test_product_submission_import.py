from __future__ import annotations

import hashlib
import io
import json
import sqlite3
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


def test_builds_pipeline_owned_identity_and_honest_private_provenance():
    from product_submission_import import build_manual_label

    label = build_manual_label(_export())

    assert label["id"] == "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11"
    assert label["upcSku"] == "050428381397"
    assert label["source_type"] == "external_manual"
    assert label["src"].endswith(label["id"])
    assert label["manual_product_provenance"] == {
        "label_verified_at": "2026-07-30",
        "review_status": "verified",
        "reviewer": "PharmaGuide Clinical Team",
        "reviewer_record_id": "3f276b64-0836-4bea-9453-1c8db4d1f8dd",
        "source_kind": "private_product_submission",
        "source_record_id": "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
    }
    assert label["label_record_metadata"]["source_record_id"] == row_id(
        _export()
    )
    serialized = json.dumps(label).lower()
    assert "user_id" not in serialized
    assert "object_path" not in serialized


def test_generated_private_provenance_passes_canonical_manual_validator():
    import dsld_api_sync
    from product_submission_import import build_manual_label

    # A private user-submission record has no honest public URL. The canonical
    # validator accepts its typed private source record instead of forcing a
    # fabricated web address.
    dsld_api_sync._validate_external_manual_label(build_manual_label(_export()))


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
            {"name": "silicon dioxide."},
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


def row_id(row: dict) -> str:
    return str(row["submission_id"])


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
        {"p_submission_id": row["submission_id"]},
    )]
    webp_path = image_dir / f"{product_id}.webp"
    assert webp_path.is_file()
    with Image.open(webp_path) as rendered:
        assert rendered.format == "WEBP"
        assert rendered.size == (900, 600)
    index = json.loads((image_dir / "product_image_index.json").read_text())
    assert index[product_id]["filename"] == f"{product_id}.webp"
    assert index[product_id]["sha256"] == hashlib.sha256(
        webp_path.read_bytes()
    ).hexdigest()
    with sqlite3.connect(catalog) as connection:
        assert connection.execute(
            "select image_thumbnail_url from products_core where dsld_id = ?",
            (product_id,),
        ).fetchone() == (f"product-images/{product_id}.webp",)


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


def test_release_train_registers_submission_images_before_cloud_sync():
    release = Path("scripts/release_full.sh").read_text(encoding="utf-8")

    snapshot = release.index("bash scripts/rebuild_dashboard_snapshot.sh")
    copy_images = release.index("product_submission_import.py --copy-images")
    cloud_sync = release.index("scripts/sync_to_supabase.py")

    assert snapshot < copy_images < cloud_sync


def test_dashboard_snapshot_applies_reviewed_submission_corrections_last():
    snapshot = Path("scripts/rebuild_dashboard_snapshot.sh").read_text(
        encoding="utf-8"
    )

    enriched_append = snapshot.index('ENR+=("$SUBMISSION_ENRICHED_DIR")')
    scored_append = snapshot.index('SCR+=("$SUBMISSION_SCORED_DIR")')
    build = snapshot.index('--enriched-dir "${ENR[@]}"')

    assert enriched_append < build
    assert scored_append < build
