#!/usr/bin/env python3
"""Turn classified FDA records into DRAFT safety alerts — or say why it can't.

The weekly sync finds regulatory events. `banned_recalled_ingredients.json`
records them for the catalog's next rebuild. Neither reaches a person who
already has the bottle. This bridges that gap by preparing alert drafts for the
fast lane (`scripts/build_safety_alerts.py`).

DRAFT ONLY. Nothing here may set a status other than "draft". Publication needs
a human who verified identity, scope, wording and source against the primary
record. Class I raises urgency, not authority — FDA does not publish every
recall to its public feeds, so automated collection is not publication evidence.

Why most events cannot be auto-scoped
-------------------------------------
An alert's scope must name identities the catalog can resolve, or it applies to
nobody while looking complete. Measured 2026-08-08 against catalog
2026.08.08.120622:

    banned_recalled_ingredients.json entries            168
    whose `id` also appears as a catalog canonical_id     11   (6.5%)

and the file carries no field linking an entry to the catalog's vocabulary
(`id`, `standard_name`, `aliases`, `cui`, `rxcui` — none of them is one).
Deriving the link from `standard_name` would be name matching, which is how an
alert ends up condemning the wrong product.

So identity is CHECKED, never guessed: a candidate id is proposed only when it
is literally present in the shipped catalog index. When nothing resolves, the
event still surfaces — as a candidate for a human to identify, not as a draft
that would silently apply to zero products.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

# Class I: "reasonable probability that use will cause serious adverse health
# consequences or death". The only recall class that warrants "stop taking this"
# without a human first weighing the specific product.
DRAFT_STATUS = "draft"

# FDA prints "Class I" / "Class II" / "Class III"; the alert schema stores the
# bare numeral.
_CLASS_PATTERN = re.compile(r"^\s*class\s+(i{1,3})\s*$", re.IGNORECASE)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def parse_fda_class(value: Any) -> Optional[str]:
    """"Class II" -> "II". Returns None for anything unrecognised.

    Unclassified events are real — DEA scheduling actions, import alerts and
    warning letters carry no recall class — and `fda_class` is nullable for
    exactly that reason. Never invent one.
    """
    match = _CLASS_PATTERN.match(str(value or ""))
    return match.group(1).upper() if match else None


def _is_class_i(record: Dict[str, Any]) -> bool:
    """Exact match. `startswith("class i")` is true of Class II and Class III
    as well, which silently escalated every classified recall to the highest
    urgency band — caught by test_routine_untracked_recall_does_not.
    """
    return parse_fda_class(record.get("classification")) == "I"


def warrants_user_alert(record: Dict[str, Any]) -> bool:
    """Would a person holding this product want to be told?

    Deliberately narrow. Every alert competes for the same trust; a feed that
    fires on routine Class III labelling corrections teaches people to ignore
    the one that matters.
    """
    if _is_class_i(record):
        return True
    # A substance we already track as banned/recalled is, by construction,
    # something we decided was worth flagging in the catalog.
    if record.get("substances_already_tracked"):
        return True
    return False


def resolvable_ids(
    candidates: Iterable[str],
    catalog_index: Dict[str, Set[str]],
) -> List[str]:
    """Keep only candidate ids literally present in the shipped catalog index.

    Exact equality against real catalog identities. No normalization, no
    substring, no fuzzy fallback — a candidate that needs any of those is not a
    verified identity and belongs in front of a human instead.
    """
    seen: List[str] = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        value = candidate.strip()
        if value and value in catalog_index and value not in seen:
            seen.append(value)
    return seen


def candidate_ids_for(entry: Dict[str, Any]) -> List[str]:
    """Identity candidates a banned-DB entry offers. Verified separately.

    The entry id first (it is the only stable machine identity the file has),
    then aliases — which are proposed ONLY so `resolvable_ids` can test them for
    exact presence in the catalog. An alias that is not literally a catalog
    canonical id is discarded, never approximated.
    """
    candidates: List[str] = []
    entry_id = entry.get("id")
    if isinstance(entry_id, str) and entry_id.strip():
        candidates.append(entry_id.strip())
    for alias in entry.get("aliases") or []:
        if isinstance(alias, str) and alias.strip():
            candidates.append(alias.strip())
    return candidates


def next_alert_id(existing_ids: Iterable[str], year: int) -> str:
    """SA_<year>_<NNNN>, continuing the highest sequence already used."""
    highest = 0
    pattern = re.compile(rf"^SA_{year}_(\d{{4}})$")
    for alert_id in existing_ids:
        match = pattern.match(str(alert_id or ""))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"SA_{year}_{highest + 1:04d}"


def _disposition_for(record: Dict[str, Any], event_type: str) -> str:
    """block = stop taking this. review = check whether yours is affected.

    A prohibited substance is in every unit of the product, so there is nothing
    for the user to check — that is `block`. A recall usually affects specific
    lots we cannot match to the user's bottle, so the honest instruction is to
    check, unless the class says the risk is serious enough not to wait.
    """
    if event_type == "ingredient_ban":
        return "block"
    return "block" if _is_class_i(record) else "review"


def draft_from_record(
    record: Dict[str, Any],
    catalog_index: Dict[str, Set[str]],
    banned_entries_by_substance: Dict[str, Dict[str, Any]],
    *,
    alert_id: str,
    today: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Return (draft, candidate). Exactly one is non-None.

    A draft is produced only when at least one identity RESOLVES against the
    shipped catalog. Otherwise the event is returned as a candidate carrying
    everything a human needs to identify it by hand.
    """
    verified: List[str] = []
    considered: List[str] = []
    for substance in record.get("substances_already_tracked") or []:
        entry = banned_entries_by_substance.get(_norm(substance))
        if not entry:
            continue
        candidates = candidate_ids_for(entry)
        considered.extend(candidates)
        verified.extend(resolvable_ids(candidates, catalog_index))

    # Preserve order, drop repeats.
    verified = list(dict.fromkeys(verified))

    source_url = record.get("fda_source_url") or ""
    substances = record.get("extracted_substances") or []
    firm = record.get("recalling_firm") or ""
    description = record.get("product_description") or ""

    if not verified:
        return None, {
            "reason": "no catalog identity resolved for any extracted substance",
            "recall_number": record.get("recall_number"),
            "classification": record.get("classification"),
            "recalling_firm": firm,
            "product_description": description[:300],
            "reason_for_recall": (record.get("reason_for_recall") or "")[:300],
            "extracted_substances": substances,
            "substances_already_tracked": record.get("substances_already_tracked") or [],
            "identity_candidates_considered": list(dict.fromkeys(considered)),
            "fda_source_url": source_url,
            "what_a_curator_must_supply": (
                "a canonical id the catalog actually uses for this substance — check "
                "display_ingredients[].canonical_id on an affected product. Do NOT scope "
                "on a name."
            ),
        }

    event_type = "ingredient_ban"
    disposition = _disposition_for(record, event_type)

    return {
        "alert_id": alert_id,
        "revision": 1,
        "event_type": event_type,
        "status": DRAFT_STATUS,
        "authority": "FDA",
        "source_url": source_url,
        # The date the sync SAW the record. A human re-verifies against the
        # primary source and resets this before publishing.
        "evidence_verified_at": today,
        "fda_class": parse_fda_class(record.get("classification")),
        "jurisdiction": "US",
        "effective_date": record.get("recall_initiation_date") or today,
        "published_at": None,
        "scope": {"ingredient_canonical_ids": verified, "dsld_ids": []},
        # Left empty on purpose: resolution happens at publication, pinned to a
        # catalog snapshot. See build_safety_alerts.resolve_all.
        "resolved_dsld_ids": [],
        "catalog_snapshot_version": None,
        "lots": None,
        "headline": f"FDA action on {', '.join(substances[:2]) or 'a tracked substance'}",
        "body": (record.get("reason_for_recall") or "").strip()[:500]
        or "FDA has taken action involving a substance tracked in this product.",
        "action": (
            "Stop taking this product and talk to your clinician."
            if disposition == "block"
            else "Check whether your product is affected."
        ),
        "consumer_disposition": disposition,
        "expires_at": None,
        "retracted": False,
        "_draft_provenance": {
            "generated_by": "fda_alert_drafts.py",
            "generated_at": today,
            "recall_number": record.get("recall_number"),
            "recalling_firm": firm,
            "identity_candidates_considered": list(dict.fromkeys(considered)),
            "identity_verified_against_catalog": verified,
            "human_must": (
                "verify identity/scope/wording against the primary source, write "
                "consumer copy, then resolve and publish. Copy here is a placeholder."
            ),
        },
    }, None


