"""
Schema enforcement tests for ingredient_quality_map.json v3.0.0

Ensures hardening stays permanent by validating:
- No cross-ingredient alias duplicates
- No empty aliases on forms
- match_rules present and valid
- absorption_structured present and valid
- relationships refer to existing IDs only

Run with: pytest tests/test_ingredient_quality_map_schema.py -v
"""

import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

# Path to the ingredient quality map file
IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def iqm_data():
    """Load the ingredient quality map data once for all tests."""
    with open(IQM_PATH, 'r') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def entries(iqm_data):
    """Extract entries (excluding metadata)."""
    return {k: v for k, v in iqm_data.items() if k != '_metadata'}


@pytest.fixture(scope='module')
def metadata(iqm_data):
    """Extract metadata."""
    return iqm_data.get('_metadata', {})


# =============================================================================
# SCHEMA VERSION TESTS
# =============================================================================

class TestSchemaVersion:
    """Verify schema version is 3.0.0+"""

    def test_schema_version_exists(self, metadata):
        """Schema version must be present."""
        assert 'schema_version' in metadata, "Missing schema_version in metadata"

    def test_schema_version_is_5(self, metadata):
        """Schema version must be 5.x.x"""
        version = metadata.get('schema_version', '')
        assert version.startswith('5.'), f"Expected schema version 5.x.x, got {version}"


# =============================================================================
# ALIAS TESTS (A-IQM-1 Enforcement)
# =============================================================================

