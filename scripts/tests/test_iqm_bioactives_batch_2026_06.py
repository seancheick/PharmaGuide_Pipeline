"""Verified-identity IQM additions for 3 unmapped bioactives (2026-06).

Surfaced by the BulkSupplements unmapped triage. Identities content-verified
against live PubChem/PubMed on 2026-06-22 (no IDs from memory):

  - L-Ornithine L-Aspartate (LOLA): CID 10220941, CAS 3230-94-2; oral F ~82%
    (Kircheis & Lüth 2019, PMID:30706424, "Pharmacokinetic and Pharmacodynamic
    Properties of L-Ornithine L-Aspartate (LOLA)…", Drugs 2019). Registered drug.
    -> form under l_ornithine, bio 13 (premium salt, well-absorbed).
  - N-Acetyl-L-Carnosine (NAC): CID 9903482, CAS 56353-15-2. Predominantly a
    TOPICAL ophthalmic agent; human oral systemic bioavailability as intact
    carnosine is not established. -> form under l_carnosine, conservative bio 6.
  - Creatinol O-Phosphate (COP): CID 23342, CAS 6903-79-3. Real compound but ~0
    indexed modern oral PK/clinical studies. -> new parent, conservative bio 5.

Conservative scores for NAC/COP are deliberate: under-crediting an unproven-oral
compound is the safe error. Notes state the evidence limitation, no ghost PMIDs.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _resolve(enricher, label):
    product = {
        "activeIngredients": [{"name": label, "quantity": 500, "unit": "mg"}],
        "inactiveIngredients": [],
    }
    data = enricher._collect_ingredient_quality_data(product)
    scorable = data.get("ingredients_scorable") or []
    assert scorable, f"{label!r} did not resolve to a scorable ingredient"
    row = scorable[0]
    return row.get("standard_name"), row.get("bio_score"), row.get("matched_form")


@pytest.mark.parametrize(
    "label,std,bio,form",
    [
        ("L-Ornithine L-Aspartate", "L-Ornithine", 13.0, "l-ornithine l-aspartate (lola)"),
        ("Ornithine Aspartate", "L-Ornithine", 13.0, "l-ornithine l-aspartate (lola)"),
        ("N-Acetyl L-Carnosine", "L-Carnosine", 6.0, "n-acetyl-l-carnosine"),
        ("N-Acetyl-L-Carnosine", "L-Carnosine", 6.0, "n-acetyl-l-carnosine"),
        ("Creatinol O-Phosphate", "Creatinol O-Phosphate", 5.0, "creatinol o-phosphate (unspecified)"),
    ],
)
def test_bioactive_resolves_to_verified_identity_and_form(enricher, label, std, bio, form):
    got_std, got_bio, got_form = _resolve(enricher, label)
    assert got_std == std
    assert got_bio == bio
    assert got_form == form


def test_lola_premium_over_free_ornithine(enricher):
    # Free ornithine keeps its own form/score; LOLA is the better-absorbed salt.
    assert _resolve(enricher, "L-Ornithine")[1] == 11.0
    assert _resolve(enricher, "L-Ornithine L-Aspartate")[1] == 13.0


@pytest.mark.parametrize(
    "parent,form,cid,cas",
    [
        ("l_ornithine", "l-ornithine l-aspartate (lola)", "10220941", "3230-94-2"),
        ("l_carnosine", "n-acetyl-l-carnosine", "9903482", "56353-15-2"),
        ("creatinol_o_phosphate", "creatinol o-phosphate (unspecified)", "23342", "6903-79-3"),
    ],
)
def test_verified_external_ids_present(iqm, parent, form, cid, cas):
    # Lock the live-verified PubChem CID + CAS so they cannot be silently altered.
    ext = iqm[parent]["forms"][form].get("external_ids", {})
    assert ext.get("pubchem_cid") == cid
    assert ext.get("cas") == cas
