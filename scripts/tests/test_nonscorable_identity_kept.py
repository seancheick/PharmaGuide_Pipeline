"""A row the enricher will not score keeps the identity the label names, for interactions only.

Non-scorability is a row role, not evidence against the substance. The
enricher re-validated the cleaner's identity on non-scorable rows only by an
exact literal, structured or taxonomy match, so a row the cleaner identified
through its descriptor preprocessing ("Lactobacillus", "Yerba Mate leaf
extract") lost its identity, and with it every interaction rule (951a05415
capture: 90 rows).

Identity is not scorability: such a row meets its interaction rules but owns
no Evidence, feeds no Dose and routes nothing; scoring reads it as before.
The cleaner's standardName is the id it mapped, so it proves nothing a
declared form contradicts: a genus listing several species ("Bifidobacterium"),
a plant read through its marker form ("Sawasabi Wasabi powder" as
isothiocyanates) or an amino acid declared as a protein source ("Arginine" as
whey protein isolate) is not kept. A blend header keeps its identity on the same terms.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from identity_integrity import build_canonical_identity_registry, resolve_identity  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enrich():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def run(dsld_id: int) -> dict:
        if dsld_id not in cache:
            raw = json.loads((FIXTURES / f"nonscorable_identity_{dsld_id}_raw.json").read_text())
            cache[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return cache[dsld_id]

    return run


@pytest.mark.parametrize(
    "dsld_id,label,canonical_id,rule_id",
    [
        # Perfect Food Green Superfood: "Lactobacillus" in a probiotic blend.
        (233668, "Lactobacillus", "probiotics", "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED"),
        # Amplified Muscle Igniter 4X: "Yerba Mate leaf extract" in an energy blend.
        (18473, "Yerba Mate leaf extract", "yerba_mate_leaf", "RULE_IQM_YERBA_MATE_CARDIOVASCULAR"),
        # Staminol: the row declares L-Arginine itself inside a proprietary blend.
        (315814, "Arginine", "l_arginine", "RULE_IQM_L_ARGININE_HYPERTENSION"),
    ],
)
def test_non_scorable_row_keeps_its_identity_and_meets_its_rules(enrich, dsld_id, label, canonical_id, rule_id):
    enriched = enrich(dsld_id)
    iqd = enriched["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] + iqd["ingredients_skipped"] if r.get("raw_source_text") == label]
    assert rows and {r["canonical_id"] for r in rows} == {canonical_id}
    assert all(r["identity_disposition"] == "taxonomy_only" and r["scoreable_identity"] is False for r in rows)
    alerts = [a for a in enriched["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == rule_id]
    assert label in {a["ingredient_name"] for a in alerts}


@pytest.mark.parametrize("dsld_id,label,canonical_id,rule_id", [
    # Ravage: the weight-only "Caffeine Blend" header is caffeine.
    (1179, "Caffeine Blend", "caffeine", "RULE_INGREDIENT_CAFFEINE"),
    # Its members (Anhydrous Caffeine, Piperine Beadlets) do not contradict the name.
    (28981, "Caffeine Blend", "caffeine", "RULE_INGREDIENT_CAFFEINE"),
    # Flex-A-Min: "Chondroitin Sulfate Complex" lists chondroitin among seven others.
    (17471, "Chondroitin Sulfate Complex", "chondroitin", "RULE_IQM_CHONDROITIN"),
])
def test_blend_header_keeps_its_identity_and_meets_its_rules(enrich, dsld_id, label, canonical_id, rule_id):
    enriched = enrich(dsld_id)
    rows = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("raw_source_text") == label]
    assert rows and {r["canonical_id"] for r in rows} == {canonical_id}
    assert any(a["rule_id"] == rule_id for a in enriched["interaction_profile"]["ingredient_alerts"])


@pytest.mark.parametrize("dsld_id,pillar,expected", [
    # LIT AF: a 300 mg "Caffeine Blend" header over 250 mg + 50 mg caffeine rows. The
    # header's identity must not add a second 300 mg to the caffeine ceiling.
    (219842, "dose", 13.0),
    # Echinacea Complex: the header identity must not replace the blend's lent
    # echinacea anchor. The reviewed general Dose conclusion is neutral;
    # no member quantity or applicable clinical regimen is invented.
    (73300, "dose", 11.4),
    # Joint Health: a header whose printed name is itself an alias (Univestin)
    # retains its identity; general Dose neutrality does not finish the
    # independently unresolved UP446 Evidence review.
    (243676, "dose", 11.4),
])
def test_header_identity_does_not_enter_scoring(enrich, dsld_id, pillar, expected):
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(enrich(dsld_id))
    assert scored["quality_pillars_v4"][pillar]["score"] == expected
    if dsld_id in {73300, 243676}:
        dose = scored["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]
        botanical = [row for row in dose["dose_contributions"] if row["assessment"] == "botanical_profile"]
        assert botanical and all(row["credit_raw"] > 0 for row in botanical)
        assert all(row["assessment"] == "botanical_profile" for row in botanical)
        assert scored["quality_assessment_status"] == "partial"
        assert scored["assessment_readiness"]["release_assessment"]["is_complete"] is False


def test_identified_food_blend_member_does_not_route_a_vitamin_product(enrich):
    """327570 Methyl B12: the restored "Beet" inside a 242 mg Food Blend borrows the
    blend's mass; it cannot make the B12/B6/folate product botanical-owned."""
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = enrich(327570)
    iqd = enriched["ingredient_quality_data"]
    assert {r["canonical_id"] for r in iqd["ingredients"] if r.get("raw_source_text") == "Beet"} == {"beetroot"}
    dims = build_scored_artifact(enriched)["_v4_module_breakdown"]["dimensions"]
    assert dims["formulation"]["metadata"]["formulation_profile"] == "generic_iqm"
    assert dims["dose"]["metadata"]["method"] != "botanical_clinical_dose_v1"