class TestAliasQuality:
    """Enforce alias quality requirements from A-IQM-1."""

    def test_no_cross_ingredient_duplicate_aliases(self, entries):
        """No alias should map to multiple different ingredients."""
        # Known acceptable cross-ingredient aliases (hierarchical relationships)
        ALLOWED_CROSS_ALIASES = {
            'beta-sitosterol',       # beta_sitosterol IS a phytosterol
            # Phosphorus/calcium shared forms — preferred_parent disambiguates by label nutrient
            'calcium phosphate',     # phosphorus/phosphate salts + calcium/calcium phosphate
            'tricalcium phosphate',  # phosphorus/phosphate salts + calcium/calcium phosphate
            'tcp',                   # abbreviation for tricalcium phosphate
            'tribasic calcium phosphate',  # synonym for tricalcium phosphate
            'calcium hydroxyapatite',      # phosphorus/phosphate salts + calcium/calcium hydroxyapatite
            'microcrystalline hydroxyapatite',  # phosphorus/phosphate salts + calcium/calcium hydroxyapatite
            'hydroxyapatite',        # phosphorus/phosphate salts + calcium/calcium hydroxyapatite
            'dicalcium phosphate dihydrate',  # phosphorus/dicalcium phosphate + dicalcium_phosphate parent
            'calcium hydrogen phosphate',    # phosphorus/dicalcium phosphate + dicalcium_phosphate parent
            # DCP shared between phosphorus/dicalcium phosphate and dicalcium_phosphate parent forms
            'dcp',                   # phosphorus/dicalcium phosphate + dicalcium_phosphate forms
            # Niacinamide ascorbate shared between vitamin_c and vitamin_b3_niacin
            'niacinamide ascorbate',      # vitamin_c + vitamin_b3_niacin — preferred_parent by label
            'nicotinamide ascorbate',     # vitamin_c + vitamin_b3_niacin
            'vitamin c niacinamide',      # vitamin_c + vitamin_b3_niacin
            'ascorbate niacinamide',      # vitamin_c + vitamin_b3_niacin
            'niacinamide ascorbate supplement',  # vitamin_c + vitamin_b3_niacin
            'nicotinamide ascorbate supplement', # vitamin_c + vitamin_b3_niacin
            # Dolomite — CaMg(CO3)2 — shared between calcium/calcium_carbonate + magnesium/magnesium_carbonate
            'dolomite',
            # BHB mineral salts — shared between d_beta_hydroxybutyrate_bhb + mineral parent
            'magnesium beta-hydroxybutyrate',
            # Creatine magnesium chelate — shared between creatine_monohydrate + magnesium
            'magnesium creatine chelate',
            # Constituent stubs — aliases shared with parent botanical extract
            'green tea egcg',           # egcg stub + green_tea_extract
            'cranberry pacs',           # pac stub + cranberry
            'proanthocyanidin',         # D2.9.1: pac stub + cranberry form (singular)
            'epigallocatechin gallate', # egcg stub + epigallocatechin_gallate
            'proanthocyanidins',        # pac stub + proanthocyanidins
            'ginsenoside rg3',          # rg3 stub + ginsenosides
            'akba',                     # AKBA primary marker for boswellia 5-Loxin/Aflapin + dedicated stub
            'vitexin',                  # Vitexin primary marker for hawthorn extracts + dedicated stub
            # Fish oil concentrate — shared between fish_oil/molecularly distilled + omega_3/ethyl ester
            'concentrated fish oil',
            # Generic form qualifiers — always looked up within an already-matched parent context,
            # so cross-parent occurrence is safe (form lookup is parent-scoped, not global)
            'triglycerides',        # dha/fish_oil triglyceride, epa/fish_oil triglyceride, omega_3 natural TG
            'triglyceride',         # same as above (singular form)
            'triglycerides natural', # natural TG form — dha + epa + omega_3 entries
            'ethyl esters',         # EE form — dha/epa/fish_oil/omega_3 ethyl ester entries
            # Prebiotic/oligosaccharide overlap — FOS/GOS/XOS are both prebiotics AND oligosaccharides
            'fos', 'fructooligosaccharides', 'gos', 'galactooligosaccharides',
            'xos', 'xylo-oligosaccharides',
            # Omega fatty acid parent/child — oleic acid IS an omega-9, palmitoleic IS an omega-7
            'oleic acid', 'cis-9-octadecenoic acid', 'omega-9',
            'omega 7', 'omega-7', 'sea buckthorn oil',
            # Vanadium/vanadyl sulfate — vanadyl_sulfate is a form of vanadium
            'vanadium', 'vanadium sulfate', 'vanadyl', 'vanadyl sulfate',
            # NAD+ precursor pathway — NR, NMN, NADH are all NAD+ precursors with own entries
            'nicotinamide riboside', 'nr', 'nicotinamide mononucleotide', 'nmn',
            'nicotinamide adenine dinucleotide',
            # Milk thistle / silymarin parent-child
            'silymarin', 'silybin', 'silibinin', 'milk thistle extract',
            # Lecithin / choline / phosphatidylserine / soy overlap
            'lecithin', 'soy lecithin', 'sunflower lecithin',
            'soy', 'soybean',
            # Phytosome delivery technology — phospholipid/phosphatidylcholine
            # complex binds multiple botanical actives (grape seed, green tea,
            # curcumin, etc.). Shared alias is safe because form lookup is
            # parent-scoped after parent resolution.
            'phospholipid complex', 'phosphatidylcholine complex',
            # Glutamate / glutamic acid overlap
            'glutamic acid', 'l-glutamic acid',
            # Orotate mineral salts — shared between mineral + orotic_acid
            'magnesium orotate', 'lithium orotate',
            # Rice bran / gamma-oryzanol / IP6 overlap
            'gamma-oryzanol', 'oryzanol', 'inositol hexaphosphate', 'ip6',
            # Naringin / naringenin parent-child
            'naringin',
            # ─── Added by IQM audit 2026-04-24 — Phase 2 whitelist expansion ───
            'algal dha',  # algae_oil + dha (source + molecule)
            'dha from algae',  # algae_oil + dha (source + molecule)
            # ─── Added by IQM audit 2026-04-24 — Step 3b post-dedup residuals ───
            'probiotics',  # probiotic_unspecified (deprecated) + probiotics umbrella
            'probiotic',  # probiotic_unspecified (deprecated) + probiotics umbrella
            'probiotic bacteria',  # probiotic_unspecified (deprecated) + probiotics umbrella
            'glutamate',  # glutamate (pending audit) + l_glutamic_acid
            'monosodium glutamate',  # glutamate (pending audit) + l_glutamic_acid
            'msg',  # glutamate (pending audit) + l_glutamic_acid
            'bovine pancreas',  # digestive_enzymes + organ_extracts (shared animal source material)
        }

        alias_map = defaultdict(list)

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    for alias in form_data.get('aliases', []):
                        alias_lower = alias.lower().strip()
                        alias_map[alias_lower].append(ing_key)

        # Find aliases that map to multiple ingredients (excluding known allowed)
        duplicates = {
            alias: list(set(ings))
            for alias, ings in alias_map.items()
            if len(set(ings)) > 1 and alias not in ALLOWED_CROSS_ALIASES
        }

        assert len(duplicates) == 0, (
            f"Found {len(duplicates)} cross-ingredient duplicate aliases:\n"
            + "\n".join(f"  '{a}': {i}" for a, i in list(duplicates.items())[:10])
        )

    def test_no_empty_aliases_on_forms(self, entries):
        """Every form must have at least one alias."""
        empty_alias_forms = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    aliases = form_data.get('aliases', [])
                    if not aliases:
                        empty_alias_forms.append((ing_key, form_name))

        assert len(empty_alias_forms) == 0, (
            f"Found {len(empty_alias_forms)} forms with empty aliases:\n"
            + "\n".join(f"  {ing}/{form}" for ing, form in empty_alias_forms[:10])
        )

    def test_no_overly_generic_aliases(self, entries):
        """Aliases should not be overly generic single words."""
        FORBIDDEN_ALIASES = {'standard', 'unspecified', 'natural', 'synthetic', 'generic'}
        violations = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    for alias in form_data.get('aliases', []):
                        if alias.lower().strip() in FORBIDDEN_ALIASES:
                            violations.append((ing_key, form_name, alias))

        assert len(violations) == 0, (
            f"Found {len(violations)} overly generic aliases:\n"
            + "\n".join(f"  {ing}/{form}: '{alias}'" for ing, form, alias in violations[:10])
        )

    def test_no_within_ingredient_alias_collisions(self, entries):
        """Aliases should not appear in multiple forms under the same parent ingredient.

        This prevents ambiguity when matching branded forms vs generic forms.
        For example, 'ashwagandha' should not appear in both 'KSM-66 ashwagandha'
        and 'ashwagandha (unspecified)' - the matcher wouldn't know which to pick.
        """
        collisions = []

        for parent_key, parent_data in entries.items():
            forms = parent_data.get('forms', {})

            # Build alias map for this parent only
            alias_to_forms = defaultdict(list)
            for form_name, form_data in forms.items():
                if isinstance(form_data, dict):
                    for alias in form_data.get('aliases', []):
                        alias_lower = alias.lower().strip()
                        alias_to_forms[alias_lower].append(form_name)

            # Find aliases that appear in multiple forms
            parent_collisions = [
                (alias, form_list)
                for alias, form_list in alias_to_forms.items()
                if len(form_list) > 1
            ]
            if parent_collisions:
                collisions.append((parent_key, parent_collisions))

        assert len(collisions) == 0, (
            f"Found {len(collisions)} parent ingredients with within-ingredient alias collisions:\n"
            + "\n".join(
                f"  {parent}: '{coll[0][0]}' in {coll[0][1]}"
                for parent, coll in collisions[:10]
            )
        )


