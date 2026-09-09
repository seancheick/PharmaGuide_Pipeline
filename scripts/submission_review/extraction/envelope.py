"""``label_draft_v1``: the provenance-bound partial draft an extractor produces.

A draft is what a reviewer *starts from*, never what the catalog ingests. It
may carry explicit unknowns, per-field photo provenance and typed
discrepancies; it may not carry anything the model is forbidden to mint
(identities, citations, scores, verdicts). The approved label is a separate
contract (``manual_label_v1``, validated by
``product_submission_import._validate_label_payload``) that the reviewer
completes from this draft. Validation here never normalizes label text.

The same rules live in the app repo's Deno module
(``supabase/functions/review-product-submissions/schema.ts``); both sides pin
``fixtures/label_draft_v1_cases.json`` by checksum.
"""

from __future__ import annotations

import math
import re
from typing import Any

SCHEMA_VERSION = "label_draft_v1"

# Keys a model output may never contain at any depth: these are identity,
# citation, benefit and scoring decisions owned by the pipeline and reviewer.
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "canonical_id",
        "canonical_ids",
        "clean_identity_id",
        "cui",
        "rxcui",
        "unii",
        "pmid",
        "pmids",
        "score",
        "scores",
        "verdict",
        "benefit",
        "benefits",
        "safety_verdict",
    }
)

FIELD_STATUSES = frozenset({"read", "partial", "unreadable", "not_present"})
ROW_STATUSES = frozenset({"read", "partial", "unreadable"})
READABILITIES = frozenset({"ok", "partial", "unreadable"})
PHOTO_ISSUES = frozenset({"glare", "blur", "cut_off", "curved", "dark", "small_print"})
PHOTO_ROLES = frozenset(
    {
        "front_identity",
        "supplement_facts",
        "ingredient_disclosure",
        "directions_warnings",
        "barcode",
        "lot_expiry",
    }
)
DISCLOSURE_HINTS = frozenset({"present", "declared_none", "on_facts_panel", "unknown"})
DISCREPANCY_CODES = frozenset(
    {
        "barcode_mismatch",
        "multiple_products",
        "front_facts_brand_conflict",
        "declared_role_mismatch",
        "facts_panel_missing",
        "facts_unreadable",
        "cut_off_text",
        "foreign_language",
        "handwritten",
        "expired_date_seen",
        "injection_text_present",
        "serving_basis_ambiguous",
        "catalog_candidate",
        "model_failure",
    }
)
DISCREPANCY_SEVERITIES = frozenset({"info", "warning", "critical"})

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "provider",
        "model",
        "prompt_version",
        "job_key",
        "result_fingerprint",
        "evidence_revision",
        "evidence_snapshot",
        "sent_inputs",
        "photo_roles",
        "identity",
        "serving",
        "ingredient_rows",
        "other_ingredients",
        "statements",
        "discrepancies",
        "abstained",
        "abstain_reason",
        "overall_confidence",
    }
)
REQUIRED_TOP_LEVEL_KEYS = TOP_LEVEL_KEYS - {"job_key", "result_fingerprint", "evidence_revision"}

MAX_INGREDIENT_ROWS = 500
MAX_STATEMENTS = 100
MAX_DISCREPANCIES = 100
MAX_TEXT = 2_000
MAX_SHORT = 200

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._:/+-]{1,120}$")