_REGISTRY = {
    "ingredient_quality_map": {
        "caffeine": {"standard_name": "Caffeine", "aliases": []},
        "guarana": {"standard_name": "Guarana", "aliases": []},
    },
    "proprietary_blends": {"proprietary_blend_concerns": [
        {"id": "BLEND_SUPERFOOD", "standard_name": "Superfood Blend", "blend_terms": []},
    ]},
}


def _decide(label: str, supplied: str, standard_name: str, **row):
    return resolve_identity(
        row={"raw_source_text": label, "standardName": standard_name, **row},
        supplied_canonical_id=supplied,
        resolve_candidate=lambda value: "guarana" if "guarana" in value.casefold() else None,
        allow_unscoreable_taxonomy_only=True,
        canonical_registry=build_canonical_identity_registry(_REGISTRY),
    )


def test_uncontradicted_supplied_identity_is_kept_unscored():
    decision = _decide("Caffeine Blend", "caffeine", "Caffeine")
    assert (decision.disposition, decision.canonical_id, decision.scoreable_identity) == (
        "taxonomy_only", "caffeine", False,
    )


def test_label_naming_another_substance_still_wins():
    assert _decide("Guarana seed extract", "caffeine", "Caffeine").canonical_id is None


def test_stale_id_the_row_never_named_is_not_kept():
    """The cleaner's standardName for "Antimony" is not caffeine."""
    assert _decide("Antimony", "caffeine", "Antimony").canonical_id is None


def test_blend_header_row_is_kept_unscored():
    decision = _decide("Caffeine Blend", "caffeine", "Caffeine", cleaner_row_role="blend_header_total")
    assert (decision.canonical_id, decision.scoreable_identity) == ("caffeine", False)