# =============================================================================
# MATCH RULES TESTS (A-IQM-2 Enforcement)
# =============================================================================

class TestMatchRules:
    """Enforce match_rules requirements from A-IQM-2."""

    def test_all_ingredients_have_match_rules(self, entries):
        """Every ingredient must have a match_rules block."""
        missing = [k for k, e in entries.items() if not e.get('match_rules')]
        assert len(missing) == 0, (
            f"Found {len(missing)} ingredients without match_rules:\n"
            + "\n".join(f"  {k}" for k in missing[:10])
        )

    def test_match_rules_has_priority(self, entries):
        """match_rules must have a priority field."""
        invalid = []
        for ing_key, entry in entries.items():
            mr = entry.get('match_rules', {})
            if 'priority' not in mr:
                invalid.append(ing_key)

        assert len(invalid) == 0, (
            f"Found {len(invalid)} match_rules without priority:\n"
            + "\n".join(f"  {k}" for k in invalid[:10])
        )

    def test_match_rules_has_match_mode(self, entries):
        """match_rules must have a match_mode field."""
        invalid = []
        for ing_key, entry in entries.items():
            mr = entry.get('match_rules', {})
            if 'match_mode' not in mr:
                invalid.append(ing_key)

        assert len(invalid) == 0, (
            f"Found {len(invalid)} match_rules without match_mode:\n"
            + "\n".join(f"  {k}" for k in invalid[:10])
        )

    def test_match_rules_priority_valid_range(self, entries):
        """Priority must be 0, 1, or 2."""
        VALID_PRIORITIES = {0, 1, 2}
        invalid = []

        for ing_key, entry in entries.items():
            priority = entry.get('match_rules', {}).get('priority')
            if priority not in VALID_PRIORITIES:
                invalid.append((ing_key, priority))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid priorities:\n"
            + "\n".join(f"  {k}: {p}" for k, p in invalid[:10])
        )

    def test_match_rules_has_exclusions(self, entries):
        """match_rules should have exclusions list."""
        missing = []
        for ing_key, entry in entries.items():
            mr = entry.get('match_rules', {})
            if 'exclusions' not in mr:
                missing.append(ing_key)

        assert len(missing) == 0, (
            f"Found {len(missing)} match_rules without exclusions:\n"
            + "\n".join(f"  {k}" for k in missing[:10])
        )

    def test_match_mode_enum_valid(self, entries):
        """match_mode must be one of supported matcher gates."""
        valid_modes = {"exact", "normalized", "alias_and_fuzzy"}
        invalid = []
        for ing_key, entry in entries.items():
            mode = (entry.get("match_rules") or {}).get("match_mode")
            if mode not in valid_modes:
                invalid.append((ing_key, mode))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid match_mode values:\n"
            + "\n".join(f"  {k}: {m}" for k, m in invalid[:10])
        )


