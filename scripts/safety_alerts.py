"""Safety-alert record contract — the fast lane for post-purchase regulatory events.

A safety alert answers *"which verified regulatory event just happened, and to
whom"*. It is deliberately NOT a projection of
`scripts/data/banned_recalled_ingredients.json`, which answers a different
question — *"which substances are prohibited"* — and cannot source alerts:

    dsld_id / upc / fda_class      0 of 168 entries (incl. external_ids, recall_scope)
    recalled entries               22, regulatory_date spanning 2009-05-01 -> 2026-03-13

No product identity, no class, and seventeen years of history. Projecting it
would have fired a 2009 recall at every user on first install.

Two lanes, one direction of authority
-------------------------------------
The alert feed is the FAST lane (minutes); the catalog is the SLOW lane
(weekly/monthly, authoritative for the BLOCKED verdict, score suppression and
search exclusion).

**The fast lane may only ADD state, never subtract it.** A retracted or expired
alert clears its own signal and nothing else — a catalog BLOCKED verdict
persists until the catalog's own separately reviewed data changes. Union
semantics across lanes; no cross-lane clearing. `is_active()` below therefore
answers only "should this alert's own signal be raised", never "is this product
safe".

Why `resolved_dsld_ids` is not merely push targeting
----------------------------------------------------
It is the frozen, publication-time applicability set. A device may hold a
catalog snapshot older than the alert, in which case its local ingredient
identities cannot resolve the newly banned substance at all — canonical
matching alone would silently miss. The resolved set is authoritative for
applicability; canonical ingredient matching is a second confirmation when the
device's snapshot supports it. Either path may raise the signal. That is what
lets an ingredient ban work safely BEFORE the slow catalog rebuild.

This module is a leaf: it imports nothing from the enrich or scoring stages, so
the publisher, the release gates and the tests can all share one contract.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = "1.0.0"

EVENT_TYPES = frozenset({"ingredient_ban", "product_recall"})
STATUSES = frozenset({"draft", "published", "retracted"})
CONSUMER_DISPOSITIONS = frozenset({"block", "review"})
# FDA recall classifications. Deliberately NOT required — see `fda_class` below.
FDA_CLASSES = frozenset({"I", "II", "III"})

# Required on EVERY record regardless of event type. Publication authority is
# non-negotiable: an alert without a verifiable official source is not an alert.
REQUIRED_FIELDS: Tuple[str, ...] = (
    "alert_id",
    "revision",
    "event_type",
    "status",
    "authority",
    "source_url",
    "evidence_verified_at",
    "jurisdiction",
    "effective_date",
    "published_at",
    "scope",
    "resolved_dsld_ids",
    "catalog_snapshot_version",
    "headline",
    "body",
    "action",
    "consumer_disposition",
    "retracted",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALERT_ID_RE = re.compile(r"^SA_[0-9]{4}_[0-9]{4}$")


def _is_date(value: Any) -> bool:
    return isinstance(value, str) and bool(_DATE_RE.match(value))


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_alert(record: Any) -> Dict[str, Any]:
    """Validate one alert record. Returns {"ok", "errors", "warnings"}.

    Errors block publication. Warnings are authoring smells that a human should
    look at but that do not make the record unsafe to ship.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(record, dict):
        return {"ok": False, "errors": ["record is not an object"], "warnings": []}

    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}

    alert_id = record.get("alert_id")
    if not _nonempty_str(alert_id) or not _ALERT_ID_RE.match(alert_id):
        errors.append(f"alert_id must match SA_YYYY_NNNN, got {alert_id!r}")

    revision = record.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append(f"revision must be an integer >= 1, got {revision!r}")

    event_type = record.get("event_type")
    if event_type not in EVENT_TYPES:
        errors.append(f"event_type must be one of {sorted(EVENT_TYPES)}, got {event_type!r}")

    status = record.get("status")
    if status not in STATUSES:
        errors.append(f"status must be one of {sorted(STATUSES)}, got {status!r}")

    for field in ("authority", "source_url", "jurisdiction", "headline", "body", "action"):
        if not _nonempty_str(record.get(field)):
            errors.append(f"{field} must be a non-empty string")

    if record.get("consumer_disposition") not in CONSUMER_DISPOSITIONS:
        errors.append(
            "consumer_disposition must be one of "
            f"{sorted(CONSUMER_DISPOSITIONS)}, got {record.get('consumer_disposition')!r}"
        )

    source_url = record.get("source_url")
    if _nonempty_str(source_url) and not str(source_url).startswith("https://"):
        errors.append("source_url must be an https:// URL to the official record")

    for field in ("evidence_verified_at", "effective_date"):
        if not _is_date(record.get(field)):
            errors.append(f"{field} must be YYYY-MM-DD, got {record.get(field)!r}")

    expires_at = record.get("expires_at")
    if expires_at is not None and not _is_date(expires_at):
        errors.append(f"expires_at must be YYYY-MM-DD or null, got {expires_at!r}")

    if not isinstance(record.get("retracted"), bool):
        errors.append("retracted must be a boolean")
    if record.get("retracted") and status != "retracted":
        errors.append("retracted=true requires status='retracted'")

    # fda_class is CONDITIONAL, never required. Classified recalls carry it when
    # the official source provides one; ingredient bans (DEA scheduling, import
    # alerts, warning-letter enforcement) have no FDA recall class and rest on a
    # different official basis, which source_url + authority already capture.
    fda_class = record.get("fda_class")
    if fda_class is not None:
        if fda_class not in FDA_CLASSES:
            errors.append(f"fda_class must be one of {sorted(FDA_CLASSES)} or null, got {fda_class!r}")
        elif event_type == "ingredient_ban":
            warnings.append(
                "fda_class is set on an ingredient_ban — recall classes describe recalls; "
                "confirm the official source really classifies this action"
            )

    errors.extend(_validate_scope(record, event_type))
    errors.extend(_validate_resolution(record))

    # lots[] is DISPLAY-ONLY and must never be read as a matching input. We do
    # not know the user's lot, so a lot-scoped alert says "check your lot" and
    # never claims a match.
    lots = record.get("lots")
    if lots is not None:
        if not isinstance(lots, list) or not all(_nonempty_str(x) for x in lots):
            errors.append("lots must be null or a list of non-empty strings")
        elif lots and event_type == "ingredient_ban":
            warnings.append("lots on an ingredient_ban is unusual — lots describe a recalled batch")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _validate_scope(record: Dict[str, Any], event_type: Any) -> List[str]:
    """Exactly one scope dimension, and no brand in v1.

    Brand scope is deliberately excluded: the matching story covers canonical
    ingredient IDs and direct DSLD IDs only. Admitting `brand` without an exact
    normalized brand identity would invite runtime fuzzy matching, which is how
    an alert condemns the wrong product.
    """
    errors: List[str] = []
    scope = record.get("scope")
    if not isinstance(scope, dict):
        return ["scope must be an object"]

    if "brand" in scope:
        errors.append("brand scope is not supported in v1 — use ingredient_canonical_ids or dsld_ids")

    ingredients = scope.get("ingredient_canonical_ids") or []
    dsld_ids = scope.get("dsld_ids") or []
    for name, value in (("ingredient_canonical_ids", ingredients), ("dsld_ids", dsld_ids)):
        if not isinstance(value, list) or not all(_nonempty_str(x) for x in value):
            errors.append(f"scope.{name} must be a list of non-empty strings")

    if bool(ingredients) == bool(dsld_ids):
        errors.append(
            "scope must populate exactly one of ingredient_canonical_ids or dsld_ids "
            f"(got {len(ingredients)} ingredient ids and {len(dsld_ids)} dsld ids)"
        )

    if event_type == "ingredient_ban" and not ingredients:
        errors.append("ingredient_ban must scope on ingredient_canonical_ids")
    if event_type == "product_recall" and not dsld_ids:
        errors.append("product_recall must scope on dsld_ids")
    return errors


