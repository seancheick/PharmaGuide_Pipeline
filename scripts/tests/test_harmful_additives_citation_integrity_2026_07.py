"""Regression locks for harmful_additives ghost-citation cleanup.

Identifiers in clinical-facing safety data must be content-verified. These
tests pin the July 2026 cleanup of broken/wrong-topic DOI references and the
mislabelled TBHQ PMC citation.
"""
import json
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "harmful_additives.json"


def _entries_by_id():
    data = json.loads(DATA_PATH.read_text())
    return {entry["id"]: entry for entry in data["harmful_additives"]}


def _entry_text(entry):
    return json.dumps(entry, sort_keys=True)


def test_dead_or_wrong_topic_harmful_additive_dois_are_removed():
    entries = _entries_by_id()
    combined = "\n".join(_entry_text(entries[eid]) for eid in (
        "ADD_ACESULFAME_K",
        "ADD_BHT",
        "ADD_SYNTHETIC_ANTIOXIDANTS",
        "ADD_TBHQ",
    ))

    assert "10.1002/tcp.10162" not in combined
    assert "10.1080/10408398.2019.1629524" not in combined
    assert "10.1016/j.fct.2005.05.012" not in combined


def test_harmful_additive_replacement_dois_are_content_specific():
    entries = _entries_by_id()

    bht = _entry_text(entries["ADD_BHT"])
    synthetic = _entry_text(entries["ADD_SYNTHETIC_ANTIOXIDANTS"])
    ace_k = _entry_text(entries["ADD_ACESULFAME_K"])
    tbhq = _entry_text(entries["ADD_TBHQ"])

    assert "10.1016/S0278-6915(99)00085-X" in bht
    assert "Safety Assessment of Butylated Hydroxyanisole and Butylated Hydroxytoluene" in bht
    assert "10.1016/S0278-6915(99)00085-X" in synthetic

    assert "10.1016/j.fct.2020.111375" in ace_k
    assert "Lack of potential carcinogenicity for acesulfame potassium" in ace_k

    assert "10.1016/0278-6915(86)90289-9" in tbhq
    assert "Toxicology of tert-butylhydroquinone (TBHQ)" in tbhq
    assert "10.1016/j.fct.2020.111595" in tbhq
    assert "Nrf2-dependent and -independent effects of tBHQ" in tbhq


def test_tbhq_pmc9147452_is_not_mislabelled_as_frontiers():
    tbhq = _entry_text(_entries_by_id()["ADD_TBHQ"])

    assert "PMC9147452" in tbhq
    assert "Life (Basel) 2022" in tbhq
    assert "Frontiers in Immunology" not in tbhq