# =============================================================================
# ABSORPTION TESTS (A-IQM-3 Enforcement)
# =============================================================================

class TestAbsorptionStructured:
    """Enforce absorption_structured requirements from A-IQM-3."""

    def test_all_forms_have_absorption_structured(self, entries):
        """Every form must have absorption_structured."""
        missing = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    if not form_data.get('absorption_structured'):
                        missing.append((ing_key, form_name))

        assert len(missing) == 0, (
            f"Found {len(missing)} forms without absorption_structured:\n"
            + "\n".join(f"  {ing}/{form}" for ing, form in missing[:10])
        )

    def test_absorption_structured_has_quality(self, entries):
        """absorption_structured must have a quality field."""
        invalid = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    ab = form_data.get('absorption_structured', {})
                    if 'quality' not in ab:
                        invalid.append((ing_key, form_name))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} absorption_structured without quality:\n"
            + "\n".join(f"  {ing}/{form}" for ing, form in invalid[:10])
        )

    def test_absorption_quality_valid_values(self, entries):
        """absorption quality must be from valid enum."""
        VALID_QUALITIES = {
            'unknown', 'poor', 'low', 'moderate', 'good', 'very_good', 'excellent', 'variable'
        }
        invalid = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    quality = form_data.get('absorption_structured', {}).get('quality')
                    if quality and quality not in VALID_QUALITIES:
                        invalid.append((ing_key, form_name, quality))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid absorption qualities:\n"
            + "\n".join(f"  {ing}/{form}: '{q}'" for ing, form, q in invalid[:10])
        )

    def test_absorption_value_valid_range(self, entries):
        """absorption value must be valid: 0-1 for percentage OR >1 for multipliers."""
        invalid = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    ab = form_data.get('absorption_structured', {})
                    value = ab.get('value')
                    is_relative = ab.get('is_relative', False)
                    if value is not None:
                        if not isinstance(value, (int, float)) or value < 0:
                            invalid.append((ing_key, form_name, value, "must be non-negative number"))
                        elif value > 1 and not is_relative:
                            # Values >1 are allowed if marked as relative (multipliers like 4.5x)
                            # Check if it's a reasonable multiplier (up to 100x)
                            if value > 100:
                                invalid.append((ing_key, form_name, value, "unreasonable multiplier"))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid absorption values:\n"
            + "\n".join(f"  {ing}/{form}: {v} ({r})" for ing, form, v, r in invalid[:10])
        )


