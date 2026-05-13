"""
Metadata-contract gate for `scripts/data/*.json`.

Catches the off-by-N drift class introduced by commit 74aa9a0 (2026-05-12),
where `other_ingredients.json` shipped with 683 entries but `_metadata.total_entries`
remained at 681. That drift survived for ~24 hours and broke two tests in b04
once anyone ran them.

This test fails fast at commit time for any data file whose
`_metadata.total_entries` disagrees with the actual entry count, across
three recognized shapes:

* **single_array**: one top-level array besides `_metadata`. Entries are the
  array items. Example: `other_ingredients.json`.
* **single_payload_dict**: exactly one top-level dict besides `_metadata`.
  Entries are the keys of that wrapping dict (values may be dicts or lists —
  both shapes are valid). Examples: `botanical_marker_contributions.json`
  (entries are dicts), `cluster_ingredient_aliases.json` (entries are alias
  lists).
* **top_level_dict_of_dicts**: no nested wrapper — the top level itself is
  the entry map, and every non-`_metadata` value is a dict (one entry record
  per top-level key). Examples: `ingredient_quality_map.json` (621 entries),
  `enhanced_delivery.json` (78), `unit_mappings.json` (14).

Files with a different shape (multi-array, mixed scalar+dict, etc.) are
skipped — but only with an explicit `INTENTIONAL_EXCEPTIONS` entry that
names the bespoke per-file test pinning that file's semantic. Silent skips
are not permitted.
"""

import json
from pathlib import Path
from typing import Any, Optional

import pytest

DATA = Path(__file__).parent.parent / "data"

# Files whose shape doesn't match the universal classifier OR whose
# total_entries means something file-specific. Each entry MUST cite the
# bespoke per-file test that pins the semantic (no silent skips).
INTENTIONAL_EXCEPTIONS: dict[str, str] = {
    "ingredient_weights.json":
        "total_entries tracks dosage_weights tier count (4 — therapeutic / "
        "optimal / maintenance / trace), not the sum across multi-section "
        "payload. Pinned by test_ingredient_weights_contract.py.",
    "unit_conversions.json":
        "total_entries tracks vitamin_conversions only; mass_conversions, "
        "probiotic_conversions, and form_detection_patterns are static "
        "rule config, not vitamin entries. Pinned by "
        "test_unit_conversions_contract.py.",
    "cert_claim_rules.json":
        "total_entries = Σ(non-_-prefixed rule keys across rules.*), "
        "excluding each category's _metadata config sub-key. Pinned by "
        "test_cert_claim_rules_contract.py.",
    "manufacture_deduction_expl.json":
        "Structural config file (1 scalar total_deduction_cap + 4 nested "
        "dicts for violation_categories / modifiers / calculation_rules / "
        "score_thresholds). total_entries=5 tracks count of top-level "
        "non-_metadata sub-sections — meaningful but not entry-shaped. "
        "Pinned by test_manufacture_deduction_expl_contract.py.",
    "banned_match_allowlist.json":
        "total_entries tracks allowlist only; denylist is auxiliary and "
        "tracked separately. Pinned by "
        "test_banned_match_allowlist_contract.py.",
    "clinical_risk_taxonomy.json":
        "UNIQUE convention — total_entries = SUM of all 7 taxonomy arrays "
        "(conditions + drug_classes + severity_levels + evidence_levels + "
        "profile_flags + product_forms + sources). Pinned by "
        "test_clinical_risk_taxonomy_contract.py.",
    "color_indicators.json":
        "total_entries tracks natural_indicators only; artificial_indicators "
        "+ explicit_natural_dyes + explicit_artificial_dyes are auxiliary. "
        "Pinned by test_color_indicators_contract.py.",
    "functional_ingredient_groupings.json":
        "total_entries tracks functional_groupings only; vague_terms_to_flag "
        "+ transparency_bonuses are auxiliary. Pinned by "
        "test_functional_ingredient_groupings_contract.py.",
    "migration_report.json":
        "total_entries tracks alias_collisions_resolved (the headline number "
        "of this migration); other arrays/dicts are scaffolding. Pinned by "
        "test_migration_report_contract.py.",
    "fda_unii_cache.json":
        "Runtime cache file (name_to_unii + unii_to_name lookups, 170K+ "
        "entries each) populated by scripts/api_audit/fda_weekly_sync.py. "
        "Size fluctuates with each FDA UNII sync — a static total_entries "
        "would be meaningless and forced bumps per sync. Intentionally "
        "carries no total_entries; the cache file's freshness is tracked "
        "by _metadata.last_updated instead.",
    "percentile_categories.json":
        "Mixed-shape config (categories dict of 9 + classification_rules "
        "dict of 4 — both top-level). The 9 categories are the meaningful "
        "entry count; classification_rules are static config the scorer "
        "reads alongside. Pinned by test_percentile_categories_contract.py.",
}


