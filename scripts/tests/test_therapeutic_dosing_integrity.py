"""Integrity + contract regression suite for the dosing reference DBs.

Covers `rda_therapeutic_dosing.json` (botanical + collagen scoring source) and the
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
        assert e.get("data"), f"{std} must carry a data[] age/sex grid so it scores"


def test_batch3_scores_via_calculator():
    """Migrated bioactives must be found + scoring-eligible in the RDA calculator."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rda_ul_calculator import RDAULCalculator

    c = RDAULCalculator()
    for name, amt, unit in [("beta-alanine", 3.2, "g"), ("citrulline malate", 8000, "mg"),
                            ("l-citrulline", 4000, "mg"), ("hmb", 3, "g")]:
        r = c.compute_nutrient_adequacy(name, amt, unit)
        assert r.rda_ai is not None and r.scoring_eligible, f"{name} not scoring-eligible in optimal-uls"


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
