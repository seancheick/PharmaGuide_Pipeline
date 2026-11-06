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

import pytest

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


def test_is_known_botanical_distinguishes_real_botanicals_from_compounds():
    from scoring_reference_resolver import is_known_botanical

    assert is_known_botanical(name="Ashwagandha") is True
    assert is_known_botanical(name="Boswellia serrata") is True
    # Setria/glutathione are branded non-botanical compounds, not botanicals.
    assert is_known_botanical(name="Setria") is False
    assert is_known_botanical(canonical_id="glutathione") is False


def test_resolver_does_not_import_scorer_or_contract():
    import scoring_reference_resolver as r

    source = Path(r.__file__).read_text()
    assert "import scoring_v4" not in source
    assert "from scoring_v4" not in source
    assert "import scoring_input_contract" not in source
    assert "from scoring_input_contract" not in source


def test_iqm_reference_entry_owns_canonical_category_lookup():
    from scoring_reference_resolver import iqm_reference_entry

    assert iqm_reference_entry("turmeric")["category"] == "herbs"
    assert iqm_reference_entry("leuconostoc_cremoris")["category"] == "probiotics"
    assert iqm_reference_entry("not_a_real_canonical_id") is None


def test_parent_relative_form_quality_normalizes_best_eligible_form_to_fifteen():
    from scoring_reference_resolver import parent_relative_form_quality

    # Vitamin D currently tops out at 14; D3 at 12 retains its within-parent
    # ratio when projected onto the 15-point Formulation scale.
    assert parent_relative_form_quality("vitamin_d", 14.0) == 15.0
    assert round(parent_relative_form_quality("vitamin_d", 12.0), 6) == 12.857143


def test_parent_relative_form_quality_falls_back_to_stored_scale_without_parent():
    from scoring_reference_resolver import parent_relative_form_quality

    assert parent_relative_form_quality("not_a_real_canonical_id", 12.0) == 12.0


def test_therapeutic_index_parity_with_botanical_profile_dosing_index():
    """Resolver and the live scorer must agree on therapeutic-reference membership."""
    from scoring_reference_resolver import _therapeutic_index
    from scoring_v4.modules.botanical_profile import _dosing_index

    assert set(_therapeutic_index().keys()) == set(_dosing_index().keys())


def test_every_parent_form_reference_is_pinned():
    """Each IQM parent's best eligible form is the reference its products are
    scored against, computed at runtime. Adding a better form, or changing a
    bio_score or review status, silently moves every product of that parent.
    Sean ratified the runtime reference on 2026-09-28 as the interim rule
    (scripts/audits/rr_correctness_20260928/CALIBRATION_PACKET.md item 1) on
    condition that no reference moves unnoticed. When this fails, measure the
    parent's products with replay.py, then update
    fixtures/iqm_parent_form_references.json in the same commit."""
    import json
    from pathlib import Path

    from scoring_reference_resolver import iqm_reference_index, parent_best_form_quality

    pinned = json.loads(
        (Path(__file__).parent / "fixtures" / "iqm_parent_form_references.json").read_text()
    )
    current = {cid: parent_best_form_quality(cid) for cid in iqm_reference_index()}
    moved = {
        cid: (pinned.get(cid, "unpinned"), current.get(cid, "removed"))
        for cid in set(pinned) | set(current)
        if pinned.get(cid, "unpinned") != current.get(cid, "removed")
    }
    assert moved == {}, f"parent form references moved (pinned, now): {moved}"


