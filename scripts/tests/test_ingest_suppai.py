"""Unit tests for scripts/ingest_suppai.py.

Pure-function, hermetic. Uses in-memory fake supp.ai dumps so tests never
touch the real 254 MB corpus. Covers:

- parse_pair_id / sort_pair_key — deterministic key handling
- build_cui_to_canonical_index / build_known_drug_rxcuis — anchor indexes
- filter_pair_by_anchor — supplement-side OR drug-side anchor
- score_sentence — recency × clinical × length × study-type
- select_top_sentences — at most N, retraction filtered, human preferred
- compress_paper_meta — only 4 fields retained (PHI + bundle-size control)
- build_research_pair_row — full shape + canonical_id / rxcui resolution
- enrich_curated_with_suppai — appends supp.ai PMIDs without duplicating
- run_ingest — full pipeline smoke test against a fake 5-file dump
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ingest_suppai as ing  # noqa: E402


# --------------------------------------------------------------------------- #
# Tiny in-memory dump fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_cui_metadata() -> dict:
    return {
        "C0042878": {
            "ent_type": "supplement",
            "preferred_name": "Vitamin K",
            "synonyms": ["Phytonadione"],
            "tradenames": [],
        },
        "C0016157": {
            "ent_type": "supplement",
            "preferred_name": "Fish Oil",
            "synonyms": ["Omega-3"],
            "tradenames": [],
        },
        "C0043031": {
            "ent_type": "drug",
            "preferred_name": "Warfarin",
            "synonyms": [],
            "tradenames": ["Coumadin"],
        },
        "C9999999": {
            "ent_type": "supplement",
            "preferred_name": "Obscurone",
            "synonyms": [],
            "tradenames": [],
        },
    }


@pytest.fixture
def fake_sentence_dict() -> dict:
    return {
        # anchored (vitamin K in IQM) — will be kept
        "C0042878-C0043031": [
            {
                "arg1": {"id": "C0042878", "span": [0, 9]},
                "arg2": {"id": "C0043031", "span": [20, 28]},
                "confidence": 0.9,
                "paper_id": "28458697",
                "sentence": (
                    "Vitamin K supplementation reduced warfarin effect and "
                    "lowered INR in patients on stable anticoagulation therapy."
                ),
                "sentence_id": 1,
                "uid": 1,
            },
            {
                "arg1": {"id": "C0042878", "span": [0, 9]},
                "arg2": {"id": "C0043031", "span": [20, 28]},
                "confidence": 0.8,
                "paper_id": "99999999",  # retraction — must be filtered
                "sentence": "Retracted sentence should not appear.",
                "sentence_id": 2,
                "uid": 2,
            },
            {
                "arg1": {"id": "C0042878", "span": [0, 9]},
                "arg2": {"id": "C0043031", "span": [20, 28]},
                "confidence": 0.7,
                "paper_id": "12345678",
                "sentence": (
                    "Clinical study showed INR changes in subjects given "
                    "oral vitamin K while receiving warfarin therapy."
                ),
                "sentence_id": 3,
                "uid": 3,
            },
            {
                "arg1": {"id": "C0042878", "span": [0, 9]},
                "arg2": {"id": "C0043031", "span": [20, 28]},
                "confidence": 0.5,
                "paper_id": "11111111",
                "sentence": "Short.",  # boilerplate-length, deprioritized
                "sentence_id": 4,
                "uid": 4,
            },
            {
                "arg1": {"id": "C0042878", "span": [0, 9]},
                "arg2": {"id": "C0043031", "span": [20, 28]},
                "confidence": 0.6,
                "paper_id": "22222222",
                "sentence": (
                    "Older study in rats showed reduction of warfarin "
                    "potency when vitamin K was coadministered."
                ),
                "sentence_id": 5,
                "uid": 5,
            },
        ],
        # supplement anchored (fish oil in IQM), drug known via rxcui map
        "C0016157-C0043031": [
            {
                "arg1": {"id": "C0016157", "span": [0, 8]},
                "arg2": {"id": "C0043031", "span": [25, 33]},
                "confidence": 0.8,
                "paper_id": "33333333",
                "sentence": (
                    "Omega-3 fatty acids from fish oil may potentiate "
                    "warfarin anticoagulation in elderly patients."
                ),
                "sentence_id": 1,
                "uid": 10,
            }
        ],
        # unanchored (neither side in our maps) — must be dropped
        "C9999999-C8888888": [
            {
                "arg1": {"id": "C9999999", "span": [0, 8]},
                "arg2": {"id": "C8888888", "span": [10, 18]},
                "confidence": 0.3,
                "paper_id": "33333333",
                "sentence": "Obscure-obscure interaction in unmapped space.",
                "sentence_id": 1,
                "uid": 11,
            }
        ],
    }


@pytest.fixture
def fake_paper_metadata() -> dict:
    return {
        "28458697": {
            "pmid": 28458697,
            "year": 2017,
            "clinical_study": True,
            "human_study": True,
            "animal_study": False,
            "retraction": False,
            "title": "Vitamin K and Warfarin Interaction: A Clinical Review",
            "authors": ["Smith J"],
            "venue": "Am J Cardiol",
        },
        "99999999": {
            "pmid": 99999999,
            "year": 2010,
            "clinical_study": False,
            "human_study": False,
            "animal_study": False,
            "retraction": True,  # filtered
            "title": "[RETRACTED] Spurious study",
            "authors": [],
            "venue": "",
        },
        "12345678": {
            "pmid": 12345678,
            "year": 2019,
            "clinical_study": True,
            "human_study": True,
            "animal_study": False,
            "retraction": False,
            "title": "INR monitoring in anticoagulated patients",
            "authors": [],
            "venue": "Thromb Res",
        },
        "11111111": {
            "pmid": 11111111,
            "year": 2020,
            "clinical_study": False,
            "human_study": True,
            "animal_study": False,
            "retraction": False,
            "title": "Short abstract",
            "authors": [],
            "venue": "Notes",
        },
        "22222222": {
            "pmid": 22222222,
            "year": 1995,
            "clinical_study": False,
            "human_study": False,
            "animal_study": True,  # downweighted
            "retraction": False,
            "title": "Rat study",
            "authors": [],
            "venue": "Rat Research",
        },
        "33333333": {
            "pmid": 33333333,
            "year": 2018,
            "clinical_study": True,
            "human_study": True,
            "animal_study": False,
            "retraction": False,
            "title": "Fish oil and warfarin pharmacokinetics",
            "authors": [],
            "venue": "BMJ",
        },
    }


@pytest.fixture
def fake_iqm() -> dict:
    return {
        "_metadata": {"schema_version": "5.0.0"},
        "vitamin_k": {
            "standard_name": "Vitamin K",
            "cui": "C0042878",
            "rxcui": None,
            "category": "vitamin",
        },
        "fish_oil": {
            "standard_name": "Fish Oil",
            "cui": "C0016157",
            "rxcui": "4419",
            "category": "fatty_acid",
        },
        "ingredient_with_no_cui": {
            "standard_name": "Mystery",
            "cui": None,
            "rxcui": None,
            "category": "mystery",
        },
    }


@pytest.fixture
def fake_drug_classes() -> dict:
    return {
        "_metadata": {"schema_version": "1.0.0"},
        "classes": {
            "class:anticoagulants": {
                "display_name": "Anticoagulants",
                "description": "",
                "member_rxcuis": ["11289"],
                "member_names": ["warfarin"],
                "rxclass_id": "N0000029128",
                "atc_codes": ["B01AA"],
            }
        },
    }


# --------------------------------------------------------------------------- #
# Parse / sort helpers
# --------------------------------------------------------------------------- #


def test_parse_pair_id_returns_two_cuis():
    assert ing.parse_pair_id("C0042878-C0043031") == ("C0042878", "C0043031")


def test_parse_pair_id_raises_on_malformed():
    with pytest.raises(ValueError):
        ing.parse_pair_id("not-a-pair")
    with pytest.raises(ValueError):
        ing.parse_pair_id("")


def test_sort_pair_key_is_lex_sorted():
    assert ing.sort_pair_key("C0043031", "C0042878") == ("C0042878", "C0043031")
    assert ing.sort_pair_key("C0042878", "C0043031") == ("C0042878", "C0043031")


# --------------------------------------------------------------------------- #
# Anchor index construction
# --------------------------------------------------------------------------- #


def test_build_cui_to_canonical_index(fake_iqm):
    idx = ing.build_cui_to_canonical_index(fake_iqm)
    assert idx == {"C0042878": "vitamin_k", "C0016157": "fish_oil"}


def test_build_cui_to_canonical_index_skips_metadata(fake_iqm):
    idx = ing.build_cui_to_canonical_index(fake_iqm)
    assert "_metadata" not in idx.values()


def test_build_known_drug_rxcuis(fake_drug_classes):
    rxcuis = ing.build_known_drug_rxcuis(fake_drug_classes)
    assert rxcuis == {"11289"}


def test_build_known_supplement_cuis_from_iqm(fake_iqm):
    cuis = ing.build_known_supplement_cuis(fake_iqm)
    assert cuis == {"C0042878", "C0016157"}


# --------------------------------------------------------------------------- #
# Pair anchor filter
# --------------------------------------------------------------------------- #


def test_pair_is_anchored_when_one_side_in_iqm(fake_cui_metadata):
    anchor = ing.PairAnchor(
        supplement_cuis={"C0042878"},
        known_drug_cuis=set(),
    )
    assert ing.pair_is_anchored("C0042878-C9999999", anchor, fake_cui_metadata)


def test_pair_is_anchored_when_drug_side_recognized(fake_cui_metadata):
    """When neither CUI is in IQM but one is a known drug in supp.ai with a
    mapped RxNorm crosswalk, the pair is still useful."""
    anchor = ing.PairAnchor(
        supplement_cuis={"C0016157"},
        known_drug_cuis={"C0043031"},
    )
    # C0016157 (fish oil, in IQM) + C0043031 (warfarin, known drug)
    assert ing.pair_is_anchored("C0016157-C0043031", anchor, fake_cui_metadata)


def test_pair_is_not_anchored_when_both_sides_unknown(fake_cui_metadata):
    anchor = ing.PairAnchor(
        supplement_cuis={"C0042878"},
        known_drug_cuis=set(),
    )
    assert not ing.pair_is_anchored("C9999999-C8888888", anchor, fake_cui_metadata)


# --------------------------------------------------------------------------- #
# Sentence scoring
# --------------------------------------------------------------------------- #


def test_score_sentence_prefers_human_clinical_recent_long(
    fake_sentence_dict, fake_paper_metadata
):
    sentences = fake_sentence_dict["C0042878-C0043031"]
    # index 0 — 2017, clinical, long
    # index 2 — 2019, clinical, long
    # index 3 — 2020, non-clinical, very short
    # index 4 — 1995, animal
    s_high = ing.score_sentence(sentences[0], fake_paper_metadata)
    s_higher = ing.score_sentence(sentences[2], fake_paper_metadata)
    s_low = ing.score_sentence(sentences[3], fake_paper_metadata)
    s_animal = ing.score_sentence(sentences[4], fake_paper_metadata)
    assert s_higher > s_animal
    assert s_high > s_animal
    assert s_high > s_low or s_higher > s_low  # clinical+long beats short


def test_score_sentence_treats_retraction_as_bottom(
    fake_sentence_dict, fake_paper_metadata
):
    sentences = fake_sentence_dict["C0042878-C0043031"]
    s_retracted = ing.score_sentence(sentences[1], fake_paper_metadata)
    s_clean = ing.score_sentence(sentences[0], fake_paper_metadata)
    # Retractions must rank strictly below clean entries
    assert s_retracted < s_clean


def test_score_sentence_handles_missing_paper(fake_paper_metadata):
    orphan = {
        "arg1": {"id": "C1", "span": [0, 1]},
        "arg2": {"id": "C2", "span": [0, 1]},
        "paper_id": "not_in_meta",
        "sentence": "x" * 100,
        "sentence_id": 1,
        "uid": 999,
    }
    # Should not raise
    score = ing.score_sentence(orphan, fake_paper_metadata)
    assert isinstance(score, (int, float, tuple))


# --------------------------------------------------------------------------- #
# Top-N selection
# --------------------------------------------------------------------------- #


def test_select_top_sentences_caps_at_n(fake_sentence_dict, fake_paper_metadata):
    sentences = fake_sentence_dict["C0042878-C0043031"]
    top = ing.select_top_sentences(sentences, fake_paper_metadata, n=3)
    assert len(top) <= 3


def test_select_top_sentences_excludes_retractions(
    fake_sentence_dict, fake_paper_metadata
):
    sentences = fake_sentence_dict["C0042878-C0043031"]
    top = ing.select_top_sentences(sentences, fake_paper_metadata, n=5)
    top_pmids = {s["paper_id"] for s in top}
    assert "99999999" not in top_pmids, "retracted paper must be filtered"


def test_select_top_sentences_deterministic(
    fake_sentence_dict, fake_paper_metadata
):
    sentences = fake_sentence_dict["C0042878-C0043031"]
    top_a = ing.select_top_sentences(sentences, fake_paper_metadata, n=3)
    top_b = ing.select_top_sentences(sentences, fake_paper_metadata, n=3)
    assert [s["uid"] for s in top_a] == [s["uid"] for s in top_b]


def test_select_top_sentences_returns_empty_when_all_retracted(
    fake_paper_metadata,
):
    only_retracted = [
        {
            "arg1": {"id": "Cx", "span": [0, 0]},
            "arg2": {"id": "Cy", "span": [0, 0]},
            "paper_id": "99999999",
            "sentence": "retracted",
            "sentence_id": 1,
            "uid": 99,
        }
    ]
    top = ing.select_top_sentences(only_retracted, fake_paper_metadata, n=3)
    assert top == []


# --------------------------------------------------------------------------- #
# Compress paper metadata (PHI + bundle-size control)
# --------------------------------------------------------------------------- #


def test_compress_paper_meta_retains_only_four_fields(fake_paper_metadata):
    compressed = ing.compress_paper_meta("28458697", fake_paper_metadata)
    assert set(compressed.keys()) == {
        "pmid",
        "year",
        "clinical_study",
        "human_study",
    }
    # no authors, no title, no doi leak
    assert "authors" not in compressed
    assert "title" not in compressed


def test_compress_paper_meta_returns_none_for_missing(fake_paper_metadata):
    assert ing.compress_paper_meta("does_not_exist", fake_paper_metadata) is None


# --------------------------------------------------------------------------- #
# Row builder
# --------------------------------------------------------------------------- #


def test_build_research_pair_row_full_shape(
    fake_sentence_dict,
    fake_paper_metadata,
    fake_iqm,
    fake_drug_classes,
    fake_cui_metadata,
):
    cui_to_canonical = ing.build_cui_to_canonical_index(fake_iqm)
    row = ing.build_research_pair_row(
        pair_id="C0042878-C0043031",
        sentences=fake_sentence_dict["C0042878-C0043031"],
        paper_meta=fake_paper_metadata,
        cui_to_canonical=cui_to_canonical,
        cui_metadata=fake_cui_metadata,
        max_sentences=3,
    )
    assert row is not None
    assert set(row.keys()) >= {
        "cui_a",
        "cui_b",
        "canonical_id_a",
        "canonical_id_b",
        "ent_type_a",
        "ent_type_b",
        "display_name_a",
        "display_name_b",
        "paper_count",
        "top_sentences",
        "top_pmids",
        "top_papers",
    }


def test_build_research_pair_row_sorts_cuis(
    fake_sentence_dict,
    fake_paper_metadata,
    fake_iqm,
    fake_cui_metadata,
):
    cui_to_canonical = ing.build_cui_to_canonical_index(fake_iqm)
    row = ing.build_research_pair_row(
        pair_id="C0043031-C0042878",  # reversed input
        sentences=fake_sentence_dict["C0042878-C0043031"],
        paper_meta=fake_paper_metadata,
        cui_to_canonical=cui_to_canonical,
        cui_metadata=fake_cui_metadata,
        max_sentences=3,
    )
    assert row["cui_a"] < row["cui_b"]
    assert row["cui_a"] == "C0042878"
    assert row["cui_b"] == "C0043031"


def test_build_research_pair_row_resolves_canonical_id(
    fake_sentence_dict,
    fake_paper_metadata,
    fake_iqm,
    fake_cui_metadata,
):
    cui_to_canonical = ing.build_cui_to_canonical_index(fake_iqm)
    row = ing.build_research_pair_row(
        pair_id="C0042878-C0043031",
        sentences=fake_sentence_dict["C0042878-C0043031"],
        paper_meta=fake_paper_metadata,
        cui_to_canonical=cui_to_canonical,
        cui_metadata=fake_cui_metadata,
        max_sentences=3,
    )
    assert row["canonical_id_a"] == "vitamin_k"
    assert row["canonical_id_b"] is None  # warfarin is a drug, no IQM mapping


def test_build_research_pair_row_counts_unique_papers(
    fake_sentence_dict,
    fake_paper_metadata,
    fake_iqm,
    fake_cui_metadata,
):
    cui_to_canonical = ing.build_cui_to_canonical_index(fake_iqm)
    row = ing.build_research_pair_row(
        pair_id="C0042878-C0043031",
        sentences=fake_sentence_dict["C0042878-C0043031"],
        paper_meta=fake_paper_metadata,
        cui_to_canonical=cui_to_canonical,
        cui_metadata=fake_cui_metadata,
        max_sentences=3,
    )
    # 5 sentences but 1 is retracted → paper_count = 4 unique non-retracted
    assert row["paper_count"] == 4


def test_build_research_pair_row_drops_retraction_sentences(
    fake_sentence_dict,
    fake_paper_metadata,
    fake_iqm,
    fake_cui_metadata,
):
    cui_to_canonical = ing.build_cui_to_canonical_index(fake_iqm)
    row = ing.build_research_pair_row(
        pair_id="C0042878-C0043031",
        sentences=fake_sentence_dict["C0042878-C0043031"],
        paper_meta=fake_paper_metadata,
        cui_to_canonical=cui_to_canonical,
        cui_metadata=fake_cui_metadata,
        max_sentences=5,
    )
    pmids_in_output = {s["pmid"] for s in row["top_sentences"]}
    assert "99999999" not in pmids_in_output


# --------------------------------------------------------------------------- #
# Curated auto-enrichment
# --------------------------------------------------------------------------- #


def test_enrich_curated_with_suppai_appends_pmids():
    research_pairs = [
        {
            "cui_a": "C0042878",
            "cui_b": "C0043031",
            "top_pmids": ["28458697", "12345678"],
        }
    ]
    curated = [
        {
            "id": "DDI_WAR_VITK",
            "agent1_id": "11289",
            "agent2_id": "C0042878",
            "source_pmids": [],
        }
    ]
    # warfarin rxcui 11289 maps to supp.ai CUI C0043031
    rxcui_to_cui = {"11289": "C0043031"}
    enriched = ing.enrich_curated_with_suppai(curated, research_pairs, rxcui_to_cui)
    assert "28458697" in enriched[0]["source_pmids"]
    assert "12345678" in enriched[0]["source_pmids"]


def test_enrich_curated_with_suppai_deduplicates_pmids():
    research_pairs = [
        {"cui_a": "C0042878", "cui_b": "C0043031", "top_pmids": ["28458697"]}
    ]
    curated = [
        {
            "id": "DDI_WAR_VITK",
            "agent1_id": "11289",
            "agent2_id": "C0042878",
            "source_pmids": ["28458697"],
        }
    ]
    rxcui_to_cui = {"11289": "C0043031"}
    enriched = ing.enrich_curated_with_suppai(curated, research_pairs, rxcui_to_cui)
    assert enriched[0]["source_pmids"].count("28458697") == 1


def test_enrich_curated_with_suppai_leaves_unmatched_alone():
    research_pairs = [
        {"cui_a": "C0001111", "cui_b": "C0002222", "top_pmids": ["99998888"]}
    ]
    curated = [
        {
            "id": "DDI_SOMETHING",
            "agent1_id": "6448",
            "agent2_id": "C0042878",
            "source_pmids": ["111"],
        }
    ]
    rxcui_to_cui = {"6448": "C0043031"}
    enriched = ing.enrich_curated_with_suppai(curated, research_pairs, rxcui_to_cui)
    assert enriched[0]["source_pmids"] == ["111"]


# --------------------------------------------------------------------------- #
# Full pipeline smoke test with fake dump on disk
# --------------------------------------------------------------------------- #


def _write_fake_dump(
    dump_dir: Path,
    cui_metadata: dict,
    sentence_dict: dict,
    paper_metadata: dict,
) -> None:
    dump_dir.mkdir(parents=True, exist_ok=True)
    (dump_dir / "meta.json").write_text(
        json.dumps({"last_updated_on": "2021-10-20T16:45:43Z"})
    )
    (dump_dir / "cui_metadata.json").write_text(json.dumps(cui_metadata))
    (dump_dir / "sentence_dict.json").write_text(json.dumps(sentence_dict))
    (dump_dir / "paper_metadata.json").write_text(json.dumps(paper_metadata))
    # interaction_id_dict isn't actually needed by the ingest pipeline but the
    # real dump ships it, so mirror the shape for future-proofing.
    iid: dict[str, list[str]] = {}
    for pair_id in sentence_dict:
        a, b = pair_id.split("-")
        iid.setdefault(a, []).append(pair_id)
        iid.setdefault(b, []).append(pair_id)
    (dump_dir / "interaction_id_dict.json").write_text(json.dumps(iid))


def test_run_ingest_end_to_end(
    tmp_path,
    fake_iqm,
    fake_drug_classes,
    fake_cui_metadata,
    fake_sentence_dict,
    fake_paper_metadata,
):
    dump_dir = tmp_path / "dump"
    _write_fake_dump(
        dump_dir, fake_cui_metadata, fake_sentence_dict, fake_paper_metadata
    )

    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps(fake_iqm))
    dc_path = tmp_path / "drug_classes.json"
    dc_path.write_text(json.dumps(fake_drug_classes))

    output_path = tmp_path / "research_pairs.json"
    report_path = tmp_path / "report.json"

    rc = ing.main(
        [
            "--suppai-dir",
            str(dump_dir),
            "--iqm",
            str(iqm_path),
            "--drug-classes",
            str(dc_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--max-sentences-per-pair",
            "3",
        ]
    )
    assert rc == 0, f"ingest_suppai exited {rc}"
    assert output_path.exists()
    payload = json.loads(output_path.read_text())
    rows = payload["research_pairs"]

    # Only the 2 anchored pairs should survive. Unanchored pair dropped.
    assert len(rows) == 2
    pair_keys = {(r["cui_a"], r["cui_b"]) for r in rows}
    assert ("C0042878", "C0043031") in pair_keys
    assert ("C0016157", "C0043031") in pair_keys
    # Each row has ≤3 sentences
    for r in rows:
        assert len(r["top_sentences"]) <= 3


def test_run_ingest_writes_metadata_block(
    tmp_path,
    fake_iqm,
    fake_drug_classes,
    fake_cui_metadata,
    fake_sentence_dict,
    fake_paper_metadata,
):
    dump_dir = tmp_path / "dump"
    _write_fake_dump(
        dump_dir, fake_cui_metadata, fake_sentence_dict, fake_paper_metadata
    )
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps(fake_iqm))
    dc_path = tmp_path / "drug_classes.json"
    dc_path.write_text(json.dumps(fake_drug_classes))
    output_path = tmp_path / "research_pairs.json"
    report_path = tmp_path / "report.json"
    rc = ing.main(
        [
            "--suppai-dir",
            str(dump_dir),
            "--iqm",
            str(iqm_path),
            "--drug-classes",
            str(dc_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--max-sentences-per-pair",
            "3",
            "--build-time",
            "2026-04-11T00:00:00Z",
        ]
    )
    assert rc == 0
    payload = json.loads(output_path.read_text())
    meta = payload["_metadata"]
    assert meta["schema_version"] == "1.0.0"
    assert meta["source"] == "supp.ai"
    assert meta["last_updated"] == "2026-04-11T00:00:00Z"
    assert meta["total_pairs"] == len(payload["research_pairs"])


def test_run_ingest_deterministic_row_order(
    tmp_path,
    fake_iqm,
    fake_drug_classes,
    fake_cui_metadata,
    fake_sentence_dict,
    fake_paper_metadata,
):
    """Two identical runs must produce identical JSON bytes."""
    dump_dir = tmp_path / "dump"
    _write_fake_dump(
        dump_dir, fake_cui_metadata, fake_sentence_dict, fake_paper_metadata
    )
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps(fake_iqm))
    dc_path = tmp_path / "drug_classes.json"
    dc_path.write_text(json.dumps(fake_drug_classes))

    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    rep = tmp_path / "rep.json"
    argv = [
        "--suppai-dir",
        str(dump_dir),
        "--iqm",
        str(iqm_path),
        "--drug-classes",
        str(dc_path),
        "--report",
        str(rep),
        "--max-sentences-per-pair",
        "3",
        "--build-time",
        "2026-04-11T00:00:00Z",
    ]
    assert ing.main(argv + ["--output", str(out_a)]) == 0
    assert ing.main(argv + ["--output", str(out_b)]) == 0
    assert out_a.read_bytes() == out_b.read_bytes(), (
        "ingest_suppai must produce byte-identical output for identical input"
    )


def test_run_ingest_dry_run_does_not_write(
    tmp_path,
    fake_iqm,
    fake_drug_classes,
    fake_cui_metadata,
    fake_sentence_dict,
    fake_paper_metadata,
):
    dump_dir = tmp_path / "dump"
    _write_fake_dump(
        dump_dir, fake_cui_metadata, fake_sentence_dict, fake_paper_metadata
    )
    iqm_path = tmp_path / "iqm.json"
    iqm_path.write_text(json.dumps(fake_iqm))
    dc_path = tmp_path / "drug_classes.json"
    dc_path.write_text(json.dumps(fake_drug_classes))

    out = tmp_path / "nope.json"
    rep = tmp_path / "rep.json"
    rc = ing.main(
        [
            "--suppai-dir",
            str(dump_dir),
            "--iqm",
            str(iqm_path),
            "--drug-classes",
            str(dc_path),
            "--output",
            str(out),
            "--report",
            str(rep),
            "--dry-run",
        ]
    )
    assert rc == 0
    assert not out.exists(), "dry-run must not write output file"