# =============================================================================
# RELATIONSHIP TESTS (A-IQM-6 Enforcement)
# =============================================================================

class TestRelationships:
    """Enforce relationship integrity from A-IQM-6."""

    def test_relationships_refer_to_existing_ids(self, entries):
        """All relationship target_ids must exist in the database."""
        broken = []

        for ing_key, entry in entries.items():
            for rel in entry.get('relationships', []):
                target_id = rel.get('target_id')
                if target_id and target_id not in entries:
                    broken.append((ing_key, target_id))

        assert len(broken) == 0, (
            f"Found {len(broken)} broken relationship references:\n"
            + "\n".join(f"  {ing} -> {target}" for ing, target in broken[:10])
        )

    def test_relationship_types_valid(self, entries):
        """Relationship types must be from valid enum."""
        VALID_TYPES = {
            'form_of', 'active_in', 'contains', 'parent_of',
            'metabolite_of', 'source_of', 'category_for', 'combines'
        }
        invalid = []

        for ing_key, entry in entries.items():
            for rel in entry.get('relationships', []):
                rel_type = rel.get('type')
                if rel_type and rel_type not in VALID_TYPES:
                    invalid.append((ing_key, rel_type))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid relationship types:\n"
            + "\n".join(f"  {ing}: '{t}'" for ing, t in invalid[:10])
        )


# =============================================================================
# DATA QUALITY TESTS (A-IQM-7 Enforcement)
# =============================================================================

class TestDataQuality:
    """Enforce data_quality requirements from A-IQM-7."""

    def test_all_ingredients_have_data_quality(self, entries):
        """Every ingredient must have a data_quality block."""
        missing = [k for k, e in entries.items() if not e.get('data_quality')]
        assert len(missing) == 0, (
            f"Found {len(missing)} ingredients without data_quality:\n"
            + "\n".join(f"  {k}" for k in missing[:10])
        )

    def test_data_quality_has_review_status(self, entries):
        """data_quality must have review_status."""
        invalid = []
        for ing_key, entry in entries.items():
            dq = entry.get('data_quality', {})
            if 'review_status' not in dq:
                invalid.append(ing_key)

        assert len(invalid) == 0, (
            f"Found {len(invalid)} data_quality without review_status:\n"
            + "\n".join(f"  {k}" for k in invalid[:10])
        )

    def test_data_quality_completeness_valid(self, entries):
        """Completeness must be between 0 and 1."""
        invalid = []
        for ing_key, entry in entries.items():
            completeness = entry.get('data_quality', {}).get('completeness')
            if completeness is not None:
                if not isinstance(completeness, (int, float)) or completeness < 0 or completeness > 1:
                    invalid.append((ing_key, completeness))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid completeness values:\n"
            + "\n".join(f"  {k}: {c}" for k, c in invalid[:10])
        )


# =============================================================================
# CUI/RXCUI TESTS (A-IQM-5 Enforcement)
# =============================================================================

