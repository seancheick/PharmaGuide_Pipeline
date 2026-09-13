"""Private, single-reviewer development results; never clinical qualification.

The console supplies explicit occurrence correspondence. We do not match by
name or position: both can change during a legitimate correction.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import statistics
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[2] / "reports" / "submission_solo"
METRICS = ("product_identity", "serving_info", "ingredient_identity", "ingredient_form", "amount", "unit", "ingredient_dose_pair")
_SAVE_LOCK = Lock()


class SoloReviewError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def save_authorized_review(record, authorization, project_url, anon_key):
    """Bind private results to the existing reviewer API and stored extraction."""
    from .extraction.bounded_http import request, TransportError
    from .extraction.envelope import _UUID, _SHA256
    from .extraction.to_manual_label import to_manual_label

    validate(record)
    if (not _UUID.fullmatch(record["submission_id"])
            or not isinstance(record.get("evidence_manifest_sha256"), str)
            or not _SHA256.fullmatch(record["evidence_manifest_sha256"])):
        raise SoloReviewError(400, "Invalid submission evidence.")

    def read(method, path, body=None):
        try:
            response = request(method, project_url.rstrip("/") + path,
                headers={"authorization": authorization, "apikey": anon_key},
                body=body, timeout=20, max_bytes=2 * 1024 * 1024)
            if response.status_code in (401, 403):
                raise SoloReviewError(response.status_code, "Reviewer access could not be confirmed. Sign in again.")
            if response.status_code != 200:
                raise SoloReviewError(503, "Reviewer data unavailable. Retry after reloading.")
            result = json.loads(response.content)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except SoloReviewError:
            raise
        except (TransportError, ValueError):
            raise SoloReviewError(503, "Reviewer data unavailable. Retry after reloading.") from None

    user = read("GET", "/auth/v1/user")
    if user.get("id") != record["reviewer"]:
        raise SoloReviewError(403, "The reviewer does not match your signed-in account.")
    response = read("POST", "/functions/v1/review-product-submissions",
                    {"action": "list", "submission_id": record["submission_id"], "limit": 1})
    submissions = response.get("submissions")
    if not isinstance(submissions, list) or len(submissions) != 1:
        raise SoloReviewError(409, "Submission unavailable. Reload the queue.")
    selected = submissions[0]
    if not isinstance(selected, dict) or any(selected.get(key) != record[key] for key in
            ("evidence_revision", "evidence_manifest_sha256")) or selected.get("id") != record["submission_id"]:
        raise SoloReviewError(409, "Photos changed. Reload this submission before saving.")
    extractions = [item for item in selected.get("extractions", []) if isinstance(item, dict)
        and item.get("version") == record["extraction_version"]
        and item.get("evidence_revision") == record["evidence_revision"]]
    if len(extractions) != 1:
        raise SoloReviewError(409, "The original extraction is no longer available. Reload the submission.")
    extraction = extractions[0]
    draft = extraction.get("draft_payload")
    if not isinstance(draft, dict) or draft != record["original_machine_draft"]:
        raise SoloReviewError(409, "The original machine draft does not match the stored extraction.")
    payload = to_manual_label(draft).payload
    if payload != record["original_machine_payload"]:
        raise SoloReviewError(409, "The original label does not match the shared draft mapper.")
    grounding = extraction.get("grounding") or {}
    if not isinstance(grounding, dict):
        grounding = {}
    # Mapper occurrence order points back to the draft even for nested rows.
    def occurrences(rows):
        for row in rows:
            yield row
            yield from occurrences(row.get("nestedRows") or [])
    by_index = {r["row_index"]: r for r in grounding.get("rows") or []
                if isinstance(r, dict) and type(r.get("row_index")) is int}
    grounding = {**grounding, "rows": [
        {**by_index.get(row["order"] - 1, {}), "row_index": index}
        for index, row in enumerate(occurrences(payload["ingredientRows"]))]}
    return save_review({**record, "reviewer": user["id"], "grounding": grounding})


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _norm(value):
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


def _known(value):
    if isinstance(value, list):
        return bool(value) and all(_known(v) for v in value)
    return value is not None and value != ""


def _flatten(rows, parent=None, result=None):
    if not isinstance(rows, list):
        raise ValueError("Ingredient rows must be a list")
    result = [] if result is None else result
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Ingredient rows must be objects")
        quantities = row.get("quantity") or []
        forms = row.get("forms") or []
        if any(not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
               for items in (quantities, forms)):
            raise ValueError("Quantities and forms must be lists of objects")
        quantity = quantities[0] if quantities else {}
        index = len(result)
        result.append({"name": row.get("name") or None,
                       "form": [f.get("name") for f in forms if f.get("name")],
                       "amount": [q.get("quantity") for q in quantities] if len(quantities) > 1 else quantity.get("quantity"),
                       "unit": [q.get("unit") for q in quantities] if len(quantities) > 1 else quantity.get("unit") or None,
                       "quantities": quantities, "parent": parent})
        _flatten(row.get("nestedRows") or [], index, result)
    return result


def validate(record):
    if not isinstance(record, dict) or record.get("schema_version") != "solo_review_v1":
        raise ValueError("Invalid solo development record")
    for key in ("submission_id", "reviewer"):
        if not isinstance(record.get(key), str) or not 0 < len(record[key]) <= 200:
            raise ValueError(f"Missing {key}")
    for key in ("evidence_revision", "extraction_version"):
        if type(record.get(key)) is not int or record[key] < 0:
            raise ValueError(f"Invalid {key}")
    for key in ("original_machine_draft", "original_machine_payload", "reviewed_payload"):
        if not isinstance(record.get(key), dict):
            raise ValueError(f"Missing {key}")
    seconds = record.get("active_seconds")
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 86400:
        raise ValueError("Invalid active review time")
    if record.get("review_complete") is not True:
        raise ValueError("Check the complete label before saving a result")
    causes = record.get("photo_causes", [])
    if not isinstance(causes, list) or len(causes) > 30 or any(not isinstance(c, str) or len(c) > 100 for c in causes):
        raise ValueError("Photo causes must be a short list of labels")
    grounding = record.get("grounding") or {}
    if not isinstance(grounding, dict) or not isinstance(grounding.get("rows", []), list):
        raise ValueError("Invalid grounding report")
    for item in grounding.get("rows", []):
        if not isinstance(item, dict) or type(item.get("row_index")) is not int:
            raise ValueError("Invalid grounding row")
    original = _flatten(record["original_machine_payload"].get("ingredientRows", []))
    reviewed = _flatten(record["reviewed_payload"].get("ingredientRows", []))
    if max(len(original), len(reviewed)) > 500:
        raise ValueError("Too many ingredient rows")
    seen_original, seen_reviewed = set(), set()
    links = record.get("rows")
    if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
        raise ValueError("Row correspondence must be a list of objects")
    for link in links:
        if link.get("confirmed") is not True:
            raise ValueError("Confirm every current row and removal before saving")
        oi, ri = link.get("original_index"), link.get("reviewed_index")
        if oi is None and ri is None:
            raise ValueError("Empty row correspondence")
        for index, values, seen in ((oi, original, seen_original), (ri, reviewed, seen_reviewed)):
            if index is not None:
                if type(index) is not int or not 0 <= index < len(values) or index in seen:
                    raise ValueError("Invalid or duplicate row correspondence")
                seen.add(index)
        if ri is None and not str(link.get("reason", "")).strip():
            raise ValueError("A removed row needs a reason")
    if seen_original != set(range(len(original))) or seen_reviewed != set(range(len(reviewed))):
        raise ValueError("Every original and reviewed row needs correspondence")
    _canonical(record)  # Reject non-JSON and non-finite values before persistence.
    return original, reviewed


def summarize(records):
    metrics = {name: {"correct": 0, "total": 0, "unknown": 0} for name in METRICS}
    verification = Counter({key: 0 for key in ("incorrect_flagged", "incorrect_supported", "correct_flagged", "not_checked")})
    errors, causes = Counter(), Counter()
    corrections, times = [], []
    missed = invented = corrected_products = total_rows = 0

    def tally(name, applicable, correct):
        metric = metrics[name]
        if applicable:
            metric["total"] += 1
            metric["correct"] += int(correct)
        else:
            metric["unknown"] += 1

    for record in records:
        originals, reviewed = validate(record)
        total_rows += len(reviewed)
        times.append(record["active_seconds"])
        before, after = record["original_machine_payload"], record["reviewed_payload"]
        identity_keys = [k for k in ("brandName", "fullName") if after.get(k) or before.get(k)]
        identity_ok = all(_norm(before.get(k)) == _norm(after.get(k)) for k in identity_keys)
        tally("product_identity", bool(identity_keys), identity_ok)
        serving_keys = [k for k in ("servingSizes", "servingsPerContainer") if after.get(k) not in (None, "", []) or before.get(k) not in (None, "", [])]
        serving_ok = all(before.get(k) == after.get(k) for k in serving_keys)
        tally("serving_info", bool(serving_keys), serving_ok)
        if identity_keys and not identity_ok:
            errors["WRONG_PRODUCT_IDENTITY"] += 1
        if serving_keys and not serving_ok:
            errors["WRONG_SERVING_INFO"] += 1
        changed = any(before.get(k) != after.get(k) for k in set(before) | set(after) if k != "ingredientRows")
        mapping = {r["original_index"]: r["reviewed_index"] for r in record["rows"] if r.get("original_index") is not None}
        grounding = {r["row_index"]: r.get("status") for r in (record.get("grounding") or {}).get("rows", [])}
        for link in record["rows"]:
            oi, ri = link.get("original_index"), link.get("reviewed_index")
            old, new = (originals[oi] if oi is not None else None), (reviewed[ri] if ri is not None else None)
            row_errors = []
            if old is None:
                missed += 1
                row_errors.append("MISSED_INGREDIENT")
            if new is None:
                invented += 1
                row_errors.append("INVENTED_INGREDIENT")
            if new is not None:
                checks = {}
                for metric, key, error in (("ingredient_identity", "name", "WRONG_INGREDIENT"),
                                            ("ingredient_form", "form", "WRONG_FORM"),
                                            ("amount", "amount", "WRONG_AMOUNT"),
                                            ("unit", "unit", "WRONG_UNIT")):
                    expected = new[key]
                    applicable = _known(expected)
                    got = old[key] if old else None
                    correct = (_norm(got) == _norm(expected)) if key != "form" else (
                        [_norm(v) for v in got or []] == [_norm(v) for v in expected])
                    checks[key] = applicable and correct
                    tally(metric, applicable, correct)
                    if not correct and (applicable or _known(got)):
                        row_errors.append(error)
                parent_ok = old is not None and ((old["parent"] is None and new["parent"] is None) or (
                    old["parent"] is not None and new["parent"] is not None and mapping.get(old["parent"]) == new["parent"]))
                dose_applicable = _known(new["amount"]) and _known(new["unit"])
                # Serving owners and all printed quantity columns are part of
                # the association, including rows with multiple quantities.
                owners_ok = old is not None and [q.get("servingSizeOrder") for q in old["quantities"]] == [q.get("servingSizeOrder") for q in new["quantities"]]
                pair_ok = all(checks[k] for k in ("name", "amount", "unit")) and parent_ok and serving_ok and owners_ok
                tally("ingredient_dose_pair", dose_applicable, pair_ok)
                if dose_applicable and not pair_ok:
                    row_errors.append("ROW_ASSOCIATION")
                if old and not parent_ok:
                    row_errors.append("BLEND_ERROR")
            row_wrong = bool(row_errors)
            if oi is not None:
                status = grounding.get(oi, "not_checked")
                if status not in ("supported", "check_this"):
                    verification["not_checked"] += 1
                elif row_wrong:
                    verification["incorrect_supported" if status == "supported" else "incorrect_flagged"] += 1
                elif status == "check_this":
                    verification["correct_flagged"] += 1
            errors.update(row_errors)
            changed |= row_wrong or (old is not None and new is not None and any(
                _norm(old[k]) != _norm(new[k]) for k in old if k != "parent"))
            corrections.append({"submission_id": record["submission_id"], "original_index": oi, "reviewed_index": ri,
                                "original_machine_value": old, "reviewed_value": new,
                                "errors": row_errors, "reason": link.get("reason", "")})
        corrected_products += int(changed)
        causes.update(set(str(v) for v in record.get("photo_causes", [])))
    return {"kind": "solo_development_results", "qualification": "not_evaluated",
            "products_reviewed": len(records), "ingredient_rows_reviewed": total_rows,
            "metrics": metrics, "missed_ingredients": missed, "invented_ingredients": invented,
            "products_corrected": corrected_products, "median_active_seconds": statistics.median(times) if times else None,
            "verification": dict(verification), "top_errors": dict(errors.most_common()),
            "suspected_photo_causes": dict(causes.most_common()), "corrections": corrections}


def render_report(summary):
    lines = ["PharmaGuide — solo development results (not qualified)",
             f"Products reviewed: {summary['products_reviewed']}",
             f"Ingredient rows reviewed: {summary['ingredient_rows_reviewed']}", ""]
    for name, value in summary["metrics"].items():
        lines.append(f"{name}: {value['correct']}/{value['total']} applicable; {value['unknown']} unknown/not applicable")
    for key in ("missed_ingredients", "invented_ingredients", "products_corrected", "median_active_seconds"):
        lines.append(f"{key}: {summary[key]}")
    for section in ("verification", "top_errors", "suspected_photo_causes"):
        lines.append(f"\n{section}:")
        lines.extend(f"  {key}: {value}" for key, value in summary[section].items())
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(("metric", "correct_or_value", "total", "unknown"))
    for key in ("products_reviewed", "ingredient_rows_reviewed", "missed_ingredients", "invented_ingredients", "products_corrected", "median_active_seconds"):
        writer.writerow((key, summary[key], "", ""))
    for name, value in summary["metrics"].items():
        writer.writerow((name, value["correct"], value["total"], value["unknown"]))
    for name, value in summary["verification"].items():
        writer.writerow((name, value, "", ""))
    for section in ("top_errors", "suspected_photo_causes"):
        for name, value in summary[section].items():
            # Prefixing these rows also prevents a photo-cause label being
            # interpreted as a spreadsheet formula.
            writer.writerow((f"{section}: {name}", value, "", ""))
    writer.writerow(())
    columns = ("submission_id", "original_index", "reviewed_index", "original_machine_value", "reviewed_value", "errors", "reason")
    writer.writerow(columns)
    for correction in summary["corrections"]:
        values = []
        for key in columns:
            value = correction[key]
            text = _canonical(value) if isinstance(value, (dict, list)) else str(value if value is not None else "")
            values.append("'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text)
        writer.writerow(values)
    return "\n".join(lines) + "\n", stream.getvalue()


def save_review(record, root=None):
    with _SAVE_LOCK:
        return _save_review(record, root)


def _save_review(record, root=None):
    validate(record)
    root = Path(root) if root is not None else ROOT
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = [record[k] for k in ("submission_id", "evidence_revision", "extraction_version", "reviewer")]
    path = root / (hashlib.sha256(_canonical(key).encode()).hexdigest() + ".json")
    if path.exists():
        previous = json.loads(path.read_text())
        for field in ("original_machine_draft", "original_machine_payload"):
            if previous[field] != record[field]:
                raise ValueError("The original machine output cannot be replaced")
    stored = {**record, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    # Validate the complete result before replacing any stored record. A bad
    # request must never poison subsequent otherwise valid reports.
    latest = {record["submission_id"]: stored}
    for candidate in root.glob("*.json"):
        if candidate == path:
            continue
        item = json.loads(candidate.read_text())
        if item.get("reviewer") != record["reviewer"]:
            continue
        existing = latest.get(item["submission_id"])
        if existing is None or item["reviewed_at"] > existing["reviewed_at"]:
            latest[item["submission_id"]] = item
    summary = summarize(list(latest.values()))
    text, csv_text = render_report(summary)
    with tempfile.NamedTemporaryFile(mode="w", dir=root, delete=False, encoding="utf-8") as handle:
        temp = Path(handle.name)
        handle.write(_canonical(stored))
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return {"summary": summary, "text": text, "csv": csv_text}
