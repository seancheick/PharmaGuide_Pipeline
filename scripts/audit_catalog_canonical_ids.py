#!/usr/bin/env python3
"""Audit and optionally repair catalog canonical-ID carriers.

Quick Check reads products_core synchronously, so every shippable product with
mapped active ingredient canonical IDs in its detail blob must expose those IDs
from products_core.key_ingredient_tags and/or ingredient_fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


STRUCTURAL_KEYS = {"nutrients", "herbs", "categories", "pharmacological_flags"}
NUTRIENT_CATEGORIES = {
    "vitamin",
    "vitamins",
    "mineral",
    "minerals",
    "amino_acid",
    "amino_acids",
    "fatty_acid",
    "fatty_acids",
}
HERB_CATEGORIES = {"botanical", "botanicals", "herb", "herbs", "plant_extract", "plant_extracts"}


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text or text in STRUCTURAL_KEYS:
        return ""
    return text


def ids_from_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    ids: list[str] = []

    def add(value: Any) -> None:
        cid = _norm(value)
        if cid and cid not in ids:
            ids.append(cid)

    if isinstance(decoded, list):
        for item in decoded:
            add(item)
        return ids
    if not isinstance(decoded, dict):
        return []

    if STRUCTURAL_KEYS.intersection(decoded):
        nutrients = decoded.get("nutrients")
        if isinstance(nutrients, dict):
            for key in nutrients:
                add(key)
        herbs = decoded.get("herbs")
        if isinstance(herbs, list):
            for item in herbs:
                add(item)
        return ids

    for key in decoded:
        add(key)
    return ids


def load_blob(detail_blobs_dir: Path, dsld_id: str) -> dict[str, Any]:
    path = detail_blobs_dir / f"{dsld_id}.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def ingredient_rows(blob: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blob.get("ingredients")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def ids_from_blob(blob: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for row in ingredient_rows(blob):
        cid = _norm(row.get("canonical_id"))
        if cid and cid not in ids:
            ids.append(cid)
    return ids


def has_mapped_active(blob: dict[str, Any]) -> bool:
    for row in ingredient_rows(blob):
        mapped = row.get("mapped", row.get("is_mapped"))
        if mapped in (True, 1, "1", "true", "True"):
            return True
    return False


def repaired_fingerprint(raw: str | None, blob: dict[str, Any]) -> str:
    try:
        existing = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        existing = {}
    if not isinstance(existing, dict):
        existing = {}

    nutrients: dict[str, dict[str, Any]] = {}
    herbs: list[str] = []
    categories: list[str] = []

    for row in ingredient_rows(blob):
        cid = _norm(row.get("canonical_id"))
        if not cid:
            continue
        category = str(row.get("category") or "").strip().lower()
        if category and category not in categories:
            categories.append(category)
        if category in HERB_CATEGORIES and cid not in herbs:
            herbs.append(cid)
        if category in NUTRIENT_CATEGORIES:
            amount = row.get("normalized_amount", row.get("dosage", row.get("quantity")))
            unit = row.get("normalized_unit", row.get("dosage_unit", row.get("unit", "")))
            if amount is not None:
                try:
                    amount = float(amount)
                except (TypeError, ValueError):
                    amount = None
            nutrients[cid] = {"amount": amount, "unit": str(unit or "")}

    existing_flags = existing.get("pharmacological_flags")
    flags = existing_flags if isinstance(existing_flags, dict) else {}
    return json.dumps(
        {
            "nutrients": nutrients,
            "herbs": herbs,
            "categories": categories or existing.get("categories", []),
            "pharmacological_flags": flags,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def update_manifest_checksum(core_db: Path) -> None:
    manifest = core_db.with_name("export_manifest.json")
    if not manifest.exists():
        return
    digest = hashlib.sha256(core_db.read_bytes()).hexdigest()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["checksum"] = f"sha256:{digest}"
    data["checksum_sha256"] = digest
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit(core_db: Path, detail_blobs_dir: Path, repair: bool) -> dict[str, Any]:
    conn = sqlite3.connect(core_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT dsld_id, product_name, brand_name, key_ingredient_tags, "
        "ingredient_fingerprint FROM products_core ORDER BY dsld_id"
    ).fetchall()

    counts = {
        "total_products": len(rows),
        "empty_key_ingredient_tags": 0,
        "detail_blob_with_canonical_id": 0,
        "product_row_derivable_before": 0,
        "quick_check_derivable_after_detail": 0,
        "no_canonical_id_despite_mapped_ingredients": 0,
        "structural_keys_exposed_before": 0,
        "repaired_rows": 0,
    }
    examples: dict[str, list[dict[str, Any]]] = {
        "no_canonical_id_despite_mapped_ingredients": [],
        "structural_keys_exposed_before": [],
    }

    updates: list[tuple[str, str, str]] = []
    for row in rows:
        product_ids = ids_from_json(row["key_ingredient_tags"]) + ids_from_json(row["ingredient_fingerprint"])
        product_ids = list(dict.fromkeys(product_ids))
        raw_tag_ids = ids_from_json(row["key_ingredient_tags"])
        blob = load_blob(detail_blobs_dir, row["dsld_id"])
        blob_ids = ids_from_blob(blob)

        if not raw_tag_ids:
            counts["empty_key_ingredient_tags"] += 1
        if blob_ids:
            counts["detail_blob_with_canonical_id"] += 1
        if product_ids:
            counts["product_row_derivable_before"] += 1
        if product_ids or blob_ids:
            counts["quick_check_derivable_after_detail"] += 1
        if has_mapped_active(blob) and not blob_ids:
            counts["no_canonical_id_despite_mapped_ingredients"] += 1
            if len(examples["no_canonical_id_despite_mapped_ingredients"]) < 20:
                examples["no_canonical_id_despite_mapped_ingredients"].append(dict(row))

        raw_tag_text = row["key_ingredient_tags"] or ""
        if any(f'"{key}"' in raw_tag_text for key in STRUCTURAL_KEYS):
            counts["structural_keys_exposed_before"] += 1
            if len(examples["structural_keys_exposed_before"]) < 20:
                examples["structural_keys_exposed_before"].append(dict(row))

        if repair and blob_ids:
            merged = list(dict.fromkeys(blob_ids + product_ids))
            new_tags = json.dumps(merged, ensure_ascii=False)
            new_fp = repaired_fingerprint(row["ingredient_fingerprint"], blob)
            if new_tags != row["key_ingredient_tags"] or new_fp != row["ingredient_fingerprint"]:
                updates.append((new_tags, new_fp, row["dsld_id"]))

    if updates:
        conn.executemany(
            "UPDATE products_core SET key_ingredient_tags = ?, ingredient_fingerprint = ? "
            "WHERE dsld_id = ?",
            updates,
        )
        conn.commit()
        counts["repaired_rows"] = len(updates)
    conn.close()

    if updates:
        update_manifest_checksum(core_db)

    return {"counts": counts, "examples": examples}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-db", required=True, type=Path)
    parser.add_argument("--detail-blobs", required=True, type=Path)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    result = audit(args.core_db, args.detail_blobs, args.repair)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    counts = result["counts"]
    if counts["no_canonical_id_despite_mapped_ingredients"]:
        return 1
    if counts["product_row_derivable_before"] < counts["detail_blob_with_canonical_id"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