def test_eaa_evidence_reference_never_borrows_mixture_dose_values():
    from scoring_reference_resolver import nutritional_role_reference, rda_ul_reference_entry
    reference = nutritional_role_reference('l_leucine')
    assert set(reference) == {'id', 'source_references'}
    assert reference['id'] == 'essential_amino_acids'
    assert reference['source_references'][0]['supports_claims'] == ['established_nutritional_role']
    mixture = rda_ul_reference_entry(canonical_id='essential_amino_acids')
    assert mixture['reference_semantics']['reference_type'] == 'no_benchmark'
    assert mixture['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'


def test_eaa_identity_family_import_and_route_reexport_perform_no_data_reads(monkeypatch):
    import importlib
    import scoring_reference_resolver as resolver
    import scoring_v4.route_features as routes
    def forbidden(*args, **kwargs):
        raise AssertionError('Identity family import must not read pipeline files')
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_text', forbidden)
        patch.setattr(Path, 'open', forbidden)
        importlib.reload(resolver)
        importlib.reload(routes)
        assert routes.EAA_CANONICALS is resolver.EAA_CANONICALS
        assert len(routes.EAA_CANONICALS) == 9


@pytest.mark.parametrize(('source', 'expected'), [
    ('D-alpha-tocopherol', True),
    ('dl-alpha-tocopheryl acetate', True),
    ('d-alpha tocopheryl succinate', True),
    ('α-tocopherol', True),
    ('d-alpha-tocopheryl acetate with mixed tocotrienols', True),
    ('mixed tocopherols with alpha-tocopherol', True),
    ('Alpha-tocopherol-free gamma-tocopherol', False),
    ('Gamma-tocopherol (not alpha-tocopherol)', False),
    ('Gamma-tocopherols', False),
    ('Delta-tocopherols', False),
    ('Gamma-Tocopherol', False),
    ('D-delta-tocopherol', False),
    ('beta-tocopherol', False),
    ('Alpha-Tocotrienol', False),
    ('D-Mixed Tocotrienols', False),
    ('Mixed Tocopherols', None),
    ('Mixed Tocotrienols/Tocopherols', None),
    ('Vitamin E', None),
    ('unidentified preparation', None),
    ('', None),
])
def test_vitamin_e_alpha_material_keeps_identity_separate_from_amount(source, expected):
    from scoring_reference_resolver import vitamin_e_alpha_material

    # Unknown material may contain alpha, but does not prove an alpha amount.
    assert vitamin_e_alpha_material(source) is expected


def test_existing_dri_sources_reach_role_reference_without_a_second_identity_list():
    from evidence_resolver import _dietary_nutrient_authority
    from scoring_reference_resolver import _rda_ul_index, nutritional_role_reference

    # Derive coverage from existing source/reference owners, not a new nutrient registry.
    count = 0
    entries = {entry["id"]: entry for entry in _rda_ul_index().values()}
    for entry in entries.values():
        canonical = entry.get('id')
        if not _dietary_nutrient_authority(canonical):
            continue
        urls = (entry.get('reference_semantics') or {}).get('source_ids') or []
        if not urls or not any('ods.od.nih.gov' in str(u) or 'nationalacademies.org' in str(u) for u in urls):
            continue
        reference = nutritional_role_reference(canonical)
        assert reference and reference['source_references'], canonical
        for identity in [canonical, *entry.get('aliases', [])]:
            authority = _dietary_nutrient_authority(identity)
            if authority:
                joined = nutritional_role_reference(authority['nutrient'])
                assert joined['source_references'] == reference['source_references'], identity
        for ref in reference['source_references']:
            assert ref['title'] and ref['url']
            assert ref['type'] == 'authority'
            assert not ref.get('pmid')
            if canonical == 'chromium':
                assert 'established_nutritional_role' not in ref['supports_claims']
                assert 'disputed' in ref['notes'].lower()
        count += 1
    assert count >= 28


def test_source_reference_dedup_preserves_authored_metadata_over_pmid_only_fallback():
    from scoring_reference_resolver import unique_source_references
    authored = {'pmid': '18184094', 'title': 'Authored source title',
                'url': 'https://pubmed.ncbi.nlm.nih.gov/18184094/'}
    assert unique_source_references([authored, {'pmid': '18184094'}]) == [authored]
    assert unique_source_references([{'pmid': '18184094'}, authored]) == [authored]


def test_source_reference_dedup_keeps_distinct_authored_claim_scopes():
    from scoring_reference_resolver import unique_source_references
    first = {'pmid': '18184094', 'title': 'Authored source',
             'supports_claims': ['nutritional_intake']}
    second = {**first, 'supports_claims': ['population_scope']}
    assert unique_source_references([first, second, {'pmid': '18184094'}]) == [first, second]
    assert unique_source_references([{'pmid': '18184094'}, first, second]) == [first, second]


def test_chloride_role_cites_primary_dri_without_rewriting_existing_dose_source():
    from scoring_reference_resolver import nutritional_role_reference, rda_ul_reference_entry
    reference = nutritional_role_reference('chloride')['source_references']
    assert len(reference) == 1
    assert reference[0]['doi'] == '10.17226/10925'
    assert reference[0]['title'] == (
        'Dietary Reference Intakes for Water, Potassium, Sodium, Chloride, and Sulfate')
    assert reference[0]['url'] == 'https://www.nationalacademies.org/read/10925/chapter/8'
    assert '272' in reference[0]['notes']
    assert rda_ul_reference_entry(canonical_id='chloride')['reference_semantics']['source_ids'] == [
        'https://nap.nationalacademies.org/skim.php?chap=386-396&record_id=11537']
