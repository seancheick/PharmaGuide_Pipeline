"""Cross-compound alias guard.

Enforces the rule from feedback_user_strict_chemistry_verification:
aliases must map only to identical compounds (same CUI / UNII /
PubChem CID). Cross-compound aliasing is forbidden.

This is the rule that the 2026-05-01 SPM aliasing first-pass violated
(Resolvin D5 / Protectin DX were aliased onto the 17-HDHA precursor —
distinct PubChem CIDs, distinct UMLS CUIs). The fix landed in commit
TBD-AT-COMMIT after this test was added. This test prevents recurrence.

Implementation strategy: build a global alias index across IQM, where
each alias-string maps to the (entry_id, form_id, identifiers) it
appears under. If the SAME alias-string appears under two entries with
DIFFERENT external identifiers (CUI / PubChem CID / UNII), that's a
cross-compound aliasing violation.

Whitelisted exceptions: parent-level aliases that are GENERIC TERMS
(e.g. "Resolvins", "Protectins") legitimately route to a precursor
because no preformed bioactive is supplemented commercially. These are
documented in ALLOWED_GENERIC_TERMS below.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ingredient_quality_map.json"

# Generic / family terms that legitimately alias to a precursor or
# umbrella entry rather than the literal compound. Documented per
# Decision 4 (SPM Mapping Policy 2026-05-01).
ALLOWED_GENERIC_TERMS = {
    # SPM family terms — products typically contain precursors not actual SPMs
    "resolvins",
    "protectins",
    "spms",
    "spm precursors",
    "specialized pro-resolving mediators",
}

# Pre-existing cross-compound alias situations baselined as of 2026-05-01.
# These are real ontology violations from earlier sessions. Listed here so
# the test passes today but BLOCKS NEW additions. Each should eventually be
# cleaned up — the entry that "owns" the alias should keep it, the others
# should drop it. Tracked separately in REMAINING_UNMAPPED_TEAM_GUIDE.md.
#
# Format: each tuple is the alias_lower string. The test allows any alias
# in this set to appear on multiple entries with different identifiers.
# DO NOT ADD TO THIS LIST without explicit clinician/dev review — this is
# the legacy-debt allowlist, not an "easy way out".
BASELINE_KNOWN_CROSS_COMPOUND_ALIASES = {
    # Captured 2026-05-01 from /tmp/baseline_violations.py — 52 pre-existing
    # cross-compound alias situations from earlier sessions. Each falls into
    # one of these classes (cleanup approach noted on each cluster):
    #
    # 1. Fatty-acid form descriptors (form-class names appearing on multiple
    #    parent fatty-acid entries). Cleanup: route form-only labels to
    #    fish_oil parent; remove from per-FA entries.
    "ethyl esters",
    "triglycerides",
    "triglyceride",
    "triglycerides natural",
    "cis-9-octadecenoic acid",  # oleic acid IUPAC name on multiple entries
    # 2. Source-vs-compound pairings (rice bran/sea buckthorn = SOURCE of
    #    a compound, not the compound). Cleanup: remove from source entry.
    "gamma-oryzanol", "oryzanol",
    "ip6", "inositol hexaphosphate",
    "sea buckthorn oil",            # palmitoleic acid alias
    "algal dha", "dha from algae",  # algae_oil/dha conflict
    # 3. Combination products (single chemical entity but mineral+vitamin
    #    or salt+salt; appears on each component's entry).
    "dolomite",                       # CaMg(CO3)2
    "nicotinamide ascorbate",
    "ascorbate niacinamide",
    "niacinamide ascorbate supplement",
    "nicotinamide ascorbate supplement",
    "microcrystalline hydroxyapatite",  # Ca + P
    "tricalcium phosphate", "tribasic calcium phosphate", "tcp",
    "calcium hydrogen phosphate", "dcp",
    # 4. Element vs salt forms
    "vanadium", "vanadium sulfate", "vanadyl",
    "magnesium beta hydroxybutyrate",
    "magnesium beta-hydroxybutyrate",
    "magnesium creatine chelate",
    # 5. Generic / family terms shared across related parents
    "akba",                          # boswellic acid, multiple boswellia forms
    "bovine pancreas",
    "bromelain",
    "cranberry pacs",
    "fos", "fructooligosaccharides",
    "gos", "galactooligosaccharides",
    "xos", "xylo-oligosaccharides",
    "green tea egcg",
    "glutamate", "glutamic acid", "l-glutamic acid",
    "monosodium glutamate", "msg",
    "nicotinamide adenine dinucleotide",
    "omega 7", "omega-7", "omega-9",
    "phosphatidylcholine complex",
    "proanthocyanidins",
    "vitexin",
}


def _load_iqm() -> dict:
    return json.loads(DATA.read_text())


def _entry_identifiers(entry: dict) -> tuple:
    """Return a (cui, pubchem_cid, unii) tuple. None for missing."""
    cui = entry.get("cui")
    ext = entry.get("external_ids") or {}
    return (
        cui,
        ext.get("pubchem_cid"),
        ext.get("unii"),
    )


def _form_identifiers(form: dict, parent_ids: tuple) -> tuple:
    """Form-level identifiers fall back to parent if not specified."""
    ext = form.get("external_ids") or {}
    return (
        ext.get("cui") or parent_ids[0],
        ext.get("pubchem_cid") or parent_ids[1],
        ext.get("unii") or parent_ids[2],
    )


def _identifiers_match(a: tuple, b: tuple) -> bool:
    """Two identifier tuples represent same compound iff at least one
    identifier matches (CUI or PubChem CID or UNII) AND no two non-None
    identifiers conflict."""
    matches = 0
    for ai, bi in zip(a, b):
        if ai and bi:
            if ai == bi:
                matches += 1
            else:
                return False  # conflicting identifier = different compound
    return matches > 0


def test_no_cross_compound_aliases():
    """No alias string should appear on two entries with conflicting
    identifiers (CUI / PubChem CID / UNII)."""
    data = _load_iqm()

    # alias_lower -> list of (entry_id, form_id, identifiers, source)
    alias_index: dict[str, list[tuple]] = defaultdict(list)

    for eid, entry in data.items():
        if eid.startswith("_") or not isinstance(entry, dict):
            continue
        parent_ids = _entry_identifiers(entry)

        for alias in entry.get("aliases") or []:
            if not isinstance(alias, str):
                continue
            alias_index[alias.lower().strip()].append(
                (eid, "<parent>", parent_ids, "parent")
            )

        for fname, form in (entry.get("forms") or {}).items():
            if not isinstance(form, dict):
                continue
            form_ids = _form_identifiers(form, parent_ids)
            for alias in form.get("aliases") or []:
                if not isinstance(alias, str):
                    continue
                alias_index[alias.lower().strip()].append(
                    (eid, fname, form_ids, "form")
                )

    violations = []
    for alias, occurrences in alias_index.items():
        if len(occurrences) < 2:
            continue
        if alias in ALLOWED_GENERIC_TERMS:
            continue
        if alias in BASELINE_KNOWN_CROSS_COMPOUND_ALIASES:
            continue
        # Compare every pair
        for i in range(len(occurrences)):
            for j in range(i + 1, len(occurrences)):
                a = occurrences[i]
                b = occurrences[j]
                if a[0] == b[0]:
                    # same parent entry — different forms can coexist;
                    # within-entry duplicates are caught by other tests
                    continue
                if not _identifiers_match(a[2], b[2]):
                    violations.append(
                        f"alias {alias!r} appears under "
                        f"{a[0]}/{a[1]} (ids={a[2]}) AND "
                        f"{b[0]}/{b[1]} (ids={b[2]}) — "
                        f"distinct compounds; cross-compound aliasing forbidden"
                    )

    assert not violations, (
        "Cross-compound aliasing violations found:\n  - "
        + "\n  - ".join(violations)
    )


def test_specific_spm_compounds_have_distinct_entries():
    """Regression guard for the 2026-05-01 SPM ontology fix.

    Resolvin D5 and Protectin DX must each have their OWN entry with
    PubChem CID, NOT be aliased onto the 17-HDHA precursor."""
    data = _load_iqm()

    # Both must exist as distinct top-level entries
    assert "resolvin_d5" in data, (
        "resolvin_d5 IQM entry missing — Resolvin D5 has distinct PubChem "
        "CID 24932575 and must not be aliased to 17-HDHA precursor"
    )
    assert "protectin_dx" in data, (
        "protectin_dx IQM entry missing — Protectin DX has distinct PubChem "
        "CID 11968800 and must not be aliased to 17-HDHA precursor"
    )

    # Verify identifiers
    rvd5 = data["resolvin_d5"]
    assert rvd5.get("cui") == "C3492734", (
        f"resolvin_d5 CUI must be C3492734 (verified UMLS), got {rvd5.get('cui')}"
    )
    assert rvd5.get("external_ids", {}).get("pubchem_cid") == 24932575, (
        "resolvin_d5 PubChem CID must be 24932575"
    )

    pdx = data["protectin_dx"]
    assert pdx.get("cui") == "C3886642", (
        f"protectin_dx CUI must be C3886642 (verified UMLS), got {pdx.get('cui')}"
    )
    assert pdx.get("external_ids", {}).get("pubchem_cid") == 11968800, (
        "protectin_dx PubChem CID must be 11968800"
    )

    # 17-HDHA must NOT alias them
    omega3 = data.get("omega_3", {})
    hdha_form = (omega3.get("forms") or {}).get(
        "17-hydroxy-docosahexaenoic acid (17-HDHA)"
    ) or {}
    hdha_aliases = [a.lower() for a in (hdha_form.get("aliases") or [])]
    assert "resolvin d5" not in hdha_aliases, (
        "Resolvin D5 must NOT be aliased on 17-HDHA precursor (distinct compound)"
    )
    assert "protectin dx" not in hdha_aliases, (
        "Protectin DX must NOT be aliased on 17-HDHA precursor (distinct compound)"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
