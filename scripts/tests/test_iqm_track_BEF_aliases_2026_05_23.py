"""IQM batch — Tracks B + E + F (small IQM batch from the NOT_SCORED triage slice).

Plan: reports/not_scored_triage/track_BEF_iqm_batch_plan.md

This file pins the IQM alias / form additions that close NOT_SCORED gaps
identified by Tracks E (form_unmapped) and F (no_quality_map_match) in the
NOT_SCORED triage. The additions are STRICTLY alias-only or form-only — no
new IQM parents, no invented bio_scores, no broadened semantic coverage.

Per dev review v2 (2026-05-23), the first three approved commits are:

  1. citrus_bergamot — add 'Citrus bergamia Risso fruit extract' +
     'Citrus bergamia Risso' to the 'bergamot (unspecified)' form aliases.
     Chemistry: 'Risso' is the botanical-authority designation for Antoine
     Risso (1813), same species as the existing 'citrus bergamia' alias.
     Affects Jarrow 211933 / 264734.

  2. isoflavones — add EXACT 'total Soy Isoflavones' + 'Soy Isoflavones' to
     existing 'soy isoflavones (genistein, daidzein)' form aliases (or
     create the form if it doesn't exist). Do NOT broaden beyond soy-specific
     terms — per dev review, no generic 'isoflavone' alias.
     Affects Solgar 201361.

  3. rna_dna — add 'Ribonucleic Acid' alias to existing rna_dna parent.
     Low bio_score preserved (oral RNA has limited clinical evidence).
     Affects Life Extension 231631.

Each commit is atomic per dev review cadence. Tests below are the data-layer
contract — the live-corpus delta is verified separately after the IQM edit.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: F401


IQM_PATH = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


# ---------------------------------------------------------------------------
# Commit #1: citrus_bergamot form alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_alias",
    [
        "Citrus bergamia Risso fruit extract",
        "Citrus bergamia Risso",
    ],
)
def test_citrus_bergamot_unspecified_form_includes_risso_aliases(iqm, expected_alias):
    """Jarrow Citrus Bergamot 500 mg (211933 / 264734) row.std_name is
    'Citrus bergamia Risso fruit extract' — must alias to the existing
    bergamot (unspecified) form. Risso is the botanical-authority
    designation for Antoine Risso, same Citrus bergamia species as the
    existing 'citrus bergamia' alias."""
    assert "citrus_bergamot" in iqm, "citrus_bergamot parent missing from IQM"
    forms = iqm["citrus_bergamot"].get("forms", {})
    assert "bergamot (unspecified)" in forms, (
        "Expected 'bergamot (unspecified)' form to exist on citrus_bergamot. "
        f"Available forms: {list(forms.keys())}"
    )
    aliases_lower = [a.lower() for a in forms["bergamot (unspecified)"].get("aliases", [])]
    assert expected_alias.lower() in aliases_lower, (
        f"alias {expected_alias!r} missing from citrus_bergamot."
        f"forms['bergamot (unspecified)'].aliases. "
        f"Jarrow Citrus Bergamot products will fall out of scored catalog."
    )


def test_citrus_bergamot_unspecified_form_bio_score_pinned(iqm):
    """Pin the conservative bio_score on the unspecified form. Adding the
    Risso alias must NOT touch the existing 12 bio_score (unspecified extract
    is intentionally lower than BPF=14 / standardized extract=12)."""
    form = iqm["citrus_bergamot"]["forms"]["bergamot (unspecified)"]
    assert form["bio_score"] == 12, (
        f"bergamot (unspecified) bio_score changed from 12 to {form['bio_score']} — "
        f"alias-add must not modify bio_score."
    )


# ---------------------------------------------------------------------------
# Commit #2: isoflavones soy-specific alias
# ---------------------------------------------------------------------------


def test_isoflavones_unspecified_form_includes_total_soy_isoflavones_alias(iqm):
    """Solgar Super Concentrated Isoflavones (201361) row.std_name is
    'total Soy Isoflavones' — must alias to the existing isoflavones parent.
    Per dev review: ONLY this exact label string. Do NOT broaden beyond
    soy/isoflavone terms (no generic 'isoflavone' alias added)."""
    assert "isoflavones" in iqm, "isoflavones parent missing from IQM"
    forms = iqm["isoflavones"].get("forms", {})
    assert "isoflavones (unspecified)" in forms
    aliases_lower = [a.lower() for a in forms["isoflavones (unspecified)"].get("aliases", [])]
    assert "total soy isoflavones" in aliases_lower, (
        "alias 'total Soy Isoflavones' missing from isoflavones."
        "forms['isoflavones (unspecified)'].aliases. "
        "Solgar Super Concentrated Isoflavones (201361) will stay NOT_SCORED."
    )


def test_isoflavones_unspecified_form_bio_score_pinned(iqm):
    """Pin the conservative bio_score = 8 on the unspecified isoflavones form.
    Isoflavones (unspecified) is intentionally low — class-level signal without
    specific genistein/daidzein standardization."""
    form = iqm["isoflavones"]["forms"]["isoflavones (unspecified)"]
    assert form["bio_score"] == 8, (
        f"isoflavones (unspecified) bio_score changed from 8 to {form['bio_score']} — "
        f"alias-add must not modify bio_score."
    )


def test_isoflavones_no_generic_isoflavone_alias_added(iqm):
    """Negative-scope guard: per dev review v2, the alias-add must NOT include
    a generic 'isoflavone' (singular) or any non-soy-specific term that would
    expand semantic coverage. Existing aliases are all soy-specific."""
    form = iqm["isoflavones"]["forms"]["isoflavones (unspecified)"]
    aliases_lower = {a.lower() for a in form.get("aliases", [])}
    # forbidden expansions
    assert "isoflavone" not in aliases_lower, (
        "Generic 'isoflavone' (singular) alias added — this broadens coverage "
        "beyond soy and is out of scope for this slice."
    )


# ---------------------------------------------------------------------------
# Commit #3: rna_dna full-name alias
# ---------------------------------------------------------------------------


def test_rna_dna_nucleic_acid_complex_form_includes_ribonucleic_acid_alias(iqm):
    """Life Extension RNA Capsules 500 mg (231631) row.name='Ribonucleic Acid'
    is the unabbreviated full chemical name for RNA. The existing
    'nucleic acid complex' form already includes 'rna' (abbreviation) as an
    alias; this adds the spelled-out variant. Form choice: the most
    conservative bio_score=4 form (oral RNA is degraded — per existing
    notes — so the low score is intentional)."""
    assert "rna_dna" in iqm, "rna_dna parent missing from IQM"
    forms = iqm["rna_dna"].get("forms", {})
    assert "nucleic acid complex" in forms
    aliases_lower = [a.lower() for a in forms["nucleic acid complex"].get("aliases", [])]
    assert "ribonucleic acid" in aliases_lower, (
        "alias 'Ribonucleic Acid' missing from rna_dna."
        "forms['nucleic acid complex'].aliases. "
        "Life Extension RNA Capsules (231631) will stay NOT_SCORED."
    )


def test_rna_dna_nucleic_acid_complex_bio_score_pinned(iqm):
    """Pin the very conservative bio_score = 4. Per the existing notes, oral
    RNA/DNA is completely degraded by pancreatic nucleases — the body
    synthesizes nucleotides de novo. Low bio_score is intentional and must
    NOT be raised by an alias addition."""
    form = iqm["rna_dna"]["forms"]["nucleic acid complex"]
    assert form["bio_score"] == 4, (
        f"nucleic acid complex bio_score changed from 4 to {form['bio_score']} — "
        f"alias-add must not modify the conservative bio_score for oral RNA."
    )


def test_rna_dna_no_new_clinical_claims_added(iqm):
    """Negative-scope guard: per dev review v2, alias-add must NOT add any
    new clinical claim. The form's existing 'notes' field must remain
    unchanged (Batch 21 audit text from 2026-04-25). Validate it still
    contains the canonical 'completely degraded' phrasing that justifies
    the conservative score."""
    form = iqm["rna_dna"]["forms"]["nucleic acid complex"]
    notes = form.get("notes", "")
    assert "completely degraded" in notes.lower() or "degraded by pancreatic" in notes.lower(), (
        "rna_dna nucleic acid complex notes lost the pancreatic-degradation "
        "rationale — alias-add must not modify the form notes / clinical "
        "rationale."
    )


# ---------------------------------------------------------------------------
# Commit #4 (Batch 2): cayenne_pepper new IQM parent
# Spec: reports/not_scored_triage/track_BEF_parent_cayenne_pepper_spec.md
# Distinct from existing capsaicin parent. Conservative bio_score=6.
# ---------------------------------------------------------------------------


def test_cayenne_pepper_iqm_parent_exists(iqm):
    assert "cayenne_pepper" in iqm, "cayenne_pepper new IQM parent missing"
    entry = iqm["cayenne_pepper"]
    assert entry.get("standard_name") == "Cayenne Pepper"
    assert entry.get("cui") == "C0006909"


def test_cayenne_pepper_external_ids_inherited_from_botanical_db(iqm):
    """UNII + RxCUI come from already-verified botanical_ingredients.cayenne_pepper."""
    ids = iqm["cayenne_pepper"].get("external_ids", {})
    assert ids.get("unii") == "6M47G7C4SY"
    assert ids.get("rxcui") == "1006340"


@pytest.mark.parametrize(
    "expected_alias",
    [
        "cayenne",
        "cayenne pepper",
        "Capsicum annuum",
        "cayenne fruit",
        "cayenne pepper powder",
        "cayenne pepper fruit powder",
    ],
)
def test_cayenne_pepper_unspecified_form_aliases_include_label_variants(iqm, expected_alias):
    form = iqm["cayenne_pepper"]["forms"]["cayenne pepper (unspecified)"]
    aliases_lower = [a.lower() for a in form.get("aliases", [])]
    assert expected_alias.lower() in aliases_lower, (
        f"alias {expected_alias!r} missing from cayenne_pepper.forms['cayenne pepper (unspecified)'] — "
        f"7 Cayenne products would not match."
    )


def test_cayenne_pepper_bio_score_is_six_not_capsaicin_seven(iqm):
    """Cayenne_pepper bio_score=6 is intentionally ONE BELOW the existing
    capsaicin (unspecified) bio_score=7. Whole-fruit supplementation provides
    ~0.5-5 mg capsaicin per 450-500 mg dose, at the low end of the 2-10 mg/day
    capsaicinoid range. Conservative scoring is the safety floor."""
    form = iqm["cayenne_pepper"]["forms"]["cayenne pepper (unspecified)"]
    assert form["bio_score"] == 6, (
        f"cayenne_pepper bio_score changed from 6 to {form['bio_score']} — "
        f"must remain conservative (one below capsaicin's 7)."
    )
    # cross-check: ensure capsaicin parent is unchanged at 7
    cap = iqm["capsaicin"]["forms"]["capsaicin (unspecified)"]
    assert cap["bio_score"] == 7, (
        f"capsaicin (unspecified) bio_score drifted to {cap['bio_score']}; "
        f"Cayenne batch must not touch the existing capsaicin parent."
    )


@pytest.mark.parametrize(
    "forbidden_alias",
    [
        "chili pepper",
        "hot pepper",
        "jalapeño",
        "habanero",
        "ghost pepper",
        "paprika",
        "bell pepper",
        "tabasco",
        # 'red pepper' — bare term ambiguous across generic Capsicum, paprika,
        # food-form pepper. Removed from cayenne aliases per dev review;
        # must NOT be re-added without explicit cayenne-context gating.
        "red pepper",
    ],
)
def test_cayenne_pepper_aliases_do_not_include_generic_chili_pepper_terms(iqm, forbidden_alias):
    """Per dev review + research subagent finding: 'chili pepper' is a class
    name spanning 5 Capsicum species with different capsaicinoid densities.
    Paprika is C. annuum but 30-500× milder than cayenne. These terms must
    NOT be aliases on cayenne_pepper or any of its forms."""
    entry = iqm["cayenne_pepper"]
    top_aliases_lower = [a.lower() for a in entry.get("aliases", [])]
    assert forbidden_alias.lower() not in top_aliases_lower
    for fname, fdata in entry.get("forms", {}).items():
        form_aliases_lower = [a.lower() for a in fdata.get("aliases", [])]
        assert forbidden_alias.lower() not in form_aliases_lower, (
            f"forbidden alias {forbidden_alias!r} found in cayenne_pepper.{fname}.aliases — "
            f"would false-match other Capsicum species with different capsaicinoid profiles."
        )


def test_cayenne_pepper_notes_include_required_safety_and_evidence_markers(iqm):
    """Per spec: notes must reference (a) FDA GRAS 182.10 as identity/safety
    context, (b) NIH ODS Weight Loss factsheet GI distress claim, (c) explicit
    'antiplatelet ... THEORETICAL' framing for warfarin/aspirin interaction
    (NOT documented), (d) explicit 'NCCIH does NOT' statement to prevent
    future drift back to false NCCIH citation."""
    form = iqm["cayenne_pepper"]["forms"]["cayenne pepper (unspecified)"]
    notes = form.get("notes", "").lower()
    assert "182.10" in notes, "FDA GRAS 21 CFR 182.10 reference missing from notes"
    assert "weight loss" in notes or "nih ods" in notes, "NIH ODS WeightLoss factsheet attribution missing"
    assert "theoretical" in notes and "antiplatelet" in notes, (
        "Antiplatelet interaction must be explicitly framed as THEORETICAL "
        "(per Tan 2021 BJCP review). Not documented clinically."
    )
    assert "nccih does not" in notes, (
        "Notes must explicitly state NCCIH does NOT maintain a cayenne-specific "
        "oral-supplement monograph (only chronic-pain digest, topical context). "
        "Prevents future drift back to false NCCIH citation."
    )


def test_cayenne_pepper_match_rules_exclusions_block_other_capsicum_species(iqm):
    exclusions = iqm["cayenne_pepper"].get("match_rules", {}).get("exclusions", [])
    exclusions_lower = [e.lower() for e in exclusions]
    for required in ["chili pepper", "jalapeño", "habanero", "paprika", "red pepper"]:
        assert required in exclusions_lower, (
            f"match_rules.exclusions must include {required!r} — "
            f"belt-and-suspenders against false-matching other Capsicum species "
            f"or generic-pepper food-form terms."
        )


# ---------------------------------------------------------------------------
# Commit #5 (Batch 2): bee_pollen new IQM parent
# Spec: reports/not_scored_triage/track_BEF_parent_bee_pollen_spec.md
# Conservative bio_score=5 — umbrella review PMID 31435975 explicitly concluded
# "Evidence regarding bee pollen is too limited to draw any conclusion on its
# clinical efficacy." Critical safety: NCCIH-documented pollen-allergy /
# anaphylaxis risk (case_report PMC4509665); single warfarin case (PMID 21098375).
# ---------------------------------------------------------------------------


def test_bee_pollen_iqm_parent_exists(iqm):
    assert "bee_pollen" in iqm
    entry = iqm["bee_pollen"]
    assert entry.get("standard_name") == "Bee Pollen"
    assert entry.get("cui") == "C0795585"


def test_bee_pollen_external_ids_inherited_from_botanical_db(iqm):
    ids = iqm["bee_pollen"].get("external_ids", {})
    assert ids.get("unii") == "3729L8MA2C"
    assert ids.get("rxcui") == "253157"


@pytest.mark.parametrize(
    "expected_alias",
    ["bee pollen", "bee pollen extract", "bee pollen granules", "pollen granules"],
)
def test_bee_pollen_unspecified_form_aliases_include_label_variants(iqm, expected_alias):
    form = iqm["bee_pollen"]["forms"]["bee pollen (unspecified)"]
    aliases_lower = [a.lower() for a in form.get("aliases", [])]
    assert expected_alias.lower() in aliases_lower


def test_bee_pollen_bio_score_is_five(iqm):
    """Bio_score=5 per PMID 31435975 umbrella-review conclusion: 'Evidence
    regarding bee pollen is too limited to draw any conclusion on its
    clinical efficacy.' Lower than cayenne (6, documented mechanism)
    because bee pollen has no comparable single-compound mechanism."""
    form = iqm["bee_pollen"]["forms"]["bee pollen (unspecified)"]
    assert form["bio_score"] == 5


@pytest.mark.parametrize(
    "forbidden_alias",
    ["propolis", "royal jelly", "honey", "beeswax", "bee venom"],
)
def test_bee_pollen_aliases_do_not_include_other_bee_products(iqm, forbidden_alias):
    """Propolis (hive resin), royal jelly (worker-bee gland secretion), honey
    (nectar sweetener), beeswax (structural wax) are distinct bee products
    with different chemistries and uses. Must NOT match bee_pollen parent."""
    entry = iqm["bee_pollen"]
    top_aliases_lower = [a.lower() for a in entry.get("aliases", [])]
    assert forbidden_alias.lower() not in top_aliases_lower
    for fname, fdata in entry.get("forms", {}).items():
        assert forbidden_alias.lower() not in [
            a.lower() for a in fdata.get("aliases", [])
        ]


def test_bee_pollen_notes_include_required_evidence_and_safety_markers(iqm):
    """Notes MUST include the verified source-quality-tagged claims:
    - PMID 31435975 'evidence too limited' as primary score-rationale anchor
    - NCCIH allergy URL (authoritative_public_health, NOT primary_regulatory)
    - Warfarin framed as SINGLE case-report signal (PMID 21098375), not
      established broad interaction
    - Pregnancy explicitly flagged tertiary_not_used_for_scoring (no
      authoritative monograph)
    """
    form = iqm["bee_pollen"]["forms"]["bee pollen (unspecified)"]
    notes = form.get("notes", "")
    notes_lower = notes.lower()
    assert "31435975" in notes, "Umbrella-review primary efficacy anchor missing"
    assert "too limited" in notes_lower, "PMID 31435975 verbatim 'too limited' quote missing"
    assert "nccih.nih.gov" in notes_lower or "seasonal-allergies" in notes_lower, (
        "NCCIH Seasonal Allergies URL missing"
    )
    assert "authoritative_public_health" in notes, (
        "NCCIH allergy citation must be tagged authoritative_public_health, "
        "not primary_regulatory (per dev review)."
    )
    assert "21098375" in notes, "PMID 21098375 warfarin single-case-report citation missing"
    assert "single" in notes_lower and "case report" in notes_lower, (
        "Warfarin claim must be framed as SINGLE case report, not established interaction."
    )
    assert "tertiary_not_used_for_scoring" in notes, (
        "Pregnancy claim must be tagged tertiary_not_used_for_scoring (no "
        "authoritative monograph)."
    )


# ---------------------------------------------------------------------------
# Commit #6 (Batch 2): english_ivy new IQM parent
# Spec: reports/not_scored_triage/track_BEF_parent_english_ivy_spec.md
# Strongest evidence anchor in Batch 2: EMA HMPC Rev. 2 well-established use.
# Two forms: unspecified (bio_score=8) + standardized hederacoside-C marker (10).
# CRITICAL double-score guard: Hederacoside C must NOT be aliased as a separate
# scorable active.
# ---------------------------------------------------------------------------


def test_english_ivy_iqm_parent_exists(iqm):
    assert "english_ivy" in iqm
    entry = iqm["english_ivy"]
    assert entry.get("standard_name") == "English Ivy"
    assert entry.get("cui") == "C0949841"


def test_english_ivy_external_ids_include_verified_unii(iqm):
    """FDA UNII ZP9XFG71A7 verified via precision.fda.gov ('HEDERA HELIX TOP').
    Was missing from botanical_ingredients; added here per subagent finding."""
    ids = iqm["english_ivy"].get("external_ids", {})
    assert ids.get("unii") == "ZP9XFG71A7"


@pytest.mark.parametrize(
    "expected_alias",
    [
        "english ivy",
        "english ivy leaf extract",
        "ivy leaf extract",
        "Hedera helix",
        "hedera helix leaf extract",
    ],
)
def test_english_ivy_unspecified_form_aliases_include_label_variants(iqm, expected_alias):
    form = iqm["english_ivy"]["forms"]["english ivy leaf extract (unspecified)"]
    aliases_lower = [a.lower() for a in form.get("aliases", [])]
    assert expected_alias.lower() in aliases_lower


def test_english_ivy_unspecified_bio_score_is_eight(iqm):
    form = iqm["english_ivy"]["forms"]["english ivy leaf extract (unspecified)"]
    assert form["bio_score"] == 8


def test_english_ivy_standardized_form_exists_and_bio_score_is_ten(iqm):
    forms = iqm["english_ivy"].get("forms", {})
    assert "english ivy standardized (hederacoside C marker)" in forms
    form = forms["english ivy standardized (hederacoside C marker)"]
    assert form["bio_score"] == 10


def test_english_ivy_DOUBLE_SCORE_GUARD_no_bare_hederacoside_c_alias(iqm):
    """CRITICAL per dev review: Hederacoside C must NOT be a standalone alias
    on any form. It is the standardization MARKER for the parent ivy extract,
    not a separately-scorable active. Adding it as an alias would cause
    products like Natures_Way 327886 Bronchial Soothe (which declares both
    English Ivy Leaf Extract 86mg AND Hederacoside C 9.4mg) to be DOUBLE-SCORED.

    The enricher-side fix (route hederacoside C row as standardization marker
    and promote parent ivy row to the standardized form) is a separate
    deferred slice. Until that ships, the safe interim is: hederacoside C
    row stays unmatched (NOT_SCORED) so it doesn't add a second score.
    """
    entry = iqm["english_ivy"]
    forbidden = ["hederacoside c", "hederacoside C", "Hederacoside C", "hederacoside-c"]
    for fname, fdata in entry.get("forms", {}).items():
        aliases_lower = [a.lower() for a in fdata.get("aliases", [])]
        for bad in forbidden:
            assert bad.lower() not in aliases_lower, (
                f"DOUBLE-SCORE GUARD VIOLATED: '{bad}' found in "
                f"english_ivy.{fname}.aliases. Hederacoside C must remain a "
                f"standardization marker only, not a separately-scored active. "
                f"See spec § 'Double-score guard'."
            )


@pytest.mark.parametrize(
    "forbidden_alias",
    [
        "ground ivy",
        "Glechoma hederacea",
        "poison ivy",
        "Toxicodendron",
        "boston ivy",
        "Parthenocissus",
        "Hedera hibernica",
    ],
)
def test_english_ivy_does_not_match_lookalike_species(iqm, forbidden_alias):
    """Hedera helix is botanically distinct from common look-alikes:
    Ground Ivy (Glechoma, Lamiaceae), Poison Ivy (Toxicodendron,
    Anacardiaceae), Boston Ivy (Parthenocissus, Vitaceae), Hedera hibernica
    (close relative, same genus). Verified via Kew + Missouri Botanical
    Garden + BSBI per subagent research."""
    entry = iqm["english_ivy"]
    top_lower = [a.lower() for a in entry.get("aliases", [])]
    assert forbidden_alias.lower() not in top_lower
    for fname, fdata in entry.get("forms", {}).items():
        assert forbidden_alias.lower() not in [
            a.lower() for a in fdata.get("aliases", [])
        ]


def test_english_ivy_unspecified_notes_include_HMPC_and_minimal_caveat(iqm):
    """Notes MUST include the primary anchor (EMA HMPC Rev. 2 well-established
    use) AND the important caveat from Holzinger 2021 PMID 33523253 'effects
    minimal at best and of uncertain clinical importance'. Both required to
    keep the IQM honest about the evidence ceiling."""
    form = iqm["english_ivy"]["forms"]["english ivy leaf extract (unspecified)"]
    notes = form.get("notes", "")
    notes_lower = notes.lower()
    assert "hmpc" in notes_lower or "hmpc/289430" in notes_lower, (
        "EMA HMPC monograph reference missing from notes."
    )
    assert "well-established" in notes_lower, (
        "HMPC 'well-established use' qualifier missing — required by spec."
    )
    assert "33523253" in notes or "minimal at best" in notes_lower, (
        "Holzinger 2021 PMID 33523253 'effects minimal at best' caveat missing — "
        "required to qualify the regulatory anchor."
    )
    assert "primary_regulatory" in notes, (
        "EMA HMPC must be tagged primary_regulatory."
    )


# ---------------------------------------------------------------------------
# Commit #7 (Batch 2): diamine_oxidase HDU-specific alias add (EXISTING parent)
# Spec: reports/not_scored_triage/track_BEF_parent_diamine_oxidase_spec.md
# Narrow scope: add unambiguous HDU-dose aliases only. Do NOT add generic
# "Porcine Kidney Extract" / "Kidney Tissue" (would false-match glandular
# products). Expected immediate product delta: 0. Pure Encapsulations DSLD
# 317962 deferred to cleaner-side context-routing slice.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_hdu_alias",
    ["DAO 10000 HDU", "DAO 10,000 HDU", "10000 HDU DAO"],
)
def test_diamine_oxidase_includes_HDU_specific_aliases(iqm, expected_hdu_alias):
    """HDU (Histamine Degrading Units) is the standard activity unit for DAO
    supplements (10,000 HDU is the conventional adult dose). HDU-tagged
    aliases are unambiguous DAO-product identifiers."""
    form = iqm["diamine_oxidase"]["forms"]["diamine oxidase (unspecified)"]
    aliases_lower = [a.lower() for a in form.get("aliases", [])]
    assert expected_hdu_alias.lower() in aliases_lower


@pytest.mark.parametrize(
    "forbidden_generic",
    [
        "porcine kidney extract",
        "porcine kidney",
        "kidney extract",
        "kidney tissue",
        "kidney glandular",
        "porcine kidney glandular",
    ],
)
def test_diamine_oxidase_does_NOT_include_generic_kidney_aliases(iqm, forbidden_generic):
    """CRITICAL: must NEVER include generic porcine-kidney aliases. Those
    would false-match generic kidney glandular products (sold for
    adrenal/urinary support without DAO activity) like Natures_Way 333753
    Kidney Bladder Blend. Per dev review: 'do not map to generic
    organ_extracts. Existing diamine_oxidase is the right parent for DAO
    Enzyme context.' Generic kidney = different product class."""
    entry = iqm["diamine_oxidase"]
    top_lower = [a.lower() for a in entry.get("aliases", [])]
    assert forbidden_generic.lower() not in top_lower
    for fname, fdata in entry.get("forms", {}).items():
        assert forbidden_generic.lower() not in [
            a.lower() for a in fdata.get("aliases", [])
        ], (
            f"FORBIDDEN GENERIC ALIAS: {forbidden_generic!r} found in "
            f"diamine_oxidase.{fname}.aliases — would false-match generic "
            f"kidney glandular products. See spec § 'What this slice does NOT do'."
        )


