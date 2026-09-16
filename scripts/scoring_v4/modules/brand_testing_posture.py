"""Shared v4 brand-level testing posture helper.

This is deliberately separate from B4a SKU/product-line certification credit.
It grants only a low trust signal when the existing manufacturer corpus has
explicit testing/certification evidence for an exact top-manufacturer match.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
import json
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
TOP_MANUFACTURERS_PATH = REPO_ROOT / "scripts" / "data" / "top_manufacturers_data.json"

from scoring_v4.quality_score_config import block as _cfg_block

_VM = _cfg_block("verification_magnitudes", "brand_testing")["brand_testing"]


BRAND_TESTING_HARD_EVIDENCE_SCORE = _VM["hard_evidence_score"]
BRAND_TESTING_SOFT_QUALITY_SCORE = _VM["soft_quality_score"]

HARD_TESTING_EVIDENCE_RE = re.compile(
    r"("
    r"third[\s-]?party|"
    r"certificates?\s+of\s+analysis|\bcoa\b|\bcoas\b|"
    r"public\s+lookup|batch[\s-]?quality|"
    r"iso[\s-]?accredited\s+lab\s+testing|"
    r"\bnsf\b|\busp\b|\bifos\b|"
    r"informed[\s-]?choice|informed[\s-]?sport|"
    r"\bbscg\b|consumerlab|labdoor"
    r")",
    re.IGNORECASE,
)

SOFT_QUALITY_POSTURE_RE = re.compile(
    r"("
    r"non[\s-]?gmo\s+project|usda\s+organic|certified\s+organic"
    r")",
    re.IGNORECASE,
)

# Audited GMP facility evidence: the audit / certification / registration /
# licensing wording must attach to the GMP program or the facility itself
# ("NSF GMP-registered", "GMP certified", "certified manufacturing",
# "TGA-registered GMP facility"). "cGMP-compliant" is a manufacturer statement,
# "IFOS-certified fish oil" or "NSF certification" certifies products, and FDA
# facility registration is not an audit (Codex audit 2026-09-16).
AUDITED_GMP_FACILITY_RE = re.compile(
    r"("
    r"\b(?:NSF|NPA|UL(?:\s+Solutions)?)[\s-]*GMP[\s-]*(?:registered|certified|audited)\b|"
    r"\bc?GMP[\s-]*(?:certified|certification|certifications|certs|registered|audited)\b|"
    r"\b(?:certified|registered|audited|licensed)[\s-]+(?:c?GMP[\s-]+)?"
    r"(?:facility|facilities|manufacturing|production)\b|"
    r"\bc?GMP\s+(?:and|&)\s+(?:ISO|HACCP|SQF|NSF)\s+(?:certified|registered)\b|"
    r"\bc?GMP\s+licens\w*|"
    r"\bNatural\s+Products\s+Association\s+certified\b|"
    r"\bTGA[\s-]*registered\b"
    r")",
    re.IGNORECASE,
)
_FDA_REGISTRATION_RE = re.compile(r"\bFDA[\s-]*registered\b", re.IGNORECASE)
_PRODUCT_SCOPE_RE = re.compile(r"\b(?:select|many|some|certain)\s+products\b", re.IGNORECASE)


def is_audited_gmp_facility_evidence(text: str) -> bool:
    """True when manufacturer evidence names an audited GMP facility."""
    text = str(text or "")
    if _PRODUCT_SCOPE_RE.search(text):
        return False
    for match in AUDITED_GMP_FACILITY_RE.finditer(text):
        window = text[max(0, match.start() - 20):match.end()]
        if not _FDA_REGISTRATION_RE.search(window):
            return True
    return False


def gmp_facility_evidence(product: Dict[str, Any]) -> str | None:
    """Return explicit facility/manufacturing GMP evidence for an exact top-
    manufacturer match, or None.

    This is intentionally stricter than product-specific cert→GMP inference.
    Product certs such as NSF Sport / USP Verified can imply GMP only for the
    matched SKU/product line through certification_data. Manufacturer-level B4b
    needs explicit GMP/facility/manufacturing wording.
    """
    if not isinstance(product, dict):
        return None
    top = _safe_dict(_safe_dict(product.get("manufacturer_data")).get("top_manufacturer"))
    if not (top.get("found") and _norm(top.get("match_type")) == "exact"):
        return None
    manufacturer_id = str(top.get("manufacturer_id") or "").strip()
    if not manufacturer_id:
        return None
    entry = _top_manufacturers_by_id().get(manufacturer_id)
    if not isinstance(entry, dict):
        return None
    for item in entry.get("evidence", []):
        if isinstance(item, str) and is_audited_gmp_facility_evidence(item):
            return item[:60]
    return None


def score_brand_testing_posture(product: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Return low brand-level testing posture score and audit metadata."""
    if not isinstance(product, dict):
        return 0.0, {"source": None, "matched_evidence": []}

    top = _safe_dict(_safe_dict(product.get("manufacturer_data")).get("top_manufacturer"))
    if not (top.get("found") and _norm(top.get("match_type")) == "exact"):
        return 0.0, {"source": None, "matched_evidence": []}

    manufacturer_id = str(top.get("manufacturer_id") or "").strip()
    if not manufacturer_id:
        return 0.0, {"source": None, "matched_evidence": []}

    entry = _top_manufacturers_by_id().get(manufacturer_id)
    if not entry:
        return 0.0, {
            "source": None,
            "manufacturer_id": manufacturer_id,
            "matched_evidence": [],
        }

    hard_evidence = [
        str(item)
        for item in entry.get("evidence", [])
        if isinstance(item, str) and HARD_TESTING_EVIDENCE_RE.search(item)
    ]
    soft_evidence = [
        str(item)
        for item in entry.get("evidence", [])
        if isinstance(item, str) and SOFT_QUALITY_POSTURE_RE.search(item)
    ]
    if not hard_evidence and not soft_evidence:
        return 0.0, {
            "source": None,
            "manufacturer_id": manufacturer_id,
            "matched_evidence": [],
        }

    if hard_evidence:
        return BRAND_TESTING_HARD_EVIDENCE_SCORE, {
            "source": "top_manufacturers_data.json",
            "manufacturer_id": manufacturer_id,
            "evidence_strength": "hard_testing",
            "matched_evidence": hard_evidence[:3],
        }

    return BRAND_TESTING_SOFT_QUALITY_SCORE, {
        "source": "top_manufacturers_data.json",
        "manufacturer_id": manufacturer_id,
        "evidence_strength": "soft_quality_posture",
        "matched_evidence": soft_evidence[:3],
    }


@lru_cache(maxsize=1)
def _top_manufacturers_by_id() -> Dict[str, Dict[str, Any]]:
    try:
        data = json.loads(TOP_MANUFACTURERS_PATH.read_text())
    except Exception:
        return {}
    rows = data.get("top_manufacturers", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()
