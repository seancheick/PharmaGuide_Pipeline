"""
Data-integrity guard — harmful_additives free-text must not contradict the
structured ``severity_level``.

When ``severity_level`` is retuned (e.g. moderate -> low) but the ``notes`` /
``safety_summary`` free-text still asserts the OLD severity ("Moderate severity
due to …"), that stale text bakes into the app's per-product detail blobs on the
next build — a clinician/user reads "Moderate severity" beside a low badge. This
is the exact class fixed for ADD_CORN_SYRUP_SOLIDS; this test makes it a
permanent invariant (also closes the guardrail gap flagged in the pipeline
review: nothing cross-checked free-text against structured severity).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "harmful_additives.json"

# Matches the adjective form only ("moderate severity"), NOT the correct
# narrative form ("so severity is low") — so a properly-worded low entry that
# says "severity is low" is not flagged.
_SEVERITY_ADJ = re.compile(r"\b(low|moderate|high)\s+severity\b", re.IGNORECASE)
_TEXT_FIELDS = ("notes", "safety_summary", "reason", "mechanism", "safety_note")


def _load_additives():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return data["harmful_additives"]


def test_free_text_severity_matches_structured_severity_level():
    violations = []
    for entry in _load_additives():
        sev = str(entry.get("severity_level") or "").lower()
        if sev not in {"low", "moderate", "high"}:
            continue
        for field in _TEXT_FIELDS:
            text = entry.get(field)
            if not isinstance(text, str):
                continue
            for match in _SEVERITY_ADJ.finditer(text):
                claimed = match.group(1).lower()
                if claimed != sev:
                    violations.append(
                        f"{entry.get('id')}: severity_level={sev!r} but {field} says "
                        f"{match.group(0)!r}"
                    )
    assert not violations, "Stale severity text contradicts severity_level:\n" + "\n".join(violations)