def _classify_shape(blob: dict) -> Optional[tuple[str, int]]:
    """Return ``(shape_name, entry_count)`` if the file matches one of three
    universal shapes; ``None`` if it needs a bespoke per-file test.

    Shapes recognized:

    1. ``single_array``: exactly one top-level array besides ``_metadata``,
       no top-level dicts. Entry count = ``len(array)``.

    2. ``single_payload_dict``: exactly one top-level dict besides
       ``_metadata``, no top-level arrays. Entry count = number of keys in
       that wrapping dict. Inner values may be dicts (entry records) or
       lists (alias arrays) — count is what matters.

    3. ``top_level_dict_of_dicts``: 2+ top-level dicts besides ``_metadata``,
       no top-level arrays, no top-level scalars. Every non-``_metadata``
       value must be a dict (an entry record). Entry count = number of
       non-``_metadata`` keys.

    A file with mixed scalars+dicts at top level (e.g. config files like
    ``manufacture_deduction_expl.json``) falls through to ``None``.
    """
    non_meta = {k: v for k, v in blob.items() if k != "_metadata"}
    arrays = [(k, v) for k, v in non_meta.items() if isinstance(v, list)]
    dicts = [(k, v) for k, v in non_meta.items() if isinstance(v, dict)]

    # Shape 1: exactly one top-level array. Auxiliary top-level dicts
    # (e.g. side-lookups, classification settings) are permitted — the
    # array is the primary entry catalog and meta tracks its length.
    # Examples: clinically_relevant_strains.json (strains array + prebiotics
    # lookup), id_redirects.json (redirects array + lookup index),
    # ingredient_classification.json (skip_exact array + settings + classifications).
    if len(arrays) == 1:
        return ("single_array", len(arrays[0][1]))

    # Shape 2: single top-level dict (wrapper), no arrays, no other keys.
    if len(dicts) == 1 and not arrays and len(non_meta) == 1:
        return ("single_payload_dict", len(dicts[0][1]))

    # Shape 3: top-level IS the entry map — every non-meta value is a dict.
    # Excludes files with any scalar at top level (e.g. config files).
    if not arrays and dicts and len(non_meta) == len(dicts):
        return ("top_level_dict_of_dicts", len(non_meta))

    return None


def _candidate_files() -> list[Path]:
    return sorted(p for p in DATA.glob("*.json") if p.is_file())


@pytest.mark.parametrize(
    "path",
    _candidate_files(),
    ids=lambda p: p.name,
)
def test_metadata_total_entries_matches_entry_count(path: Path) -> None:
    """Every classifiable data file must have _metadata.total_entries match
    its entry count, where "entry count" is shape-defined (see _classify_shape).

    Drift means either:
      * an author added/removed entries without bumping _metadata, or
      * an author bumped _metadata without matching reality — either way,
        downstream consumers reading total_entries get a lie.

    If a file legitimately tracks something else under total_entries (e.g.
    a section of a multi-section payload), add it to INTENTIONAL_EXCEPTIONS
    with a rationale AND write a bespoke per-file test pinning the semantic.
    """
    blob = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(blob, dict) or "_metadata" not in blob:
        pytest.skip(f"{path.name}: no _metadata block")

    # INTENTIONAL_EXCEPTIONS is the FIRST check after _metadata exists so that
    # files with a decided semantic skip with their rationale + bespoke-test
    # pointer, regardless of whether they have total_entries or a recognized
    # shape. This is what makes "no silent skips" enforceable — every file in
    # the exceptions dict carries an explicit reason.
    if path.name in INTENTIONAL_EXCEPTIONS:
        pytest.skip(f"{path.name}: {INTENTIONAL_EXCEPTIONS[path.name]}")

    meta_total = blob["_metadata"].get("total_entries")
    if meta_total is None:
        pytest.skip(f"{path.name}: _metadata has no total_entries field")

    classification = _classify_shape(blob)
    if classification is None:
        pytest.skip(
            f"{path.name}: shape not recognized by universal classifier "
            f"(needs a bespoke per-file test; add to INTENTIONAL_EXCEPTIONS "
            f"with a pointer to that test)."
        )

    shape_name, actual = classification
    assert actual == meta_total, (
        f"{path.name}: _metadata.total_entries={meta_total} but "
        f"{shape_name} payload has {actual} entries. "
        f"Bump _metadata.total_entries to {actual} "
        f"(or, if the semantic intentionally differs, add to "
        f"INTENTIONAL_EXCEPTIONS with rationale + bespoke test)."
    )