class TestCuiRxcui:
    """Enforce CUI/RxCUI hygiene from A-IQM-5."""

    def test_null_cui_has_note(self, entries):
        """If CUI is null, cui_note must be present."""
        orphans = []
        for ing_key, entry in entries.items():
            if entry.get('cui') is None and not entry.get('cui_note'):
                orphans.append(ing_key)

        assert len(orphans) == 0, (
            f"Found {len(orphans)} null CUI without cui_note:\n"
            + "\n".join(f"  {k}" for k in orphans[:10])
        )

    def test_null_rxcui_has_note(self, entries):
        """If RxCUI is null, rxcui_note must be present."""
        orphans = []
        for ing_key, entry in entries.items():
            if entry.get('rxcui') is None and not entry.get('rxcui_note'):
                orphans.append(ing_key)

        assert len(orphans) == 0, (
            f"Found {len(orphans)} null RxCUI without rxcui_note:\n"
            + "\n".join(f"  {k}" for k in orphans[:10])
        )


# =============================================================================
# CATEGORY TESTS (A-IQM-4 Enforcement)
# =============================================================================

class TestCategories:
    """Enforce category normalization from A-IQM-4."""

    def test_all_ingredients_have_category(self, entries):
        """Every ingredient must have a category."""
        missing = [k for k, e in entries.items() if not e.get('category')]
        assert len(missing) == 0, (
            f"Found {len(missing)} ingredients without category:\n"
            + "\n".join(f"  {k}" for k in missing[:10])
        )

    def test_category_enum_present(self, entries):
        """All ingredients should have category_enum."""
        missing = [k for k, e in entries.items() if not e.get('category_enum')]
        # This is advisory, not mandatory
        if missing:
            pytest.skip(f"{len(missing)} ingredients missing category_enum (advisory)")

    def test_category_enum_matches_category(self, entries):
        """category_enum should mirror category for parent-level consistency."""
        mismatches = []
        for ing_key, entry in entries.items():
            category = entry.get("category")
            category_enum = entry.get("category_enum")
            if category and category_enum and category != category_enum:
                mismatches.append((ing_key, category, category_enum))

        assert len(mismatches) == 0, (
            f"Found {len(mismatches)} category/category_enum mismatches:\n"
            + "\n".join(f"  {k}: category={c}, category_enum={ce}" for k, c, ce in mismatches[:10])
        )


# =============================================================================
# BIO SCORE TESTS
# =============================================================================

class TestBioScore:
    """Enforce bio_score validity."""

    def test_bio_score_valid_range(self, entries):
        """bio_score must be between 1 and 15."""
        invalid = []

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    bio = form_data.get('bio_score')
                    if bio is not None:
                        if not isinstance(bio, (int, float)) or bio < 1 or bio > 15:
                            invalid.append((ing_key, form_name, bio))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} invalid bio_scores:\n"
            + "\n".join(f"  {ing}/{form}: {b}" for ing, form, b in invalid[:10])
        )

    def test_score_matches_bio_and_natural_formula(self, entries):
        """score must be deterministic: bio_score + 3 if natural else bio_score."""
        mismatches = []
        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get("forms", {}).items():
                if not isinstance(form_data, dict):
                    continue
                bio = form_data.get("bio_score")
                natural = bool(form_data.get("natural", False))
                score = form_data.get("score")
                if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
                    expected = bio + (3 if natural else 0)
                    if score != expected:
                        mismatches.append((ing_key, form_name, bio, natural, score, expected))

        assert len(mismatches) == 0, (
            f"Found {len(mismatches)} score/bio_score mismatches:\n"
            + "\n".join(
                f"  {ing}/{form}: bio={bio}, natural={nat}, score={score}, expected={expected}"
                for ing, form, bio, nat, score, expected in mismatches[:10]
            )
        )

    def test_dosage_importance_numeric(self, entries):
        """dosage_importance should be numeric to avoid silent scorer fallback."""
        invalid = []
        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get("forms", {}).items():
                if not isinstance(form_data, dict):
                    continue
                value = form_data.get("dosage_importance")
                if value is None:
                    continue
                if not isinstance(value, (int, float)):
                    invalid.append((ing_key, form_name, value))

        assert len(invalid) == 0, (
            f"Found {len(invalid)} non-numeric dosage_importance values:\n"
            + "\n".join(f"  {ing}/{form}: {v!r}" for ing, form, v in invalid[:10])
        )


