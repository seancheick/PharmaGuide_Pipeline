"""Focused tests for scripts/api_audit/verify_interaction_rules_citations.py.

The two fixtures are excerpts (title, first abstract sentence, MeSH) of the real
PubMed records of the ghost citations removed on 2026-09-25. The old
union-of-claims word overlap passed both.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api_audit"))

import verify_interaction_rules_citations as virc  # noqa: E402

# PMID 32876395: names cascara, supports none of the claims it was cited for.
CASCAROSIDE_CHROMATOGRAPHY = {
    "title": (
        "Isolation of six anthraquinone diglucosides from cascara sagrada bark "
        "by high-performance countercurrent chromatography."
    ),
    "abstract": (
        "In this study, high-performance countercurrent chromatography was "
        "employed to isolate six anthraquinone diglucosides, namely, cascarosides "
        "A-F, from cascara sagrada (Rhamnus purshiana DC [Rhamnaceae]) bark."
    ),
    "mesh_terms": [
        "anthraquinones", "chromatography, high pressure liquid",
        "countercurrent distribution", "glucosides", "molecular conformation",
        "plant bark", "plant extracts", "rhamnus", "stereoisomerism",
    ],
}
# PMID 36702448: Cassia obtusifolia / C. tora seeds; only its MeSH says senna.
CASSIAE_SEMEN_REVIEW = {
    "title": (
        "Cassiae Semen: A comprehensive review of botany, traditional use, "
        "phytochemistry, pharmacology, toxicity, and quality control."
    ),
    "abstract": (
        "Cassiae Semen, belonging to the family Leguminosae, is derived from the "
        "dry mature seeds of Cassia obtusifolia L. or Cassia tora L. and has long "
        "been used as a laxative, hepatoprotective, improve eyesight, and "
        "antidiabetic complications medicine or functional food in Asia."
    ),
    "mesh_terms": [
        "plants, medicinal", "medicine, chinese traditional", "botany",
        "quality control", "senna plant", "phytochemicals", "seeds",
        "ethnopharmacology", "plant extracts",
    ],
}
FISH_OIL_WARFARIN = {
    "title": "Fish oil interaction with warfarin.",
    "abstract": "",
    "mesh_terms": ["fatty acids, omega-3", "international normalized ratio", "warfarin"],
}


def _phrases(db: str, canonical_id: str) -> set[str]:
    entries = virc.load_subject_entries()
    return virc.subject_phrases({"db": db, "canonical_id": canonical_id}, entries)


def test_on_subject_off_claim_citation_fails_topic():
    phrases = _phrases("ingredient_quality_map", "cascara_sagrada")
    for topic in (
        "condition:pregnancy",
        "condition:liver_disease",
        "condition:kidney_disease",
        "drug:cardiac_glycosides",
        "pregnancy_lactation",
    ):
        assert virc.check_citation(CASCAROSIDE_CHROMATOGRAPHY, phrases, topic) == ["topic"]


def test_related_species_citation_fails_subject_even_with_mesh_match():
    phrases = _phrases("ingredient_quality_map", "senna")
    assert "senna" in phrases
    for topic in ("condition:kidney_disease", "drug:cardiac_glycosides"):
        assert virc.check_citation(CASSIAE_SEMEN_REVIEW, phrases, topic) == [
            "subject",
            "topic",
        ]


def test_on_subject_on_claim_citation_passes():
    phrases = _phrases("ingredient_quality_map", "fish_oil")
    assert virc.check_citation(FISH_OIL_WARFARIN, phrases, "drug:anticoagulants") == []


def test_unknown_topic_fails_instead_of_passing_silently():
    phrases = _phrases("ingredient_quality_map", "fish_oil")
    assert virc.check_citation(FISH_OIL_WARFARIN, phrases, "drug:not_a_class") == ["topic"]


def test_every_rule_topic_has_stems():
    rules = json.loads((ROOT / "data" / "ingredient_interaction_rules.json").read_text())
    topics = set()
    for rule in rules["interaction_rules"]:
        topics |= {c["condition_id"] for c in rule.get("condition_rules") or []}
        topics |= {c["drug_class_id"] for c in rule.get("drug_class_rules") or []}
    assert topics - set(virc.TOPIC_STEMS) == set()


def test_subject_phrases_drop_trailing_part_words():
    phrases = _phrases("botanical_ingredients", "licorice_root")
    assert {"licorice root", "licorice"} <= phrases


def test_strict_mode_passes_only_reviewed_suspects(tmp_path):
    suspects = [("32876395", "RULE_X", "condition:pregnancy", ["topic"], "title")]
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"reviewed": [
        {"pmid": "32876395", "rule_id": "RULE_X", "sub_rule": "condition:pregnancy",
         "rationale": ""},
    ]}))
    assert virc.unreviewed(suspects, virc.reviewed_keys(review)) == suspects
    review.write_text(json.dumps({"reviewed": [
        {"pmid": "32876395", "rule_id": "RULE_X", "sub_rule": "condition:pregnancy",
         "rationale": "class-level review that names the claim in its full text"},
    ]}))
    assert virc.unreviewed(suspects, virc.reviewed_keys(review)) == []


def test_subject_phrases_skip_common_words():
    """Short aliases and stripped heads such as "age" (garlic AGE), "same"
    (SAMe), "black" (black seed oil) and "hip"/"rust" (iron) occur in almost
    any abstract, so they would pass the subject check for every citation."""
    assert "age" not in _phrases("ingredient_quality_map", "garlic")
    assert "same" not in _phrases("ingredient_quality_map", "same")
    assert "black" not in _phrases("ingredient_quality_map", "black_seed_oil")
    assert {"hip", "rust"}.isdisjoint(_phrases("ingredient_quality_map", "iron"))
    fish_oil = _phrases("ingredient_quality_map", "fish_oil")
    assert "fish oil" in fish_oil and "fish" not in fish_oil
    assert "iron" in _phrases("ingredient_quality_map", "iron")  # the entry's own name
    # Short names that are real identities stay: a digit, or a plant name left
    # after stripping a part word ("kava root" -> "kava").
    assert "b12" in _phrases("ingredient_quality_map", "vitamin_b12_cobalamin")
    assert "kava" in _phrases("ingredient_quality_map", "kavalactones")


def test_bookshelf_sources_are_collected_per_sub_rule():
    rules = [{
        "id": "RULE_X",
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "5_htp"},
        "drug_class_rules": [{"drug_class_id": "maois", "sources": [
            "https://www.ncbi.nlm.nih.gov/books/NBK548375/",
            "https://pubmed.ncbi.nlm.nih.gov/31523132/",
        ]}],
    }]
    claims = virc.collect_claims(rules, virc.load_subject_entries())
    assert {key: [(rid, label) for rid, label, _ in value] for key, value in claims.items()} == {
        "NBK548375": [("RULE_X", "drug:maois")],
        "31523132": [("RULE_X", "drug:maois")],
    }


def test_bookshelf_chapter_must_name_the_subject():
    """NBK548375 is LiverTox "Muscle Relaxants"; it was cited for 5-HTP. A
    Bookshelf chapter is a per-drug monograph, so only the subject is checked,
    against the chapter and book titles."""
    htp = _phrases("ingredient_quality_map", "5_htp")
    livertox = "LiverTox: Clinical and Research Information on Drug-Induced Liver Injury"
    assert virc.check_book_chapter({"title": "Muscle Relaxants", "books": [livertox]}, htp) == ["subject"]
    cascara = _phrases("ingredient_quality_map", "cascara_sagrada")
    assert virc.check_book_chapter({"title": "Cascara", "books": [livertox]}, cascara) == []
    fish_oil = _phrases("ingredient_quality_map", "fish_oil")
    assert virc.check_book_chapter(
        {"title": "HEALTH EFFECTS", "books": ["Toxicological Profile for Fish Oil"]}, fish_oil
    ) == []


def test_bookshelf_record_parses_book_titles():
    record = {
        "rid": "NBK592340",
        "title": "HEALTH EFFECTS",
        "bookinfo": (
            '<Info><Path><Parent id="tpvanadium" role="source" type="book" uid="5466422">'
            "<Title>Toxicological Profile for Vanadium</Title></Parent>"
            '<Self id="ch3" role="document" type="chapter" uid="5466550">'
            "<Title>HEALTH EFFECTS</Title></Self></Path></Info>"
        ),
    }
    assert virc.book_chapter(record) == {
        "title": "HEALTH EFFECTS",
        "books": ["Toxicological Profile for Vanadium"],
    }
