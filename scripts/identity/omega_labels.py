"""One reader for what an omega label row names.

The cleaner decides whether a row is a blend header and the scoring contract
decides whether a row owns an EPA+DHA amount. Both are asking the same
question about the same text, so they ask it here.
"""

from __future__ import annotations

import re
from typing import Any

_EPA_TOKEN_RE = re.compile(r"\b(?:epa|eicosapentaenoic)\b")
_DHA_TOKEN_RE = re.compile(r"\b(?:dha|docosahexaenoic)\b")
# Any other fatty acid on the row means the mass is not EPA+DHA alone. Oil and
# source words are deliberately absent from the filler set: "Fish Oil (EPA/DHA)"
# is carrier mass, not an EPA+DHA amount.
_OTHER_FATTY_ACID_TOKEN_RE = re.compile(
    r"\b(?:ala|alpha\s*linolenic|linolenic|dpa|docosapentaenoic|linoleic|oleic|"
    r"omega\s*6|omega\s*9|gla|cla|sda|eta)\b"
)
_FILLER_TOKEN_RE = re.compile(
    r"\b(?:omega\s*3|omega|fatty|acids?|total|combined|and|plus|as|the)\b"
)


def states_only_epa_and_dha(name: Any) -> bool:
    """True when a row names EPA and DHA and nothing else it could be measuring.

    Nature Made prints the combined marine dose as "Omega-3 EPA & DHA" or
    "EPA (Eicosapentaenoic Acid) and DHA (Docosahexaenoic Acid)"; Up & Up prints
    "EPA/DHA". Those rows state a disclosed dose. A row naming another fatty
    acid, an oil or a source is not covered.
    """
    normalized = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()
    if not normalized:
        return False
    if _OTHER_FATTY_ACID_TOKEN_RE.search(normalized):
        return False
    if not (_EPA_TOKEN_RE.search(normalized) and _DHA_TOKEN_RE.search(normalized)):
        return False
    residue = _EPA_TOKEN_RE.sub(" ", normalized)
    residue = _DHA_TOKEN_RE.sub(" ", residue)
    residue = _FILLER_TOKEN_RE.sub(" ", residue)
    return not residue.strip()
