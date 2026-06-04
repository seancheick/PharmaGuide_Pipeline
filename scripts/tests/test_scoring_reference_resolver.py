"""Shared scoring reference resolver — Step 2 of the botanical-ownership root fix.

The resolver is the single source of truth for "what dose/quality reference
family applies to an ingredient", consumed by BOTH the contract and the scorer
(dependency direction: contract -> shared resolver <- scorer). It must never
import scorer/contract internals.

`rda_therapeutic_dosing.json` membership is EVIDENCE, not ownership.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def test_has_therapeutic_reference_true_for_db_botanicals():
    from scoring_reference_resolver import has_therapeutic_reference

    assert has_therapeutic_reference(name="Elderberry") is True
    assert has_therapeutic_reference(name="Grape Seed Extract") is True
    assert has_therapeutic_reference(canonical_id="elderberry") is True


def test_has_therapeutic_reference_false_for_nutrient_sources():
    from scoring_reference_resolver import has_therapeutic_reference

    # Acerola / Vitamin C have no botanical therapeutic dose range -> evidence absent.
    assert has_therapeutic_reference(name="Acerola") is False
    assert has_therapeutic_reference(canonical_id="vitamin_c", name="Vitamin C") is False


def test_reference_family_vitamin_is_rda_ul():
    from scoring_reference_resolver import reference_family

    res = reference_family(canonical_id="vitamin_c", name="Vitamin C", domain="vitamin")
    assert res.family == "rda_ul"


def test_reference_family_therapeutic_botanical_matches_with_high_confidence():
    from scoring_reference_resolver import reference_family

    res = reference_family(name="Elderberry", domain="herb")
    assert res.family == "botanical_therapeutic"
    assert res.matched_reference_id is not None
    assert res.confidence == "high"
    assert res.reason_code == "therapeutic_reference_matched"
    assert res.source_path == "data/rda_therapeutic_dosing.json"


def test_reference_family_botanical_without_reference_is_low_confidence():
    from scoring_reference_resolver import reference_family

    # Acerola is herb-domain (a source botanical) but has no therapeutic range:
    # family is botanical_therapeutic but the reference is absent -> low confidence.
    res = reference_family(name="Acerola", domain="herb")
    assert res.family == "botanical_therapeutic"
    assert res.matched_reference_id is None
    assert res.confidence == "low"
    assert res.reason_code == "no_therapeutic_reference"


def test_reference_family_by_domain_for_omega_probiotic_sports():
    from scoring_reference_resolver import reference_family

    assert reference_family(domain="omega_epa_dha").family == "omega"
    assert reference_family(domain="probiotic_strain").family == "probiotic"
    assert reference_family(domain="sports_active").family == "sports"


def test_reference_family_unknown_for_generic_active():
    from scoring_reference_resolver import reference_family

    assert reference_family(canonical_id="d_mannose", domain="generic_active").family == "unknown"


def test_resolver_does_not_import_scorer_or_contract():
    import scoring_reference_resolver as r

    source = Path(r.__file__).read_text()
    assert "import scoring_v4" not in source
    assert "from scoring_v4" not in source
    assert "import scoring_input_contract" not in source
    assert "from scoring_input_contract" not in source


def test_therapeutic_index_parity_with_botanical_profile_dosing_index():
    """Resolver and the live scorer must agree on therapeutic-reference membership."""
    from scoring_reference_resolver import _therapeutic_index
    from scoring_v4.modules.botanical_profile import _dosing_index

    assert set(_therapeutic_index().keys()) == set(_dosing_index().keys())
