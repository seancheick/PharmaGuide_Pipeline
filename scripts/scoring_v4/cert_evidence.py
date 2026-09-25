"""Certification evidence shared by every v4 trust scorer, confidence and export.

One owner for three facts that used to be copied between generic_trust,
omega_trust and confidence (and re-implemented in build_final_db):

- which verified certification rows belong to this product's brand;
- which certification programs require an audited GMP facility
  (``implies_gmp`` policy in data/cert_claim_rules.json);
- whether this product has audited GMP evidence at all (a verified product
  certification that audits GMP, or the canonical manufacturer's sourced
  registration in an audited GMP facility registry).

Label GMP wording (a "GMP"/"cGMP" claim, an NSF GMP mark, FDA facility
registration) is self-asserted and never counts as audited GMP.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from scoring_v4.modules import brand_testing_posture

_CERT_CLAIM_RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "cert_claim_rules.json"

# The only bases on which GMP counts as audited. Trust modules emit one of these
# as ``gmp_basis``; the Verification pillar and the export accept nothing else.
AUDITED_GMP_BASES = frozenset({"verified_certification", "manufacturer_facility"})
_USABLE_PRODUCT_CERT_RECENCY = frozenset({"fresh", "warn"})


class CertificationPolicyError(RuntimeError):
    """The canonical certification policy cannot be loaded safely."""


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def brand_key(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[®™©]", " ", text)
    text = re.sub(
        r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|company|co|gmbh|holdings|group|brands|brand)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def brand_tokens(value: str) -> set[str]:
    return {token for token in value.split() if len(token) >= 2}


def cert_entry_brand_matches_product(product: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """A registry row matched to another brand must not verify this product."""
    matched_brand = brand_key(entry.get("matched_brand"))
    if not matched_brand:
        return True
    product_brand = brand_key(
        product.get("brandName")
        or product.get("brand_name")
        or product.get("brand")
        or ""
    )
    if not product_brand:
        return False
    product_tokens = brand_tokens(product_brand)
    matched_tokens = brand_tokens(matched_brand)
    if not product_tokens or not matched_tokens:
        return False
    return product_tokens.issubset(matched_tokens) or matched_tokens.issubset(product_tokens)


def verified_cert_entries(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """verified_cert_programs at top level or under certification_data."""
    direct = product.get("verified_cert_programs")
    if isinstance(direct, list):
        return [entry for entry in direct if isinstance(entry, dict)]
    cert_data = product.get("certification_data")
    nested = cert_data.get("verified_cert_programs") if isinstance(cert_data, dict) else None
    if isinstance(nested, list):
        return [entry for entry in nested if isinstance(entry, dict)]
    return []


@lru_cache(maxsize=1)
def marine_cert_tokens() -> frozenset[str]:
    """Normalized names of certification programs whose registry scope is marine.

    ``cert_claim_rules.json`` ``rules.third_party_programs`` is the only
    source. A missing file, malformed JSON, or a registry that declares no
    marine program is a systemic configuration failure. Scoring stops rather
    than substituting a private list or silently withholding unrelated
    certification credit.
    """
    try:
        data = json.loads(_CERT_CLAIM_RULES_PATH.read_text())
    except (OSError, ValueError) as exc:
        raise CertificationPolicyError(
            f"cannot load canonical certification policy: {_CERT_CLAIM_RULES_PATH}"
        ) from exc
    if not isinstance(data, dict):
        raise CertificationPolicyError("canonical certification policy root is not an object")
    programs = (data.get("rules") or {}).get("third_party_programs") if isinstance(data.get("rules"), dict) else None
    if not isinstance(programs, dict):
        raise CertificationPolicyError(
            "canonical certification policy has no third_party_programs object"
        )
    tokens: set[str] = set()
    for key, entry in programs.items():
        if not isinstance(key, str) or key.startswith("_") or not isinstance(entry, dict):
            continue
        if _norm(entry.get("product_scope")) != "marine":
            continue
        display = _norm(entry.get("display_name"))
        key_norm = _norm(key.replace("_", " "))
        if display:
            tokens.add(display)
        if key_norm:
            tokens.add(key_norm)
    if not tokens:
        raise CertificationPolicyError(
            "canonical certification policy declares no marine-scoped program"
        )
    return frozenset(tokens)


@lru_cache(maxsize=1)
def gmp_implying_programs() -> frozenset[str]:
    """Normalized program names whose certification requires a GMP facility audit."""
    try:
        data = json.loads(_CERT_CLAIM_RULES_PATH.read_text())
    except (OSError, ValueError):
        return frozenset()
    programs = (data.get("rules") or {}).get("third_party_programs") or {}
    tokens = set()
    for key, entry in programs.items():
        if key.startswith("_") or not isinstance(entry, dict):
            continue
        policy = entry.get("implies_gmp")
        if isinstance(policy, dict) and _norm(policy.get("verified_program")):
            tokens.add(_norm(policy.get("verified_program")))
    return frozenset(tokens)


def is_verified_product_cert_entry(product: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Whether one resolver row is current, attributable product evidence.

    Product scope alone is not verification.  A scoring row must retain the
    current registry record, its source, usable snapshot recency, and the
    product-brand binding.  Keeping this predicate here prevents trust,
    confidence, export, and badges from inventing separate meanings of
    "verified".
    """
    return bool(
        not entry.get("scoring_blocked_reason")
        and _norm(entry.get("scope")) in {"sku", "product_line"}
        and str(entry.get("record_id") or "").strip()
        and str(entry.get("source_url") or "").strip()
        and str(entry.get("snapshot_date") or "").strip()
        and _norm(entry.get("recency_status")) in _USABLE_PRODUCT_CERT_RECENCY
        and cert_entry_brand_matches_product(product, entry)
    )


