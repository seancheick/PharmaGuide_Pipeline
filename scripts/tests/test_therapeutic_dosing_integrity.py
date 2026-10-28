"""Integrity + contract regression suite for the dosing reference DBs.

Covers `rda_therapeutic_dosing.json` (non-RDA therapeutic dose anchors) and the
citation-verifier wiring shared with `rda_optimal_uls.json`. Grows per batch of the
dosing-overhaul plan (boundary cleanup, migration, verified expansion).

These assertions are deliberately structural/contractual — clinical dose-range
*values* are validated against primary sources during the per-entry research pass,
and the dose *bands* are asserted by the v4 scorer suites
(test_v4_botanical_profile / test_v4_collagen_profile / test_collagen_taxonomy).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
THERAPEUTIC = DATA_DIR / "rda_therapeutic_dosing.json"
OPTIMAL_ULS = DATA_DIR / "rda_optimal_uls.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def therapeutic() -> dict:
    return _load(THERAPEUTIC)


@pytest.fixture(scope="module")
def optimal_uls() -> dict:
    return _load(OPTIMAL_ULS)


# ── metadata count truth ────────────────────────────────────────────────

def test_therapeutic_metadata_count_matches(therapeutic):
    entries = therapeutic["therapeutic_dosing"]
    assert therapeutic["_metadata"]["total_entries"] == len(entries)


def test_optimal_uls_metadata_count_matches(optimal_uls):
    entries = optimal_uls["nutrient_recommendations"]
    assert optimal_uls["_metadata"]["total_entries"] == len(entries)


def test_therapeutic_purpose_remains_broad_non_rda_contract(therapeutic):
    purpose = therapeutic["_metadata"]["purpose"]
    assert "not covered by RDA/UL standards" in purpose
    assert "no general dose range, serving size, efficacy grade or safety ceiling" in purpose


RETAINED_CAUTIONS = {
    "st_john_s_wort": "CYP450", "ginkgo_biloba_extract": "bleeding", "cinnamon_cassia": "coumarin",
    "vitex_agnus_castus": "pregnancy", "andrographis_paniculata": "pregnancy",
    "holy_basil_tulsi": "pregnancy", "elderberry": "cyanogenic", "black_seed_oil_nigella_sativa": "anticoagulants",
    "ashwagandha_root_extract": "thyroid", "probiotics_general": "Immunocompromised",
    "lemon_balm": "CNS depressants", "bergamot": "statins", "gymnema_sylvestre": "antidiabetics",
}


def test_retired_dose_and_ceiling_fields_stay_retired(therapeutic):
    """No record re-gains a generic range, serving, grade or safety ceiling, and the
    clinically relevant cautions those fields carried survive in notes."""
    import re
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from db_integrity_sanity_check import RETIRED_THERAPEUTIC_FIELDS, check_rda_therapeutic
    findings = []
    check_rda_therapeutic(findings, therapeutic, "rda_therapeutic_dosing.json")
    assert not [f for f in findings if f.issue == "retired_field_present"]
    # Unqualified universal safety or dose conclusions only. A source-qualified statement
    # ("well tolerated at the tested dose in this six-week trial") is not banned.
    generic_ceiling = re.compile(r"\bsafe up to\b|\bsafe for long-term use\b|\bgenerally (very )?safe\b"
                                 r"|\bstandard (single )?(validated )?dose\b|\bvalidated dose\b", re.I)
    rows = {e["id"]: e for e in therapeutic["therapeutic_dosing"]}
    for e in rows.values():
        assert not RETIRED_THERAPEUTIC_FIELDS & set(e), e["id"]
        for key in ("notes", "common_use"):
            assert not generic_ceiling.search(e.get(key) or ""), (e["id"], key)
    for rid, caution in RETAINED_CAUTIONS.items():
        assert caution in rows[rid]["notes"], rid
    # The retired claims are gone from every free-text field, approved purpose included.
    for rid, phrase in (("collagen_peptides", "2.5 g+"), ("collagen_peptides", "5-10 g"),
                        ("gelatin", "LOWER bioavailability"), ("uc_ii_collagen", "gram range"),
                        ("ginkgo_biloba_extract", ">240mg")):
        assert phrase not in json.dumps(rows[rid]), (rid, phrase)
    planted = {"therapeutic_dosing": [{"standard_name": "X", "upper_limit": "100"}]}
    findings = []
    check_rda_therapeutic(findings, planted, "rda_therapeutic_dosing.json")
    assert any(f.issue == "retired_field_present" for f in findings)


# ── references[] shape: bare PMID digit-strings only ────────────────────

@pytest.mark.parametrize("filename", ["rda_therapeutic_dosing.json", "rda_optimal_uls.json"])
def test_references_are_bare_pmid_strings(filename):
    data = _load(DATA_DIR / filename)
    key = "therapeutic_dosing" if "therapeutic" in filename else "nutrient_recommendations"
    for e in data[key]:
        refs = e.get("references")
        if refs is None:
            continue
        assert isinstance(refs, list), f"{e.get('standard_name')}: references must be a list"
        for r in refs:
            assert isinstance(r, str) and r.isdigit(), (
                f"{e.get('standard_name')}: reference {r!r} must be a bare PMID digit-string"
            )


def test_no_source_pmids_convention_drift(therapeutic, optimal_uls):
    """Single citation convention: references[]. No parallel source_pmids field."""
    for data, key in ((therapeutic, "therapeutic_dosing"), (optimal_uls, "nutrient_recommendations")):
        for e in data[key]:
            assert "source_pmids" not in e, f"{e.get('standard_name')}: use references[], not source_pmids"


# ── collagen scorer-contract guard (committed v4 Phase 7, commit eec0e3ba) ──

# collagen_profile keys dose routing on these exact normalized aliases — renaming
# them silently breaks collagen dose scoring. Locked here.
COLLAGEN_REQUIRED_ALIASES = {"uc-ii", "nem", "biocell", "gelatin", "collagen"}


def test_collagen_routing_aliases_present(therapeutic):
    all_aliases = set()
    for e in therapeutic["therapeutic_dosing"]:
        all_aliases.update(a.lower() for a in (e.get("aliases") or []))
        all_aliases.add((e.get("standard_name") or "").lower())
    missing = {a for a in COLLAGEN_REQUIRED_ALIASES if a not in all_aliases}
    assert not missing, f"collagen routing aliases missing (breaks collagen_profile): {missing}"


def test_collagen_entries_carry_verified_references(therapeutic):
    """The 5 collagen entries shipped with content-verified PMIDs — keep them."""
    collagen_ids = {
        "collagen_peptides", "uc_ii_collagen", "biocell_collagen",
        "gelatin", "eggshell_membrane_nem",
    }
    by_id = {e.get("id"): e for e in therapeutic["therapeutic_dosing"]}
    for cid in collagen_ids:
        assert cid in by_id, f"collagen entry {cid} missing"
        assert by_id[cid].get("references"), f"collagen entry {cid} must keep its verified references[]"


# ── Batch 1: migration of inert duplicates (zero score delta) ───────────

# The 4 endogenous/synthetic compounds removed from the therapeutic file because
# they are scored from rda_optimal_uls.json (generic path) and are NOT reachable
# via the botanical or collagen dose adapters — so their removal is score-neutral.
BATCH1_REMOVED = {
    "alpha_lipoic_acid": "Alpha-Lipoic Acid",
    "coenzyme_q10_ubiquinone": "Coenzyme Q10",
    "creatine_monohydrate": "Creatine",
    "taurine": "Taurine",
}


def test_batch1_removed_entries_absent(therapeutic):
    ids = {e.get("id") for e in therapeutic["therapeutic_dosing"]}
    for rid in BATCH1_REMOVED:
        assert rid not in ids, f"{rid} should have been removed from therapeutic file"


def test_batch1_removed_are_unreachable_via_botanical(therapeutic):
    """Zero-delta proof (static half): the removed compounds are not in the
    botanical identity set, so _is_botanical_active can only fire on them via an
    enricher 'botanical' tag — which never happens for these endogenous/synthetic
    compounds. Thus the botanical dose adapter could never have consumed them."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scoring_v4.modules.botanical_profile import _norm, _botanical_identity_set

    bset = _botanical_identity_set()
    # probe the removed names + their aliases
    probes = {
        "alpha_lipoic_acid": ["alpha-lipoic acid", "ala", "thioctic acid"],
        "coenzyme_q10_ubiquinone": ["coenzyme q10", "coq10", "ubiquinone"],
        "creatine_monohydrate": ["creatine", "creatine monohydrate"],
        "taurine": ["taurine", "l-taurine"],
    }
    for rid, names in probes.items():
        hits = [n for n in names if _norm(n) in bset]
        assert not hits, f"{rid} is botanical-name-matched ({hits}) — removal NOT score-neutral"