def test_diamine_oxidase_bio_score_preserved(iqm):
    """Existing entry bio_score must not change — this is alias-only."""
    form = iqm["diamine_oxidase"]["forms"]["diamine oxidase (unspecified)"]
    assert form["bio_score"] == 5


# ---------------------------------------------------------------------------
# Batch 3 commit A: horse_chestnut_seed new IQM parent
# Distinct from existing `aescin` parent (which scores isolated compound).
# PRIMARY anchor: EMA HMPC Rev. 1 (23/04/2020) well-established use for CVI +
# Cochrane PMID 23152216 (Pittler & Ernst 2012) + NCCIH endorsement.
# CRITICAL safety: raw seed is toxic (esculin/aesculin); standardized extracts
# must be esculin-removed.
# ---------------------------------------------------------------------------


def test_horse_chestnut_seed_iqm_parent_exists(iqm):
    assert "horse_chestnut_seed" in iqm
    entry = iqm["horse_chestnut_seed"]
    assert entry.get("standard_name") == "Horse Chestnut Seed"
    assert entry.get("cui") == "C0001443"


def test_horse_chestnut_seed_external_ids_inherited_from_botanical_db(iqm):
    ids = iqm["horse_chestnut_seed"].get("external_ids", {})
    assert ids.get("unii") == "3C18L6RJAZ"
    assert ids.get("rxcui") == "260020"


