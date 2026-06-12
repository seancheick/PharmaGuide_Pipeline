"""Guard: UMLS CUI identifiers must NOT live in IQM `aliases` match lists.

Aliases are the product-name match namespace. A CUI string (e.g. "C0065527")
can never match a product label, so it is inert clutter at best — and at worst
an UNVERIFIED or wrong concept masquerading as data (the file's CUI machinery
only validates the primary `cui` field; secondary CUIs dumped into aliases were
never verified, and at least one was a ghost: hmb carried C3640807, the
unrelated HMB-45 antibody concept, while its real cui C1995592 sits in `cui`).

Verified identifiers belong in `cui` / `rxcui` / `external_ids`, never in
`aliases`. This guard prevents re-pollution (2026-06 sweep removed 144).
"""
import json
import os
import re

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")
CUI_RE = re.compile(r"^C\d{7}$")


def _load():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _cui_aliases(iqm):
    """Yield (location, alias) for every CUI-format string found in any alias list."""
    for pk, pv in iqm.items():
        if pk == "_metadata" or not isinstance(pv, dict):
            continue
        for a in pv.get("aliases", []) or []:
            if CUI_RE.match(str(a).strip()):
                yield f"{pk}.aliases", a
        for fn, fd in (pv.get("forms") or {}).items():
            if not isinstance(fd, dict):
                continue
            for a in fd.get("aliases", []) or []:
                if CUI_RE.match(str(a).strip()):
                    yield f"{pk}::{fn}", a


def test_no_cui_format_strings_in_aliases():
    violations = list(_cui_aliases(_load()))
    assert not violations, (
        f"{len(violations)} CUI-format identifiers found in alias lists "
        f"(must live in `cui`/`external_ids`, not match aliases). "
        f"First 10: {violations[:10]}"
    )