def test_batch1_coverage_preserved_in_optimal_uls(optimal_uls):
    """Coverage must not be lost: each removed bioactive must exist in optimal-uls."""
    names = {(e.get("standard_name") or "").lower() for e in optimal_uls["nutrient_recommendations"]}
    for std in BATCH1_REMOVED.values():
        assert std.lower() in names, f"{std} missing from rda_optimal_uls.json (coverage lost)"


def test_lutein_retained_botanical_routable(therapeutic):
    """Lutein stays: it is botanical-routable via marigold (in botanical_ingredients.json),
    so its therapeutic entry is consumed for marigold-derived products — NOT a dead duplicate."""
    ids = {e.get("id") for e in therapeutic["therapeutic_dosing"]}
    assert "lutein" in ids


# ── Batch 3: migrate sports-amino bioactives → optimal-uls ──────────────

# Migrated OUT of therapeutic and INTO rda_optimal_uls.json (generic dose path),
# each with content-verified PMIDs. id-in-therapeutic -> standard_name-in-optimal-uls.
BATCH3_MIGRATED = {
    "beta_alanine": "Beta-Alanine",
    "citrulline_malate": "Citrulline Malate",
    "l_citrulline": "L-Citrulline",
    "hmb_beta_hydroxy_beta_methylbutyrate": "HMB",
}