def test_blend_header_its_printed_name_does_not_name_is_not_kept():
    """The cleaner's standardName alone never names a header: "Adrenal Blend" is not caffeine."""
    assert _decide("Adrenal Blend", "caffeine", "Caffeine", cleaner_row_role="blend_header_total").canonical_id is None


@pytest.mark.parametrize("dsld_id,label", [
    # Schisandra, rhodiola, ashwagandha, eleuthero: an adrenal-support formula, not adrenal tissue.
    (204571, "Organic Adrenal Blend"),
    (274389, "Organic Adrenal Blend"),
    # Saw palmetto, beta-sitosterol, pumpkin seed, lycopene: not prostate tissue.
    (33607, "Prostate Formula"),
    # Members caseinate, whey, egg albumin, milk protein: those proteins' amino profile.
    (228823, "Glutamic Acid"),
])
def test_blend_header_whose_members_name_other_substances_is_not_kept(enrich, dsld_id, label):
    iqd = enrich(dsld_id)["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] + iqd["ingredients_skipped"]
            if r.get("raw_source_text") == label and r.get("cleaner_row_role") == "blend_header_total"]
    assert rows and {r["canonical_id"] for r in rows} == {None}


def test_role_record_is_not_kept_as_a_substance():
    assert _decide("Raw Certified Organic Superfood Blend", "BLEND_SUPERFOOD", "Superfood Blend").canonical_id is None


