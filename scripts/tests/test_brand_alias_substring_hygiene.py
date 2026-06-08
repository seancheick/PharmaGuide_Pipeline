"""Hygiene: remove 2-3 char brand aliases that false-match as SUBSTRINGS.

`_brand_mentioned` does a substring `term in all_text` check. Aliases 'ps'
(BRAND_PHOSPHATIDYLSERINE), 'asi' (BRAND_NITROSIGINE), 'nr' (BRAND_NIAGEN) match
inside unrelated words ("ca[ps]ule", "qu[asi]", "evening primrose oil" → "..n r.."),
so generic/unrelated products wrongly pass the brand-evidence guard. The full-name
aliases (phosphatidylserine / arginine silicate / nicotinamide riboside) cover real
products; the short abbreviations are ambiguous defects. Found during the Step-10 P1
evidence-matcher audit (2026-06-08); the broader Defect-A fix is staged pending a
per-compound evidence-validity review.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def _study(enricher, sid):
    return next(s for s in enricher.databases["backed_clinical_studies"]["backed_clinical_studies"]
               if s.get("id") == sid)


@pytest.mark.parametrize("sid,gone,kept", [
    ("BRAND_PHOSPHATIDYLSERINE", "ps", "phosphatidylserine"),
    ("BRAND_NITROSIGINE", "asi", "arginine silicate"),
    ("BRAND_NIAGEN", "nr", "nicotinamide riboside"),
])
def test_short_substring_alias_removed_full_name_kept(enricher, sid, gone, kept) -> None:
    study = _study(enricher, sid)
    aliases = [a.lower() for a in study.get("aliases", [])]
    assert gone not in aliases, f"{gone!r} is a substring-bug alias and must be removed"
    # the full compound name remains reachable via standard_name OR an alias
    reachable = kept in str(study.get("standard_name", "")).lower() or any(kept in a for a in aliases)
    assert reachable, f"{kept!r} must remain reachable (standard_name or alias)"


@pytest.mark.parametrize("name,sid", [
    ("Multivitamin Veggie Capsules", "BRAND_PHOSPHATIDYLSERINE"),  # 'ps' in 'capsules'
    ("Evening Primrose Oil", "BRAND_NIAGEN"),                       # 'nr' substring
])
def test_substring_does_not_pass_brand_guard(enricher, name, sid) -> None:
    study = _study(enricher, sid)
    product = {"fullName": name, "activeIngredients": []}
    assert enricher._brand_mentioned(study["standard_name"], study["aliases"], product) is False