def test_horse_chestnut_seed_distinct_from_aescin_parent(iqm):
    """Distinct parent — different identity (whole-seed extract vs isolated
    compound). aescin parent (CUI C0014838, bio_score=5) is NOT touched."""
    assert "horse_chestnut_seed" in iqm
    assert "aescin" in iqm
    assert iqm["horse_chestnut_seed"].get("cui") == "C0001443"
    assert iqm["aescin"].get("cui") == "C0014838"
    assert iqm["aescin"]["forms"]["aescin (unspecified)"]["bio_score"] == 5


def test_horse_chestnut_seed_two_forms_unspecified_and_standardized(iqm):
    forms = iqm["horse_chestnut_seed"].get("forms", {})
    assert "horse chestnut seed (unspecified)" in forms
    assert "horse chestnut standardized (aescin marker)" in forms


def test_horse_chestnut_seed_unspecified_bio_score_is_eight(iqm):
    form = iqm["horse_chestnut_seed"]["forms"]["horse chestnut seed (unspecified)"]
    assert form["bio_score"] == 8


def test_horse_chestnut_seed_standardized_bio_score_is_ten(iqm):
    """Standardized aescin form bio_score=10 — matches the form clinical
    RCTs actually study (16-28% aescin per superseded HMPC; 100 mg aescin
    daily dose per current monograph)."""
    form = iqm["horse_chestnut_seed"]["forms"]["horse chestnut standardized (aescin marker)"]
    assert form["bio_score"] == 10