class LabelDraftError(ValueError):
    """A draft violates the ``label_draft_v1`` contract; ``path`` names where."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


def validate_label_draft_v1(value: Any) -> dict[str, Any]:
    """Return ``value`` unchanged when it is a valid draft; raise otherwise."""
    draft = _obj(value, "$")
    _reject_unknown(draft, TOP_LEVEL_KEYS, "$")
    for key in sorted(REQUIRED_TOP_LEVEL_KEYS):
        if key not in draft:
            raise LabelDraftError(f"$.{key}", "required")
    _reject_forbidden_keys(draft, "$")

    if draft["schema_version"] != SCHEMA_VERSION:
        raise LabelDraftError("$.schema_version", f"must be {SCHEMA_VERSION}")
    for key in ("provider", "model", "prompt_version"):
        _token(draft[key], f"$.{key}")
    for key in ("job_key", "result_fingerprint"):
        if key in draft and draft[key] is not None:
            _token(draft[key], f"$.{key}")
    if "evidence_revision" in draft and draft["evidence_revision"] is not None:
        _positive_int(draft["evidence_revision"], "$.evidence_revision")

    snapshot = _snapshot(draft["evidence_snapshot"])
    _sent_inputs(draft["sent_inputs"], snapshot)
    _photo_roles(draft["photo_roles"], snapshot)

    identity = _obj(draft["identity"], "$.identity")
    _reject_unknown(identity, {"brand", "product_name", "barcode_digits_seen"}, "$.identity")
    _field(identity.get("brand"), "$.identity.brand", snapshot)
    _field(identity.get("product_name"), "$.identity.product_name", snapshot)
    _nullable_field(identity.get("barcode_digits_seen"), "$.identity.barcode_digits_seen", snapshot)

    serving = _obj(draft["serving"], "$.serving")
    _reject_unknown(serving, {"size", "servings_per_container", "basis_text"}, "$.serving")
    for key in ("size", "servings_per_container", "basis_text"):
        _field(serving.get(key), f"$.serving.{key}", snapshot)

    _ingredient_rows(draft["ingredient_rows"], snapshot)

    other = _obj(draft["other_ingredients"], "$.other_ingredients")
    _reject_unknown(other, {"text", "disclosure_hint"}, "$.other_ingredients")
    _nullable_field(other.get("text"), "$.other_ingredients.text", snapshot)
    if other.get("disclosure_hint") not in DISCLOSURE_HINTS:
        raise LabelDraftError("$.other_ingredients.disclosure_hint", "unknown disclosure hint")

    statements = _list(draft["statements"], "$.statements", MAX_STATEMENTS)
    for index, statement in enumerate(statements):
        _field(statement, f"$.statements[{index}]", snapshot)

    _discrepancies(draft["discrepancies"], snapshot)

    if not isinstance(draft["abstained"], bool):
        raise LabelDraftError("$.abstained", "must be boolean")
    reason = draft["abstain_reason"]
    if draft["abstained"]:
        _text(reason, "$.abstain_reason", MAX_SHORT, required=True)
    elif reason is not None:
        _text(reason, "$.abstain_reason", MAX_SHORT, required=False)
    _confidence(draft["overall_confidence"], "$.overall_confidence")
    return draft


# ---------------------------------------------------------------------------
# Sections


def _snapshot(value: Any) -> dict[str, str]:
    snapshot = _obj(value, "$.evidence_snapshot")
    if not snapshot:
        raise LabelDraftError("$.evidence_snapshot", "at least one photo required")
    for photo_id, digest in snapshot.items():
        if not _UUID.match(str(photo_id)):
            raise LabelDraftError("$.evidence_snapshot", f"invalid photo id {photo_id!r}")
        if not isinstance(digest, str) or not _SHA256.match(digest):
            raise LabelDraftError(f"$.evidence_snapshot.{photo_id}", "invalid sha256")
    return snapshot


def _sent_inputs(value: Any, snapshot: dict[str, str]) -> None:
    items = _list(value, "$.sent_inputs", len(snapshot) * 4)
    for index, item in enumerate(items):
        path = f"$.sent_inputs[{index}]"
        entry = _obj(item, path)
        _reject_unknown(entry, {"photo_id", "sha256", "crop"}, path)
        photo_id = _photo_ref(entry.get("photo_id"), f"{path}.photo_id", snapshot)
        if entry.get("sha256") != snapshot[photo_id]:
            raise LabelDraftError(f"{path}.sha256", "must equal the snapshot hash")
        if "crop" in entry and entry["crop"] is not None:
            _region(entry["crop"], f"{path}.crop")


def _photo_roles(value: Any, snapshot: dict[str, str]) -> None:
    roles = _list(value, "$.photo_roles", len(snapshot))
    for index, item in enumerate(roles):
        path = f"$.photo_roles[{index}]"
        entry = _obj(item, path)
        _reject_unknown(entry, {"photo_id", "declared", "inferred", "readability", "issues"}, path)
        _photo_ref(entry.get("photo_id"), f"{path}.photo_id", snapshot)
        for role in _list(entry.get("declared"), f"{path}.declared", len(PHOTO_ROLES)):
            if role not in PHOTO_ROLES:
                raise LabelDraftError(f"{path}.declared", f"unknown role {role!r}")
        for j, inferred in enumerate(_list(entry.get("inferred"), f"{path}.inferred", len(PHOTO_ROLES))):
            ipath = f"{path}.inferred[{j}]"
            inferred_obj = _obj(inferred, ipath)
            _reject_unknown(inferred_obj, {"role", "confidence"}, ipath)
            if inferred_obj.get("role") not in PHOTO_ROLES:
                raise LabelDraftError(f"{ipath}.role", "unknown role")
            _confidence(inferred_obj.get("confidence"), f"{ipath}.confidence")
        if entry.get("readability") not in READABILITIES:
            raise LabelDraftError(f"{path}.readability", "unknown readability")
        for issue in _list(entry.get("issues"), f"{path}.issues", len(PHOTO_ISSUES)):
            if issue not in PHOTO_ISSUES:
                raise LabelDraftError(f"{path}.issues", f"unknown issue {issue!r}")


def _ingredient_rows(value: Any, snapshot: dict[str, str]) -> None:
    rows = _list(value, "$.ingredient_rows", MAX_INGREDIENT_ROWS)
    headers: set[int] = set()
    for index, item in enumerate(rows):
        path = f"$.ingredient_rows[{index}]"
        row = _obj(item, path)
        _reject_unknown(
            row,
            {"display_name", "amount", "percent_dv", "form_text", "parent_index", "is_blend_header", "status"},
            path,
        )
        _field(row.get("display_name"), f"{path}.display_name", snapshot)
        _amount(row.get("amount"), f"{path}.amount", snapshot)
        _nullable_field(row.get("percent_dv"), f"{path}.percent_dv", snapshot, numeric=True)
        _nullable_field(row.get("form_text"), f"{path}.form_text", snapshot)
        if not isinstance(row.get("is_blend_header"), bool):
            raise LabelDraftError(f"{path}.is_blend_header", "must be boolean")
        if row.get("status") not in ROW_STATUSES:
            raise LabelDraftError(f"{path}.status", "unknown row status")
        parent = row.get("parent_index")
        if parent is not None:
            if isinstance(parent, bool) or not isinstance(parent, int):
                raise LabelDraftError(f"{path}.parent_index", "must be an integer or null")
            if parent < 0 or parent >= index:
                raise LabelDraftError(f"{path}.parent_index", "must reference an earlier row")
            if parent not in headers:
                raise LabelDraftError(f"{path}.parent_index", "must reference a blend header")
        if row["is_blend_header"]:
            headers.add(index)


def _discrepancies(value: Any, snapshot: dict[str, str]) -> None:
    items = _list(value, "$.discrepancies", MAX_DISCREPANCIES)
    for index, item in enumerate(items):
        path = f"$.discrepancies[{index}]"
        entry = _obj(item, path)
        _reject_unknown(entry, {"code", "severity", "detail", "photo_ids"}, path)
        if entry.get("code") not in DISCREPANCY_CODES:
            raise LabelDraftError(f"{path}.code", "unknown discrepancy code")
        if entry.get("severity") not in DISCREPANCY_SEVERITIES:
            raise LabelDraftError(f"{path}.severity", "unknown severity")
        _text(entry.get("detail"), f"{path}.detail", MAX_TEXT, required=False)
        for j, photo_id in enumerate(_list(entry.get("photo_ids"), f"{path}.photo_ids", len(snapshot))):
            _photo_ref(photo_id, f"{path}.photo_ids[{j}]", snapshot)


# ---------------------------------------------------------------------------
# Field primitives


def _field(value: Any, path: str, snapshot: dict[str, str], *, numeric: bool = False) -> None:
    field = _obj(value, path)
    _reject_unknown(field, {"value", "status", "confidence", "sources"}, path)
    status = field.get("status")
    if status not in FIELD_STATUSES:
        raise LabelDraftError(f"{path}.status", "unknown field status")
    raw = field.get("value")
    sources = _list(field.get("sources"), f"{path}.sources", len(snapshot) * 4)
    if status in ("read", "partial"):
        if raw is None:
            raise LabelDraftError(f"{path}.value", f"{status} field requires a value")
        if not sources:
            raise LabelDraftError(f"{path}.sources", f"{status} field requires a source")
    else:
        if raw is not None:
            raise LabelDraftError(f"{path}.value", f"{status} field must have no value")
        if sources:
            raise LabelDraftError(f"{path}.sources", f"{status} field must have no sources")
    if raw is not None:
        if numeric:
            _finite_number(raw, f"{path}.value", minimum=0.0)
        elif isinstance(raw, dict):
            raise LabelDraftError(f"{path}.value", "must be text or a number")
        elif isinstance(raw, str):
            _text(raw, f"{path}.value", MAX_TEXT, required=True)
        else:
            _finite_number(raw, f"{path}.value")
    _confidence(field.get("confidence"), f"{path}.confidence")
    for index, source in enumerate(sources):
        spath = f"{path}.sources[{index}]"
        entry = _obj(source, spath)
        _reject_unknown(entry, {"photo_id", "supporting_text", "region"}, spath)
        _photo_ref(entry.get("photo_id"), f"{spath}.photo_id", snapshot)
        _text(entry.get("supporting_text"), f"{spath}.supporting_text", MAX_TEXT, required=False)
        if "region" in entry and entry["region"] is not None:
            _region(entry["region"], f"{spath}.region")


def _nullable_field(value: Any, path: str, snapshot: dict[str, str], *, numeric: bool = False) -> None:
    if value is None:
        return
    _field(value, path, snapshot, numeric=numeric)


def _amount(value: Any, path: str, snapshot: dict[str, str]) -> None:
    """An amount is a field whose value is ``{value, unit_text}`` exactly as printed."""
    if value is None:
        return
    field = _obj(value, path)
    _reject_unknown(field, {"value", "status", "confidence", "sources"}, path)
    status = field.get("status")
    if status not in FIELD_STATUSES:
        raise LabelDraftError(f"{path}.status", "unknown field status")
    raw = field.get("value")
    sources = _list(field.get("sources"), f"{path}.sources", len(snapshot) * 4)
    if status in ("read", "partial"):
        amount = _obj(raw, f"{path}.value")
        _reject_unknown(amount, {"value", "unit_text"}, f"{path}.value")
        _finite_number(amount.get("value"), f"{path}.value.value", minimum=0.0)
        _text(amount.get("unit_text"), f"{path}.value.unit_text", MAX_SHORT, required=True)
        if not sources:
            raise LabelDraftError(f"{path}.sources", f"{status} amount requires a source")
    else:
        if raw is not None or sources:
            raise LabelDraftError(f"{path}.value", f"{status} amount must have no value")
    _confidence(field.get("confidence"), f"{path}.confidence")
    for index, source in enumerate(sources):
        spath = f"{path}.sources[{index}]"
        entry = _obj(source, spath)
        _reject_unknown(entry, {"photo_id", "supporting_text", "region"}, spath)
        _photo_ref(entry.get("photo_id"), f"{spath}.photo_id", snapshot)
        _text(entry.get("supporting_text"), f"{spath}.supporting_text", MAX_TEXT, required=False)
        if "region" in entry and entry["region"] is not None:
            _region(entry["region"], f"{spath}.region")


# ---------------------------------------------------------------------------
# Primitives


def _obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LabelDraftError(path, "must be an object")
    return value


def _list(value: Any, path: str, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise LabelDraftError(path, "must be an array")
    if len(value) > maximum:
        raise LabelDraftError(path, f"at most {maximum} items")
    return value


def _reject_unknown(obj: dict[str, Any], allowed: frozenset[str] | set[str], path: str) -> None:
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        raise LabelDraftError(path, f"unknown key {unknown[0]!r}")


def _reject_forbidden_keys(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise LabelDraftError(f"{path}.{key}", "model output may not carry this key")
            _reject_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}[{index}]")


def _token(value: Any, path: str) -> None:
    if not isinstance(value, str) or not _TOKEN.match(value):
        raise LabelDraftError(path, "must be a short token")


def _text(value: Any, path: str, maximum: int, *, required: bool) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str):
        raise LabelDraftError(path, "must be text")
    if required and not value.strip():
        raise LabelDraftError(path, "must not be empty")
    if len(value) > maximum:
        raise LabelDraftError(path, f"at most {maximum} characters")


def _finite_number(value: Any, path: str, *, minimum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise LabelDraftError(path, "must be a finite number")
    if minimum is not None and value < minimum:
        raise LabelDraftError(path, f"must be at least {minimum:g}")


def _positive_int(value: Any, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LabelDraftError(path, "must be a positive integer")


def _confidence(value: Any, path: str) -> None:
    if value is None:
        return
    _finite_number(value, path)
    if value < 0 or value > 1:
        raise LabelDraftError(path, "must be between 0 and 1")


def _photo_ref(value: Any, path: str, snapshot: dict[str, str]) -> str:
    if not isinstance(value, str) or value not in snapshot:
        raise LabelDraftError(path, "must reference a snapshot photo")
    return value


def _region(value: Any, path: str) -> None:
    region = _obj(value, path)
    _reject_unknown(region, {"x", "y", "w", "h"}, path)
    for key in ("x", "y", "w", "h"):
        component = region.get(key)
        _finite_number(component, f"{path}.{key}")
        if component < 0 or component > 1:
            raise LabelDraftError(f"{path}.{key}", "must be a fraction of the image")
    if region["x"] + region["w"] > 1.000001 or region["y"] + region["h"] > 1.000001:
        raise LabelDraftError(path, "must stay inside the image")