def _validate_resolution(record: Dict[str, Any]) -> List[str]:
    """The frozen applicability set must be present and pinned to a snapshot."""
    errors: List[str] = []
    resolved = record.get("resolved_dsld_ids")
    if not isinstance(resolved, list) or not all(_nonempty_str(x) for x in resolved):
        errors.append("resolved_dsld_ids must be a list of non-empty strings")

    # The snapshot pins the resolution, so the two travel together: a record
    # that HAS resolved ids must name the catalog they were resolved against,
    # and an unresolved draft legitimately has neither yet. Requiring the
    # snapshot unconditionally contradicted the draft allowance directly below
    # and made an authored, not-yet-resolved draft unrepresentable.
    snapshot_given = _nonempty_str(record.get("catalog_snapshot_version"))
    if isinstance(resolved, list) and resolved and not snapshot_given:
        errors.append("catalog_snapshot_version must name the catalog the scope was resolved against")
    elif not snapshot_given and record.get("status") != "draft":
        errors.append(
            "catalog_snapshot_version must name the catalog the scope was resolved against "
            "(only a draft may be unpinned)"
        )

    # A published alert that resolves to nothing would notify nobody and match
    # nothing — almost always an authoring or resolution error, so it is an
    # error rather than a warning. A draft may legitimately be unresolved.
    if record.get("status") == "published" and isinstance(resolved, list) and not resolved:
        errors.append(
            "published alert has an empty resolved_dsld_ids — resolve the scope against a "
            "catalog snapshot before publishing, or keep it a draft"
        )
    return errors