@pytest.mark.parametrize(
    "expected_alias",
    [
        "horse chestnut",
        "horse chestnut seed",
        "horse chestnut seed extract",
        "Aesculus hippocastanum",
        "standardized Horse Chestnut extract",
    ],
)
def test_horse_chestnut_seed_aliases_include_label_variants(iqm, expected_alias):
    """Aliases distributed across forms — assert each is present in AT LEAST
    one form's alias list."""
    entry = iqm["horse_chestnut_seed"]
    found = False
    for fname, fdata in entry.get("forms", {}).items():
        aliases_lower = [a.lower() for a in fdata.get("aliases", [])]
        if expected_alias.lower() in aliases_lower:
            found = True
            break
    assert found, (
        f"alias {expected_alias!r} missing from any horse_chestnut_seed form — "
        f"Solgar 216723 Horse Chestnut Seed Extract 250mg would stay NOT_SCORED."
    )


@pytest.mark.parametrize(
    "forbidden_alias",
    [
        "sweet chestnut",
        "spanish chestnut",
        "castanea",
        "Castanea sativa",
        "water chestnut",
        "Eleocharis dulcis",
        "buckeye",
        # Note: bare "chestnut" exclusion REMOVED. The matcher uses
        # substring-style exclusion checking, so a bare "chestnut" entry
        # would also reject ALL "horse chestnut" aliases (they contain
        # the substring "chestnut"). The explicit "sweet chestnut" /
        # "water chestnut" / etc. entries above are sufficient guard
        # against the actual lookalike species. Verified runtime:
        # _match_quality_map("chestnut") → None (matches no parent).
    ],
)
def test_horse_chestnut_seed_excludes_unrelated_chestnut_species(iqm, forbidden_alias):
    """Distinct from edible sweet chestnut (Castanea sativa, Fagaceae),
    water chestnut (Eleocharis dulcis, Cyperaceae), and California buckeye
    (Aesculus californica, same genus distinct species). Per subagent
    verification with Wikipedia + Native Plant Trust + Missouri Botanical
    Garden."""
    entry = iqm["horse_chestnut_seed"]
    top_lower = [a.lower() for a in entry.get("aliases", [])]
    assert forbidden_alias.lower() not in top_lower
    for fname, fdata in entry.get("forms", {}).items():
        aliases_lower = [a.lower() for a in fdata.get("aliases", [])]
        assert forbidden_alias.lower() not in aliases_lower, (
            f"forbidden alias {forbidden_alias!r} in horse_chestnut_seed.{fname} — "
            f"would false-match unrelated chestnut species."
        )