# =============================================================================
# IDENTIFIER STANDARDIZATION TESTS (A-IQM-8 Enforcement)
# =============================================================================

class TestIdentifierStandardization:
    """Enforce the IQM identifier hierarchy:
      Parent level: cui (concept), rxcui (drug), external_ids.unii (representative)
      Form level: forms[name].external_ids.unii (chemical substance identity)
    No top-level leaks of chemical identifiers (unii, cas, pubchem_cid).
    """

    def test_no_top_level_unii(self, entries):
        """UNII must be in external_ids.unii, never top-level entry.unii."""
        leaks = [k for k, e in entries.items() if 'unii' in e and e['unii']]
        assert len(leaks) == 0, (
            f"Found {len(leaks)} entries with top-level 'unii' (should be in external_ids):\n"
            + "\n".join(f"  {k}: {entries[k]['unii']}" for k in leaks[:10])
        )

    def test_no_top_level_cas(self, entries):
        """CAS must be in external_ids.cas, never top-level."""
        leaks = [k for k, e in entries.items() if 'cas' in e and e['cas']]
        assert len(leaks) == 0, (
            f"Found {len(leaks)} entries with top-level 'cas' (should be in external_ids):\n"
            + "\n".join(f"  {k}" for k in leaks[:10])
        )

    def test_no_top_level_pubchem_cid(self, entries):
        """PubChem CID must be in external_ids.pubchem_cid, never top-level."""
        leaks = [k for k, e in entries.items() if 'pubchem_cid' in e and e['pubchem_cid']]
        assert len(leaks) == 0, (
            f"Found {len(leaks)} entries with top-level 'pubchem_cid' (should be in external_ids):\n"
            + "\n".join(f"  {k}" for k in leaks[:10])
        )

    def test_external_ids_is_always_dict(self, entries):
        """external_ids must be a dict on every entry (never None or missing)."""
        invalid = []
        for k, e in entries.items():
            ext = e.get('external_ids')
            if ext is None or not isinstance(ext, dict):
                invalid.append((k, type(ext).__name__))
        assert len(invalid) == 0, (
            f"Found {len(invalid)} entries with non-dict external_ids:\n"
            + "\n".join(f"  {k}: {t}" for k, t in invalid[:10])
        )

    def test_aliases_is_always_list(self, entries):
        """aliases must be a list on every entry (never None or missing)."""
        invalid = []
        for k, e in entries.items():
            aliases = e.get('aliases')
            if aliases is None or not isinstance(aliases, list):
                invalid.append((k, type(aliases).__name__))
        assert len(invalid) == 0, (
            f"Found {len(invalid)} entries with non-list aliases:\n"
            + "\n".join(f"  {k}: {t}" for k, t in invalid[:10])
        )

    def test_no_null_valued_fields(self, entries):
        """No field should be present with a None value. Absent is fine, None is not."""
        violations = []
        for k, e in entries.items():
            for field, value in e.items():
                if value is None:
                    violations.append((k, field))
        assert len(violations) == 0, (
            f"Found {len(violations)} null-valued fields (remove the key instead):\n"
            + "\n".join(f"  {k}.{f}" for k, f in violations[:10])
        )

    def test_cui_is_string_when_present(self, entries):
        """CUI stays at parent level and must be a string when present."""
        invalid = [(k, type(e['cui']).__name__) for k, e in entries.items()
                    if 'cui' in e and not isinstance(e['cui'], str)]
        assert len(invalid) == 0, (
            f"Found {len(invalid)} non-string CUI values:\n"
            + "\n".join(f"  {k}: {t}" for k, t in invalid[:10])
        )

    def test_form_external_ids_is_dict_when_present(self, entries):
        """Form-level external_ids must be a dict when present."""
        invalid = []
        for k, e in entries.items():
            for fname, fdata in e.get('forms', {}).items():
                if not isinstance(fdata, dict):
                    continue
                fext = fdata.get('external_ids')
                if fext is not None and not isinstance(fext, dict):
                    invalid.append((k, fname, type(fext).__name__))
        assert len(invalid) == 0, (
            f"Found {len(invalid)} forms with non-dict external_ids:\n"
            + "\n".join(f"  {k}/{fn}: {t}" for k, fn, t in invalid[:10])
        )

    def test_no_duplicate_form_names_across_parents(self, entries):
        """Each form name must be unique across all parents (prevents UNII conflicts)."""
        from collections import defaultdict
        form_parents = defaultdict(list)
        for k, e in entries.items():
            for fname in e.get('forms', {}):
                form_parents[fname.lower()].append(k)
        dupes = {fn: parents for fn, parents in form_parents.items() if len(parents) > 1}
        assert len(dupes) == 0, (
            f"Found {len(dupes)} form names shared across multiple parents:\n"
            + "\n".join(f"  '{fn}' → {parents}" for fn, parents in list(dupes.items())[:10])
        )

    def test_no_duplicate_form_uniis(self, entries):
        """Each form UNII must be unique (one chemical substance = one location)."""
        unii_locs = {}
        conflicts = []
        for k, e in entries.items():
            for fname, fdata in e.get('forms', {}).items():
                if not isinstance(fdata, dict):
                    continue
                fext = fdata.get('external_ids', {})
                if isinstance(fext, dict) and fext.get('unii'):
                    unii = fext['unii']
                    loc = f"{k}/{fname}"
                    if unii in unii_locs:
                        conflicts.append(f"{unii}: {unii_locs[unii]} AND {loc}")
                    unii_locs[unii] = loc
        assert len(conflicts) == 0, (
            f"Found {len(conflicts)} duplicate form UNIIs:\n"
            + "\n".join(f"  {c}" for c in conflicts[:10])
        )

    def test_form_level_unii_coverage(self, entries):
        """At least 10% of forms should have form-level UNII (currently ~12%)."""
        total_forms = 0
        forms_with_unii = 0
        for e in entries.values():
            for fname, fdata in e.get('forms', {}).items():
                if not isinstance(fdata, dict):
                    continue
                total_forms += 1
                fext = fdata.get('external_ids', {})
                if isinstance(fext, dict) and fext.get('unii'):
                    forms_with_unii += 1
        rate = forms_with_unii / total_forms if total_forms else 0
        assert rate >= 0.10, (
            f"Form UNII coverage {rate:.1%} is below 10% threshold "
            f"({forms_with_unii}/{total_forms})"
        )


# =============================================================================
# SUMMARY TEST
# =============================================================================

class TestSummaryStatistics:
    """Print summary statistics (always passes)."""

    def test_summary_stats(self, entries, metadata):
        """Print summary statistics for the database."""
        total_forms = sum(len(e.get('forms', {})) for e in entries.values())
        total_aliases = sum(
            len(f.get('aliases', []))
            for e in entries.values()
            for f in e.get('forms', {}).values()
            if isinstance(f, dict)
        )
        with_relationships = sum(1 for e in entries.values() if e.get('relationships'))

        print(f"\n=== Ingredient Quality Map v{metadata.get('schema_version')} ===")
        print(f"Total ingredients: {len(entries)}")
        print(f"Total forms: {total_forms}")
        print(f"Total aliases: {total_aliases}")
        print(f"Ingredients with relationships: {with_relationships}")

        assert True  # Always pass