def propose_drafts(
    records: Sequence[Dict[str, Any]],
    catalog_index: Dict[str, Set[str]],
    banned_entries_by_substance: Dict[str, Dict[str, Any]],
    *,
    existing_alert_ids: Iterable[str],
    today: str,
    year: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split classified records into drafts and identity candidates."""
    drafts: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    used_ids = list(existing_alert_ids)

    for record in records:
        if not warrants_user_alert(record):
            continue
        alert_id = next_alert_id(used_ids, year)
        draft, candidate = draft_from_record(
            record,
            catalog_index,
            banned_entries_by_substance,
            alert_id=alert_id,
            today=today,
        )
        if draft is not None:
            drafts.append(draft)
            used_ids.append(alert_id)
        elif candidate is not None:
            candidates.append(candidate)

    return {"drafts": drafts, "candidates_needing_identity": candidates}


def index_banned_entries(entries: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """standard_name / alias (lowercased) -> entry, for substance lookup.

    This index maps the SYNC's extracted substance text to a banned-DB entry. It
    is not an identity claim about the catalog — the entry's ids still have to
    survive `resolvable_ids` before they can scope an alert.
    """
    index: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        for name in [entry.get("standard_name")] + list(entry.get("aliases") or []):
            key = _norm(name)
            if key:
                index.setdefault(key, entry)
    return index