def test_horse_chestnut_seed_notes_include_verified_evidence_and_safety_markers(iqm):
    """Notes must include:
    - PMID 23152216 (CORRECTED Cochrane — NOT ghost PMID 22592684)
    - EMA HMPC reference
    - Raw-seed esculin/aesculin toxicity warning (standardized-extract caveat)
    - Warfarin/anticoagulant interaction (documented per MSKCC, not theoretical)
    - source-quality tags per dev review
    """
    form = iqm["horse_chestnut_seed"]["forms"]["horse chestnut seed (unspecified)"]
    notes = form.get("notes", "")
    notes_lower = notes.lower()
    assert "23152216" in notes, "Verified Cochrane PMID 23152216 missing"
    assert "22592684" not in notes, "GHOST PMID 22592684 must NEVER appear"
    assert "hmpc" in notes_lower, "EMA HMPC reference missing"
    assert "esculin" in notes_lower or "aesculin" in notes_lower, (
        "Raw-seed esculin/aesculin toxicity warning required — standardized "
        "extracts must have the toxic coumarin glycoside removed."
    )
    assert "warfarin" in notes_lower or "anticoagulant" in notes_lower or "bleeding" in notes_lower, (
        "Documented warfarin/anticoagulant interaction warning required (MSKCC)."
    )
    assert "primary_regulatory" in notes, (
        "EMA HMPC must be tagged primary_regulatory."
    )
    assert "authoritative_public_health" in notes, (
        "NCCIH must be tagged authoritative_public_health (not primary_regulatory)."
    )