def verified_product_cert_entries(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registry rows that verify THIS product: sku/product_line scope, not
    blocked by the resolver, and matched to this product's brand. Brand-only,
    claimed-only and needs-review rows never verify a product."""
    return [
        entry for entry in verified_cert_entries(product)
        if is_verified_product_cert_entry(product, entry)
    ]


QUALITY_FLAGS = ("purity_verified", "heavy_metal_tested", "label_accuracy_verified")


@lru_cache(maxsize=1)
def verified_program_capabilities() -> Dict[str, frozenset[str]]:
    """Registry program -> quality flags its product-level verification
    establishes (``verified_capabilities`` in data/cert_claim_rules.json)."""
    try:
        data = json.loads(_CERT_CLAIM_RULES_PATH.read_text())
    except (OSError, ValueError):
        return {}
    programs = (data.get("rules") or {}).get("third_party_programs") or {}
    capabilities: Dict[str, frozenset[str]] = {}
    for key, entry in programs.items():
        if key.startswith("_") or not isinstance(entry, dict):
            continue
        policy = entry.get("verified_capabilities")
        if isinstance(policy, dict) and _norm(policy.get("verified_program")):
            capabilities[_norm(policy["verified_program"])] = frozenset(
                flag for flag in policy.get("capabilities") or [] if flag in QUALITY_FLAGS
            )
    return capabilities


def claimed_programs(product: Dict[str, Any]) -> List[str]:
    """Every certification/testing program the label claims, in label order.
    A claim is never verification, even when a registry also verifies it."""
    cert_data = product.get("certification_data")
    third_party = cert_data.get("third_party_programs") if isinstance(cert_data, dict) else None
    entries = third_party.get("programs") if isinstance(third_party, dict) else None
    names: List[str] = []
    for entry in entries if isinstance(entries, list) else []:
        name = str((entry.get("name") if isinstance(entry, dict) else entry) or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def verified_programs(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registry-verified product certifications with their provenance, one per
    program (first product-verifying row wins)."""
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in verified_product_cert_entries(product):
        program = str(entry.get("program") or "").strip()
        if not program or _norm(program) in seen:
            continue
        seen.add(_norm(program))
        out.append({
            "name": program,
            "program": program,
            "record_id": entry.get("record_id"),
            "scope": entry.get("scope"),
            "source_url": entry.get("source_url"),
            "snapshot_date": entry.get("snapshot_date"),
            "recency_status": entry.get("recency_status"),
        })
    return out


def verified_quality_flags(product: Dict[str, Any]) -> Dict[str, bool]:
    """Purity / heavy-metal / label-accuracy flags established by verified
    product certifications only. Label claims light none of them."""
    capabilities = verified_program_capabilities()
    earned: set[str] = set()
    for verified in verified_programs(product):
        earned |= capabilities.get(_norm(verified["program"]), frozenset())
    return {flag: flag in earned for flag in QUALITY_FLAGS}


def gmp_implied_by_verified_cert(product: Dict[str, Any]) -> Optional[str]:
    """The product-verifying certification whose program audits GMP, or None."""
    programs = gmp_implying_programs()
    for entry in verified_product_cert_entries(product):
        if _norm(entry.get("program")) in programs:
            return entry.get("program")
    return None


FACILITY_AUDIT_SCOPE = "gmp_facility"
_USABLE_RECENCY = frozenset({"fresh", "warn"})


@lru_cache(maxsize=1)
def _cert_registry():
    from cert_resolver import CertRegistry

    return CertRegistry.load()


def facility_audit_programs() -> frozenset[str]:
    """Registry programs whose listings are audited GMP facility registrations
    (``registry_sources[].audit_scope == "gmp_facility"``)."""
    sources = (_cert_registry().metadata or {}).get("registry_sources") or []
    return frozenset(
        str(source["program"])
        for source in sources
        if isinstance(source, dict) and source.get("program") and source.get("audit_scope") == FACILITY_AUDIT_SCOPE
    )


def facility_audit_resolution(product: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve an audited GMP facility registration for the product's
    canonical manufacturer.

    Only an exact ``top_manufacturer`` identity counts, and only through that
    manufacturer's sourced ``facility_registrations`` links to a fresh
    facility-scope row of a gmp_facility audit source. Brand-name similarity
    and free-text manufacturer summaries never attribute a facility."""
    manufacturer_data = product.get("manufacturer_data")
    top = manufacturer_data.get("top_manufacturer") if isinstance(manufacturer_data, dict) else None
    top = top if isinstance(top, dict) else {}
    manufacturer_id = str(top.get("manufacturer_id") or "").strip()
    if not (top.get("found") and _norm(top.get("match_type")) == "exact" and manufacturer_id):
        return {"state": "no_canonical_manufacturer"}
    entry = brand_testing_posture._top_manufacturers_by_id().get(manufacturer_id) or {}
    links = [link for link in entry.get("facility_registrations") or [] if isinstance(link, dict)]
    if not links:
        return {"state": "no_sourced_registration"}

    from cert_resolver import normalize_brand

    registry = _cert_registry()
    programs = facility_audit_programs()
    for link in links:
        record = registry.record_by_id(link.get("registry_record_id"))
        if (
            record is None
            or _norm(record.get("scope")) != "facility"
            or record.get("program") not in programs
            or record.get("_recency_status") not in _USABLE_RECENCY
            or normalize_brand(record.get("brand") or "") != normalize_brand(link.get("registered_company") or "")
        ):
            continue
        return {
            "state": "resolved",
            "program": record["program"],
            "registered_company": record.get("brand"),
            "record_id": record.get("record_id"),
            "relationship": link.get("relationship"),
            "evidence_url": link.get("evidence_url"),
            "source_url": record.get("source_url"),
            "snapshot_date": record.get("_snapshot_date"),
            "recency_status": record.get("_recency_status"),
        }
    return {"state": "registry_row_stale_or_missing"}


def audited_gmp_evidence(product: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """The one GMP decision: ``{"basis", "detail"}`` when a verified product
    certification requires a GMP audit, or the canonical manufacturer is
    listed in an audited GMP facility registry; otherwise None."""
    program = gmp_implied_by_verified_cert(product)
    if program:
        return {"basis": "verified_certification", "detail": program}
    facility = facility_audit_resolution(product)
    if facility["state"] == "resolved":
        return {
            "basis": "manufacturer_facility",
            "detail": f"{facility['program']}: {facility['registered_company']}",
        }
    return None
