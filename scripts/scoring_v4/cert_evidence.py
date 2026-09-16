"""Certification evidence shared by every v4 trust scorer, confidence and export.

One owner for three facts that used to be copied between generic_trust,
omega_trust and confidence (and re-implemented in build_final_db):

- which verified certification rows belong to this product's brand;
- which certification programs require an audited GMP facility
  (``implies_gmp`` policy in data/cert_claim_rules.json);
- whether this product has audited GMP evidence at all.

Label GMP wording (a "GMP"/"cGMP" claim, an NSF GMP mark, FDA facility
registration) is self-asserted and never counts as audited GMP.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from scoring_v4.modules.brand_testing_posture import gmp_facility_evidence

_CERT_CLAIM_RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "cert_claim_rules.json"

# The only bases on which GMP counts as audited. Trust modules emit one of these
# as ``gmp_basis``; the Verification pillar and the export accept nothing else.
AUDITED_GMP_BASES = frozenset({"verified_certification", "manufacturer_facility"})


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
        return True
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


def verified_product_cert_entries(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registry rows that verify THIS product: sku/product_line scope, not
    blocked by the resolver, and matched to this product's brand. Brand-only,
    claimed-only and needs-review rows never verify a product."""
    return [
        entry for entry in verified_cert_entries(product)
        if not entry.get("scoring_blocked_reason")
        and _norm(entry.get("scope")) in {"sku", "product_line"}
        and cert_entry_brand_matches_product(product, entry)
    ]


def gmp_implied_by_verified_cert(product: Dict[str, Any]) -> Optional[str]:
    """The product-verifying certification whose program audits GMP, or None."""
    programs = gmp_implying_programs()
    for entry in verified_product_cert_entries(product):
        if _norm(entry.get("program")) in programs:
            return entry.get("program")
    return None


def audited_gmp_evidence(product: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """The one GMP decision: ``{"basis", "detail"}`` when a verified
    certification requires a GMP audit or an exact manufacturer facility record
    names a certified/audited facility; otherwise None."""
    program = gmp_implied_by_verified_cert(product)
    if program:
        return {"basis": "verified_certification", "detail": program}
    facility = gmp_facility_evidence(product)
    if facility:
        return {"basis": "manufacturer_facility", "detail": facility}
    return None