@pytest.mark.parametrize("dsld_id,label,wrong_id", [
    # Forms B. bifidum BB-2 and B. animalis lactis: a genus, not B. lactis alone.
    (288699, "Bifidobacterium", "bifidobacterium_lactis"),
    # Forms name whey protein isolate: an amino-profile constituent, not supplemental arginine.
    (176044, "Arginine", "l_arginine"),
    # Listed inside "Solae Soy Protein isolate": the protein's amino profile.
    (79397, "Arginine", "l_arginine"),
    # DSLD group "Agave" names the genus only; century_plant is Agave americana.
    (31062, "Agave powder", "century_plant"),
    # The marker form "Total Isothiocyanate" is not the plant.
    (59766, "Sawasabi Wasabi powder", "isothiocyanates"),
    # Arginine in Amino Acids in Cilantro: a food's composition, three levels deep.
    (80495, "Arginine", "l_arginine"),
    # Form Polydatin, resveratrol's glucoside: a marker form is not the row's identity.
    (277367, "Glycosides", "resveratrol"),
])
def test_contradicted_identity_is_not_kept(enrich, dsld_id, label, wrong_id):
    iqd = enrich(dsld_id)["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] + iqd["ingredients_skipped"] if r.get("raw_source_text") == label]
    assert rows and wrong_id not in {r["canonical_id"] for r in rows}


def test_wasabi_label_keeps_its_plant(enrich):
    iqd = enrich(59766)["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] if r.get("raw_source_text") == "Sawasabi Wasabi powder"]
    assert rows and {r["canonical_id"] for r in rows} == {"wasabi_root"}


@pytest.mark.parametrize("dsld_id,pillar,expected", [
    # Lactobacillus row kept for interactions; probiotic Evidence as on main.
    (274777, "evidence", 0.0),
    # Gamma-Carotene -> vitamin_a is a cleaner identity, not vitamin A evidence.
    (297685, "evidence", 16.7),
    # Restored Apple/coffeeberry flavor rows do not become title Evidence owners.
    # Source-qualified cranberry hold removes unsupported Evidence; kept flavor rows stay excluded.
    (40089, "evidence", 11.1),
    # "Raw organic Svetol" (green coffee) does not own Evidence through "Fit Coffee".
    (204521, "evidence", 10.0),
    # A 0.4 mg iron row kept for interactions feeds no Dose.
    # 11.4 on main, where "Natural Berry Flavor" made acai the declared purpose; 1.1 is
    # what main gives the same label titled "Raw Superfoods".
    (178728, "dose", 1.1),
    # "organic Beet" re-identified later as Beetroot Powder (as on main) still scores.
    # 10.8 on main; 12.4 since PR214, whose multi panel no longer averages adjunct rows.
    (62890, "formulation", 12.4),
])
def test_interaction_only_identity_owns_no_evidence_or_dose(enrich, dsld_id, pillar, expected):
    from scoring_v4.scored_artifact import build_scored_artifact

    assert build_scored_artifact(enrich(dsld_id))["quality_pillars_v4"][pillar]["score"] == expected


def test_member_forms_keep_the_family_identity():
    registry = build_canonical_identity_registry({"ingredient_quality_map": {
        "probiotics": {"standard_name": "Probiotics", "aliases": []},
        "lactobacillus_acidophilus": {"standard_name": "Lactobacillus Acidophilus", "aliases": []},
        "whey_protein": {"standard_name": "Whey Protein", "aliases": ["whey protein isolate"]},
        "l_arginine": {"standard_name": "L-Arginine", "aliases": []},
    }})

    def decide(label, supplied, standard_name, forms):
        return resolve_identity(
            row={"raw_source_text": label, "standardName": standard_name,
                 "forms": [{"name": form} for form in forms]},
            supplied_canonical_id=supplied,
            resolve_candidate=lambda value: None,
            allow_unscoreable_taxonomy_only=True,
            canonical_registry=registry,
            canonical_parent_of=lambda parent, child: (parent, child) == ("probiotics", "lactobacillus_acidophilus"),
        )

    assert decide("Lactobacillus", "probiotics", "Probiotics", ["Lactobacillus Acidophilus"]).canonical_id == "probiotics"
    assert decide("Arginine", "l_arginine", "L-Arginine", ["Whey Protein Isolate"]).canonical_id is None


def _scoring_inputs(artifact):
    breakdown = artifact["_v4_module_breakdown"]
    dims = breakdown["dimensions"]
    return {
        "score": artifact["quality_score_v4_100"],
        "status": artifact["quality_assessment_status"],
        "evidence_owners": dims["evidence"]["metadata"].get("evidence_owner_canonicals"),
        "dose_credits": sorted(
            round(c.get("credit_raw") or 0, 2) for c in dims["dose"]["metadata"].get("dose_contributions") or []
        ),
    }


@pytest.mark.parametrize("dsld_id,expected", [
    # The Coptis owner stays; its reviewed general Dose adds11.4 without clinical credit.
    (252567, {"score": 57.1, "status": "partial", "evidence_owners": ["coptis_rhizome"], "dose_credits": [11.97]}),
    # 50.6 before 2026-10-28: Dr. Pham's GABA ruling (very limited stress
    # evidence, no points until the calibration batch) makes INGR_GABA
    # reference-only. Owners and Dose are unchanged; only Evidence moves.
    (315814, {"score": 43.3, "status": "partial", "evidence_owners": ["gaba", "maca", "oat_straw", "yohimbe"],
              "dose_credits": [12.54]}),
    # A kept coffeeberry row is invisible to scoring, never re-matched as coffee.
    # Since "Fruit" no longer names Apple (title owner), vitamin C is a major owner and
    # the vitamins are the Dose panel (60.7 and [12.54] on main).
    # Grape remains unfinished; cranberry qualification hold lowers Evidence without changing roles or Dose.
    (40089, {"score": 63.9, "status": "partial",
             "evidence_owners": ["bilberry", "blackberry", "blueberry", "carrot", "cranberry", "grape", "plum",
                                 "pomegranate", "spinach", "strawberry", "tart_cherry", "tomato", "vitamin_c"],
             "dose_credits": [12.83, 15.12, 17.46]}),
    (327402, {"score": 72.8, "status": "partial", "evidence_owners": None, "dose_credits": [1.28, 6.19]}),
    # 83.8 on main; 83.9 since PR214 (multi panel form quality reads material rows only).
    (328104, {"score": 83.9, "status": "partial", "evidence_owners": None, "dose_credits": [4.65, 13.17]}),
])
def test_scoring_inputs_equal_main_when_a_row_keeps_an_identity(enrich, dsld_id, expected):
    """Source-bound values: retain main controls; reviewed Coptis Dose adds neutral only."""
    from scoring_v4.scored_artifact import build_scored_artifact

    product = enrich(dsld_id)
    artifact = build_scored_artifact(product)
    assert _scoring_inputs(artifact) == expected
    if dsld_id in {327402, 328104}:
        assert artifact["assessment_readiness"]["release_assessment"]["is_complete"] is False
    if dsld_id == 40089:
        from evidence_resolver import resolve_product_evidence
        resolution = resolve_product_evidence(product, owner_scoped=True)
        pending = [(row.canonical_id, row.blocking_reasons) for row in resolution.resolutions
                   if row.disposition == "literature_resolution_required"]
        assert pending == [("grape", ["literature_verification_pending"])]
        data = json.loads((SCRIPTS / "data" / "literature_evidence_records.json").read_text())
        source = next(row for row in data["literature_evidence_records"] if row["canonical_id"] == "grape")
        assert source["qualifying_human_studies"] == []
        assert source["verification_provenance"]["verified_by"] == "scripts/api_audit/verify_literature_records.py"


def test_recognition_clears_the_interaction_only_marker(enrich):
    from identity_integrity import NON_SCORING_IDENTITY_RATIONALE

    rows = [r for r in enrich(252567)["ingredient_quality_data"]["ingredients"]
            if r.get("raw_source_text") == "Coptis chinensis extract"]
    assert rows and {r["canonical_id"] for r in rows} == {"coptis_rhizome"}
    assert all(r["identity_resolution_rationale"] != NON_SCORING_IDENTITY_RATIONALE for r in rows)



@pytest.mark.parametrize("dsld_id,label,canonical_id", [
    # BCM-95 "Total Curcuminoids complex (with Essential Oils)" inside "BCM-95 Bio-Curcumin
    # Turmeric 25:1 extract": BCM-95 is curcumin with turmeric essential oils (PMID 25994138).
    (210718, "Total Curcuminoids complex", "curcumin"),
    # Control: a turmeric header whose members include turmeric keeps turmeric.
    (222850, "Turmeric Blend", "turmeric"),
])
def test_curcuminoid_header_with_its_turmeric_oil_keeps_its_identity(enrich, dsld_id, label, canonical_id):
    iqd = enrich(dsld_id)["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] + iqd["ingredients_skipped"] if r.get("raw_source_text") == label]
    assert rows and {r["canonical_id"] for r in rows} == {canonical_id}


@pytest.mark.parametrize("forms,parent", [
    (["Essential Oils"], "Ginger root extract"),  # an essential oil not tied to turmeric
    (["Ginger"], "BCM-95 Bio-Curcumin Turmeric 25:1 extract"),  # an unrelated member
])
def test_curcuminoid_header_with_another_member_is_not_kept(forms, parent):
    registry = build_canonical_identity_registry({"ingredient_quality_map": {
        "curcumin": {"standard_name": "Curcumin", "aliases": [],
                     "forms": {"curcumin (unspecified)": {"aliases": ["total curcuminoids"]}}},
        "volatile_oils": {"standard_name": "Volatile Oils", "aliases": ["essential oils"]},
        "ginger": {"standard_name": "Ginger", "aliases": []},
    }})
    decision = resolve_identity(
        row={"raw_source_text": "Total Curcuminoids complex", "standardName": "Curcumin",
             "cleaner_row_role": "blend_header_total", "parentBlend": parent,
             "forms": [{"name": form} for form in forms]},
        supplied_canonical_id="curcumin",
        resolve_candidate=lambda value: None,
        allow_unscoreable_taxonomy_only=True,
        canonical_registry=registry,
    )
    assert decision.canonical_id is None