def latest_revisions(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Highest revision per alert_id. Records are immutable per (alert_id, revision)."""
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        alert_id = record.get("alert_id")
        revision = record.get("revision")
        if not _nonempty_str(alert_id) or not isinstance(revision, int):
            continue
        current = latest.get(alert_id)
        if current is None or revision > int(current.get("revision", 0)):
            latest[alert_id] = record
    return latest


def validate_feed(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-record checks: duplicate (alert_id, revision) pairs are fatal."""
    records = list(records)
    errors: List[str] = []
    warnings: List[str] = []

    seen: Dict[Tuple[str, int], int] = {}
    for index, record in enumerate(records):
        outcome = validate_alert(record)
        for message in outcome["errors"]:
            errors.append(f"[{index}] {message}")
        for message in outcome["warnings"]:
            warnings.append(f"[{index}] {message}")
        if not outcome["ok"]:
            continue
        key = (record["alert_id"], record["revision"])
        if key in seen:
            errors.append(
                f"[{index}] duplicate (alert_id, revision) {key} — records are immutable; "
                f"publish a higher revision instead of editing revision {key[1]}"
            )
        seen[key] = index

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def is_active(record: Dict[str, Any], today: str) -> bool:
    """Should this alert's OWN signal be raised on `today` (YYYY-MM-DD)?

    Never a statement about product safety — see the module docstring. A False
    here clears only this alert's signal and must not touch a catalog verdict.
    """
    if not isinstance(record, dict):
        return False
    if record.get("status") != "published" or record.get("retracted"):
        return False
    effective = record.get("effective_date")
    if _is_date(effective) and effective > today:
        return False
    expires = record.get("expires_at")
    if _is_date(expires) and expires < today:
        return False
    return True


def applies_to(
    record: Dict[str, Any],
    *,
    dsld_id: Optional[str] = None,
    ingredient_canonical_ids: Optional[Iterable[str]] = None,
) -> bool:
    """Does this alert apply to one saved product?

    `resolved_dsld_ids` is authoritative — it was computed at publication
    against a pinned catalog snapshot, so it still applies on a device whose own
    snapshot predates the alert. Canonical ingredient matching is the second
    confirmation, used only when the caller's snapshot can supply identities.
    Either path alone is sufficient; never match on name similarity.
    """
    if not isinstance(record, dict):
        return False
    if dsld_id and dsld_id in set(record.get("resolved_dsld_ids") or []):
        return True
    scope_ingredients = set((record.get("scope") or {}).get("ingredient_canonical_ids") or [])
    if scope_ingredients and ingredient_canonical_ids:
        return bool(scope_ingredients & set(ingredient_canonical_ids))
    return False