def test_batch3_migrated_absent_from_therapeutic(therapeutic):
    ids = {e.get("id") for e in therapeutic["therapeutic_dosing"]}
    for rid in BATCH3_MIGRATED:
        assert rid not in ids, f"{rid} should have migrated out of the therapeutic file"


def test_batch3_present_in_optimal_uls_with_references(optimal_uls):
    by_name = {(e.get("standard_name") or "").lower(): e for e in optimal_uls["nutrient_recommendations"]}
    for std in BATCH3_MIGRATED.values():
        e = by_name.get(std.lower())
        assert e is not None, f"{std} missing from rda_optimal_uls.json after migration"
        assert e.get("references"), f"{std} must carry content-verified references[]"
        assert e.get("data"), f"{std} must retain its source-context grid"


def test_batch3_studied_records_are_found_without_nutritional_credit():
    """Finding a source record does not turn its study amount into an RDA."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rda_ul_calculator import RDAULCalculator

    c = RDAULCalculator()
    for name, amt, unit in [("beta-alanine", 3.2, "g"), ("citrulline malate", 8000, "mg"),
                            ("l-citrulline", 4000, "mg"), ("hmb", 3, "g")]:
        r = c.compute_nutrient_adequacy(name, amt, unit)
        assert r.rda_ai is not None, f"{name} source context was lost"
        assert r.rda_ai_source == "unknown"
        assert r.scoring_eligible is False
        assert c._find_nutrient(name)["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"


# ── Batch 4: migrate remaining non-botanical bioactives → optimal-uls ───

BATCH4_MIGRATED = {
    "glucosamine_sulfate": "Glucosamine Sulfate",
    "msm_methylsulfonylmethane": "MSM",
    "hyaluronic_acid": "Hyaluronic Acid",
    "gaba_gamma_aminobutyric_acid": "GABA",
    "melatonin": "Melatonin",
    "nac_n_acetyl_cysteine": "NAC",
    "ubiquinol_active_coq10": "Ubiquinol",
    "magnesium_l_threonate": "Magnesium L-Threonate",
    "nmn_nicotinamide_mononucleotide": "NMN",
    "pqq_pyrroloquinoline_quinone": "PQQ",
    "sam_e_s_adenosyl_methionine": "SAM-e",
    "berberine": "Berberine",
    "quercetin": "Quercetin",
    "dim_diindolylmethane": "DIM",
    "5_htp_5_hydroxytryptophan": "5-HTP",
}


def test_batch4_migrated_absent_from_therapeutic(therapeutic):
    ids = {e.get("id") for e in therapeutic["therapeutic_dosing"]}
    for rid in BATCH4_MIGRATED:
        assert rid not in ids, f"{rid} should have migrated out of the therapeutic file"


def test_batch4_present_in_optimal_uls_with_refs_and_grid(optimal_uls):
    by_name = {(e.get("standard_name") or "").lower(): e for e in optimal_uls["nutrient_recommendations"]}
    for std in BATCH4_MIGRATED.values():
        e = by_name.get(std.lower())
        assert e is not None, f"{std} missing from rda_optimal_uls.json"
        assert e.get("references"), f"{std} must carry content-verified references[]"
        assert len(e.get("data") or []) == 16, f"{std} must have a full 16-row data[] grid"


def test_current_therapeutic_entries_have_a_consuming_route(therapeutic):
    """Current-state invariant: every shipped therapeutic entry must be reachable
    by an existing scorer path or explicit route exception. This prevents dead
    data without narrowing the file's clinical domain to botanical/collagen only."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scoring_v4.modules.botanical_profile import _norm, _botanical_identity_set

    bset = _botanical_identity_set()
    collagen_ids = {"collagen_peptides", "uc_ii_collagen", "biocell_collagen", "gelatin", "eggshell_membrane_nem"}
    allowed_exceptions = {
        "probiotics_general",  # CFU unit — cannot fit the mg/g optimal-uls schema
        "lutein",              # marigold-routable: consumed via a marigold active's matched_form, not the entry name
        "neumentix_spearmint_extract",  # exact spearmint matched_form; source-scoped no-threshold decision, not generic tea
    }
    for e in therapeutic["therapeutic_dosing"]:
        eid = e.get("id")
        if eid in collagen_ids or eid in allowed_exceptions:
            continue
        keys = [_norm(e.get("standard_name"))] + [_norm(a) for a in (e.get("aliases") or [])]
        assert any(k in bset for k in keys), (
            f"{e.get('standard_name')} is neither botanical-name-matched, collagen, nor an allowed exception"
        )


