from __future__ import annotations

import re
from typing import Any


# The app joins catalog products to curated interaction rows through
# key_ingredient_tags. These tags must represent clean ingredient identity;
# regulatory posture is carried by verdict/safety fields and warnings.
INTERACTION_CANONICAL_ALIASES: dict[str, str] = {
    "BANNED_RED_YEAST_RICE": "red_yeast_rice",
    "banned_red_yeast_rice": "red_yeast_rice",
    "BANNED_CBD_US": "cbd",
    "banned_cbd_us": "cbd",
    "NOOTROPIC_VINPOCETINE": "vinpocetine",
    # Kava is canonicalized to its active-compound id `kavalactones` (used by
    # DSI_SEDATIVES_KAVA, the ingredient_interaction_rules.json subject, and
    # the catalog key_ingredient_tags). Normalize the risk-flavored
    # SSI_KAVA_ACETAMINOPHEN id onto it so both kava interactions join the
    # same product identity.
    "RISK_KAVA": "kavalactones",
    "risk_kava": "kavalactones",
}

INTERACTION_TEXT_TAG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(red\s+yeast\s+rice|monascus\s+purpureus|monacolin\s+k)\b",
            re.I,
        ),
        "red_yeast_rice",
    ),
    (re.compile(r"\b(cbd|cannabidiol)\b", re.I), "cbd"),
    (re.compile(r"\bvinpocetine\b", re.I), "vinpocetine"),
)


def normalize_interaction_canonical_id(value: Any) -> str | None:
    """Return the catalog-facing canonical used for interaction lookup."""
    if value is None:
        return None
    canonical = str(value).strip()
    if not canonical:
        return None
    return INTERACTION_CANONICAL_ALIASES.get(canonical, canonical)


def normalize_catalog_interaction_tag(value: Any) -> str | None:
    """Normalize a product-side ingredient tag for interaction lookup."""
    canonical = normalize_interaction_canonical_id(
        str(value or "").lower().replace(" ", "_")
    )
    return canonical or None


def interaction_tags_from_text(*values: Any) -> list[str]:
    text = " ".join(str(v) for v in values if str(v or "").strip())
    if not text:
        return []
    return [
        canonical_id
        for pattern, canonical_id in INTERACTION_TEXT_TAG_PATTERNS
        if pattern.search(text)
    ]