# ── Batch 7: optimal-uls bioactive expansion + Inositol correction ──────

BATCH7_NEW_BIOACTIVES = [
    "Citicoline", "Betaine Anhydrous (TMG)", "Glycine",
    "Essential Amino Acids (EAA)", "Pantethine", "Urolithin A",
    "Bovine Colostrum", "L-Glutamine",
]


def test_batch7_new_bioactives_present_with_refs(optimal_uls):
    by_name = {(e.get("standard_name") or "").lower(): e for e in optimal_uls["nutrient_recommendations"]}
    for std in BATCH7_NEW_BIOACTIVES:
        e = by_name.get(std.lower())
        assert e is not None, f"{std} missing from rda_optimal_uls.json"
        assert e.get("references"), f"{std} must carry content-verified references[]"
        assert len(e.get("data") or []) == 16, f"{std} must have a 16-row data[] grid"


def test_inositol_range_corrected(optimal_uls):
    inos = [e for e in optimal_uls["nutrient_recommendations"] if (e.get("standard_name") or "").lower() == "inositol"]
    assert len(inos) == 1
    assert inos[0]["optimal_range"] == "2000-4000", "Retain the reviewed regimen context without creating a scoring range"
    assert inos[0]["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"
    assert "38163998" in (inos[0].get("references") or []), "Inositol must cite the 2023 PCOS guideline meta-analysis"


# ── Batch 8: fatty-acid/chlorophyllin dose-anchor expansion ─────────────

BATCH8_NEW_DOSE_ANCHORS = [
    "Gamma-Linolenic Acid",
    "Evening Primrose Oil",
    "Chlorophyllin",
]


def test_batch8_new_dose_anchors_present_with_refs(optimal_uls):
    by_name = {(e.get("standard_name") or "").lower(): e for e in optimal_uls["nutrient_recommendations"]}
    for std in BATCH8_NEW_DOSE_ANCHORS:
        e = by_name.get(std.lower())
        assert e is not None, f"{std} missing from rda_optimal_uls.json"
        assert e.get("references"), f"{std} must carry content-verified references[]"
        assert len(e.get("data") or []) == 16, f"{std} must have a 16-row data[] grid"


def test_batch8_studied_records_are_found_without_nutritional_credit():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rda_ul_calculator import RDAULCalculator

    c = RDAULCalculator()
    for name, amt, unit in [
        ("gamma-linolenic acid", 120, "mg"),
        ("evening primrose oil", 500, "mg"),
        ("sodium copper chlorophyllin", 300, "mg"),
    ]:
        r = c.compute_nutrient_adequacy(name, amt, unit)
        assert r.rda_ai is not None, f"{name} source context was lost"
        assert r.rda_ai_source == "unknown"
        assert r.scoring_eligible is False
        assert c._find_nutrient(name)["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"


def test_chlorophyllin_anchor_does_not_alias_generic_chlorophyll(optimal_uls):
    chlorophyllin = [
        e for e in optimal_uls["nutrient_recommendations"]
        if (e.get("standard_name") or "").lower() == "chlorophyllin"
    ][0]
    aliases = {a.lower() for a in chlorophyllin.get("aliases") or []}
    assert "chlorophyll" not in aliases


def test_generic_chlorophyll_does_not_partially_match_chlorophyllin_anchor():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rda_ul_calculator import RDAULCalculator

    c = RDAULCalculator()
    natural = c.compute_nutrient_adequacy("chlorophyll", 300, "mg")
    chlorophyllin = c.compute_nutrient_adequacy("chlorophyllin", 300, "mg")

    assert natural.rda_ai is None
    assert natural.scoring_eligible is False
    assert chlorophyllin.rda_ai == 300.0
    assert chlorophyllin.rda_ai_source == "unknown"
    assert chlorophyllin.scoring_eligible is False
    assert c._find_nutrient("chlorophyllin")["reference_semantics"]["reference_type"] == "discrete_studied_regimen"


# ── citation verifier wiring ────────────────────────────────────────────

def test_citation_verifier_configs_present():
    """Both dosing files must have a content-verifier FILE_CONFIG so their PMIDs
    are gated by verify_all_citations_content.py (pmid_list source format)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api_audit"))
    import verify_all_citations_content as vac

    by_file = {c["file"]: c for c in vac.FILE_CONFIGS}
    for fname in ("rda_therapeutic_dosing.json", "rda_optimal_uls.json"):
        assert fname in by_file, f"no verifier FILE_CONFIG for {fname}"
        assert by_file[fname]["source_format"] == "pmid_list"
        assert by_file[fname]["sources_field"] == "references"
