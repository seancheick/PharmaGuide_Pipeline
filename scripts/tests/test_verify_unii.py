#!/usr/bin/env python3
"""Tests for GSRS/UNII verification safety and persistence."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _substance(
    *,
    name="Curcumin",
    unii="IT942ZTH98",
    cas="458-37-7",
    rxcui="2955",
    dsld="310 products",
    cfr=None,
    relationships=None,
):
    codes = []
    if cas is not None:
        codes.append({"codeSystem": "CAS", "code": cas})
    if rxcui is not None:
        codes.append({"codeSystem": "RXCUI", "code": rxcui})
    if dsld is not None:
        codes.append({"codeSystem": "DSLD", "code": "", "comments": dsld})
    for section in cfr or []:
        codes.append({"codeSystem": "CFR", "code": section})
    return {
        "_name": name,
        "approvalID": unii,
        "substanceClass": "chemical",
        "codes": codes,
        "names": [{"name": name}],
        "relationships": relationships or [],
    }


def test_verify_flat_file_rejects_cas_mismatch_and_does_not_apply():
    from api_audit.verify_unii import verify_flat_file

    class FakeClient:
        def search_substance(self, name, cas=None):
            assert name == "Curcumin"
            assert cas == "458-37-7"
            return _substance(cas="111-11-1")

    entry = {
        "id": "ADD_CURCUMIN",
        "standard_name": "Curcumin",
        "external_ids": {"cas": "458-37-7"},
    }
    data = {"harmful_additives": [entry]}

    report = verify_flat_file(data, "harmful_additives", FakeClient(), apply=True)

    assert report["filled"] == []
    assert len(report["rejected"]) == 1
    assert "CAS mismatch" in report["rejected"][0]["reason"]
    assert entry["external_ids"] == {"cas": "458-37-7"}
    assert "gsrs" not in entry


def test_verify_iqm_file_rejects_alias_match_when_form_cas_conflicts():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, name, cas=None):
            if cas:
                return None
            if name == "passiflora incarnata":
                return _substance(name="Passiflora incarnata", cas="999-99-9", unii="ABC123")
            return None

    data = {
        "_metadata": {},
        "passionflower": {
            "standard_name": "Passionflower",
            "forms": {
                "standardized extract": {
                    "external_ids": {"cas": "8057-62-3"},
                    "aliases": ["passiflora incarnata"],
                }
            },
        },
    }

    report = verify_iqm_file(data, FakeClient(), apply=True)

    assert report["filled"] == []
    assert len(report["rejected"]) == 1
    assert "CAS mismatch" in report["rejected"][0]["reason"]
    assert data["passionflower"].get("external_ids") is None


def test_verify_flat_file_validates_existing_unii_before_marking_verified():
    from api_audit.verify_unii import verify_flat_file

    class FakeClient:
        def get_full_substance(self, unii):
            assert unii == "WRONG123"
            return _substance(name="Completely Different Substance", unii=unii, cas="999-99-9")

        def search_substance(self, name, cas=None):
            raise AssertionError("existing UNII path should not trigger search")

    data = {
        "harmful_additives": [
            {
                "id": "ADD_CURCUMIN",
                "standard_name": "Curcumin",
                "external_ids": {"cas": "458-37-7", "unii": "WRONG123"},
            }
        ]
    }

    report = verify_flat_file(data, "harmful_additives", FakeClient(), apply=False)

    assert report["verified"] == []
    assert len(report["rejected"]) == 1
    assert report["rejected"][0]["id"] == "ADD_CURCUMIN"
    assert "mismatch" in report["rejected"][0]["reason"].lower()


def test_verify_flat_file_apply_persists_gsrs_enrichment_and_rxcui():
    from api_audit.verify_unii import verify_flat_file

    relationships = [
        {
            "type": "ACTIVE MOIETY",
            "relatedSubstance": {"name": "Stearic Acid", "approvalID": "XYZ0001"},
        },
        {
            "type": "PARENT->SALT/SOLVATE",
            "relatedSubstance": {"name": "Magnesium Stearate Monohydrate", "approvalID": "XYZ0002"},
        },
        {
            "type": "METABOLIC ENZYME->INHIBITOR",
            "relatedSubstance": {"name": "MRP-1 inhibitor", "approvalID": "XYZ0003"},
        },
        {
            "type": "PARENT->METABOLITE ACTIVE",
            "relatedSubstance": {"name": "Curcumin glucuronide", "approvalID": "XYZ0004"},
        },
    ]

    class FakeClient:
        def search_substance(self, name, cas=None):
            return _substance(
                name="Curcumin",
                cas="458-37-7",
                unii="IT942ZTH98",
                rxcui="2955",
                dsld="310 products",
                cfr=["21 CFR 182.10"],
                relationships=relationships,
            )

    entry = {
        "id": "ADD_CURCUMIN",
        "standard_name": "Curcumin",
        "external_ids": {"cas": "458-37-7"},
        "rxcui": None,
        "rxcui_note": "No RxNorm concept for supplement ingredient",
    }

    report = verify_flat_file({"harmful_additives": [entry]}, "harmful_additives", FakeClient(), apply=True)

    assert report["changes_applied"] == 1
    assert entry["external_ids"]["unii"] == "IT942ZTH98"
    assert entry.get("rxcui") == "2955"
    assert entry.get("rxcui_note") is None
    assert entry["gsrs"]["cfr_sections"] == ["21 CFR 182.10"]
    assert entry["gsrs"]["dsld_count"] == 310
    assert entry["gsrs"]["dsld_info_raw"] == "310 products"
    assert entry["gsrs"]["active_moiety"]["name"] == "Stearic Acid"
    assert entry["gsrs"]["salt_parents"][0]["name"] == "Magnesium Stearate Monohydrate"
    assert entry["gsrs"]["metabolic_relationships"][0]["name"] == "MRP-1 inhibitor"
    assert entry["gsrs"]["metabolites"][0]["name"] == "Curcumin glucuronide"


def test_verify_iqm_apply_enriches_existing_unii_record():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def get_full_substance(self, unii):
            return _substance(name="Vitamin A", unii=unii, cas="68-26-8", rxcui="11149", dsld=None)

        def search_substance(self, name, cas=None):
            raise AssertionError("existing UNII should be resolved directly")

    data = {
        "_metadata": {},
        "vitamin_a": {
            "standard_name": "Vitamin A",
            "external_ids": {"unii": "UNII123"},
            "rxcui": None,
            "rxcui_note": "No RxNorm concept for supplement ingredient",
            "forms": {
                "retinol": {
                    "external_ids": {"cas": "68-26-8"},
                    "aliases": ["retinol"],
                }
            },
        },
    }

    report = verify_iqm_file(data, FakeClient(), apply=True)

    assert len(report["verified"]) == 1
    assert report["changes_applied"] == 1
    assert data["vitamin_a"].get("rxcui") == "11149"
    assert data["vitamin_a"].get("rxcui_note") is None
    assert data["vitamin_a"]["gsrs"]["substance_name"] == "Vitamin A"


def test_verify_flat_file_accepts_match_when_local_cas_is_present_in_gsrs_superseded_codes():
    from api_audit.verify_unii import verify_flat_file

    substance = _substance(name="Potassium Sorbate", cas=None, unii="1VPU26JZZ4", rxcui="8606")
    substance["codes"].extend([
        {"codeSystem": "CAS", "code": "24634-61-5", "type": "PRIMARY"},
        {"codeSystem": "CAS", "code": "590-00-1", "type": "SUPERSEDED"},
        {
            "codeSystem": "DSLD",
            "code": "1192 (Number of products:26)",
            "comments": "Dietary Supplement Label Database|Chemical|Potassium sorbate",
        },
    ])

    class FakeClient:
        def search_substance(self, name, cas=None):
            assert name == "Potassium Sorbate"
            assert cas == "24634-61-5"
            return substance

    entry = {
        "id": "ADD_POTASSIUM_SORBATE",
        "standard_name": "Potassium Sorbate",
        "external_ids": {"cas": "24634-61-5"},
    }

    report = verify_flat_file({"harmful_additives": [entry]}, "harmful_additives", FakeClient(), apply=True)

    assert report["rejected"] == []
    assert report["changes_applied"] == 1
    assert entry["external_ids"]["unii"] == "1VPU26JZZ4"
    assert entry["gsrs"]["dsld_count"] == 26


def test_verify_flat_file_reports_curated_governed_null_without_lookup():
    from api_audit.verify_unii import verify_flat_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("governed-null GSRS entry should not hit live lookup")

    report = verify_flat_file(
        {
            "harmful_additives": [
                {
                    "id": "ADD_CANDURIN_SILVER",
                    "standard_name": "Candurin Silver",
                    "external_ids": {"cas": "12001-26-2"},
                }
            ]
        },
        "harmful_additives",
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "id": "ADD_CANDURIN_SILVER",
            "name": "Candurin Silver",
            "reason": "proprietary mica-based pearlescent pigment system; GSRS resolves to component materials rather than one exact ingredient identity",
        }
    ]


def test_verify_flat_file_accepts_botanical_alias_match():
    from api_audit.verify_unii import verify_flat_file

    substance = _substance(name="BRASSICA RAPA SUBSP. OLEIFERA OIL", unii="N4G8379626", cas="8002-13-9", rxcui="1306155")
    substance["substanceClass"] = "structurallyDiverse"
    substance["names"].append({"name": "Brassica rapa subsp. oleifera oil"})

    class FakeClient:
        def search_substance(self, name, cas=None):
            assert name == "Canola Oil (Refined)"
            assert cas == "8002-13-9"
            return substance

    entry = {
        "id": "ADD_CANOLA_OIL",
        "standard_name": "Canola Oil (Refined)",
        "aliases": ["Brassica rapa subsp. oleifera oil"],
        "external_ids": {"cas": "8002-13-9"},
    }

    report = verify_flat_file({"harmful_additives": [entry]}, "harmful_additives", FakeClient(), apply=True)

    assert report["rejected"] == []
    assert report["governed_null"] == []
    assert report["changes_applied"] == 1
    assert entry["external_ids"]["unii"] == "N4G8379626"


def test_verify_flat_file_rejects_leaf_oil_match_for_generic_citrus_bergamot():
    from api_audit.verify_unii import verify_flat_file

    substance = _substance(
        name="CITRUS BERGAMIA LEAF OIL",
        unii="ZVY8741I1V",
        cas=None,
        rxcui="2264903",
    )
    substance["substanceClass"] = "structurallyDiverse"
    substance["names"].append({"name": "Citrus bergamia leaf oil"})

    class FakeClient:
        def get_full_substance(self, unii):
            assert unii == "ZVY8741I1V"
            return substance

        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("existing UNII should be resolved directly")

    entry = {
        "id": "BOT_CITRUS_BERGAMOT",
        "standard_name": "Citrus Bergamot",
        "aliases": ["Citrus bergamia"],
        "external_ids": {"unii": "ZVY8741I1V"},
        "rxcui": "2264903",
        "gsrs": {"substance_name": "CITRUS BERGAMIA LEAF OIL"},
        "latin_name": "Citrus bergamia",
    }

    report = verify_flat_file({"botanical_ingredients": [entry]}, "botanical_ingredients", FakeClient(), apply=True)

    assert report["verified"] == []
    assert len(report["rejected"]) == 1
    assert "name mismatch" in report["rejected"][0]["reason"].lower()
    assert entry["external_ids"] == {}
    assert entry.get("rxcui") is None
    assert entry.get("gsrs") is None


def test_verify_flat_file_governs_product_recall_entry_without_lookup():
    from api_audit.verify_unii import verify_flat_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("product recall entries should not hit GSRS as single-ingredient records")

    report = verify_flat_file(
        {
            "ingredients": [
                {
                    "id": "RECALLED_HYDROXYCUT",
                    "standard_name": "Hydroxycut (Multiple Formulations)",
                    "entity_type": "product",
                    "cui": None,
                    "cui_status": "no_single_umls_concept",
                    "cui_note": "Product recall record is intentionally null-CUI because one ingredient concept would misrepresent the recalled brand/formulation family.",
                }
            ]
        },
        "ingredients",
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "id": "RECALLED_HYDROXYCUT",
            "name": "Hydroxycut (Multiple Formulations)",
            "reason": "Product recall record is intentionally null-CUI because one ingredient concept would misrepresent the recalled brand/formulation family.",
        }
    ]


def test_verify_flat_file_reports_hexavalent_chromium_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_flat_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("Cr(VI) class entry should not hit GSRS as one exact substance")

    report = verify_flat_file(
        {
            "ingredients": [
                {
                    "id": "HM_CHROMIUM_HEXAVALENT",
                    "standard_name": "Chromium (VI) — Hexavalent Chromium",
                    "entity_type": "contaminant",
                    "external_ids": {},
                }
            ]
        },
        "ingredients",
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "id": "HM_CHROMIUM_HEXAVALENT",
            "name": "Chromium (VI) — Hexavalent Chromium",
            "reason": "Cr(VI) entry spans multiple hazardous chromium compounds; keep UNII null unless the record is split into a specific compound such as chromium trioxide or sodium dichromate.",
        }
    ]


def test_verify_iqm_file_reports_vitamin_k_parent_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("generic vitamin K parent should not hit GSRS as one exact substance")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("generic vitamin K parent should not hit GSRS as one exact substance")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "vitamin_k": {
                "standard_name": "Vitamin K",
                "category": "vitamins",
                "cui": "C0042878",
                "forms": {
                    "phylloquinone (K1)": {"aliases": ["vitamin k1"]},
                    "menaquinone-7 (MK-7)": {"aliases": ["vitamin k2 mk7"]},
                },
                "aliases": ["K2 Vital Delta"],
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "vitamin_k",
            "name": "Vitamin K",
            "reason": "generic vitamin K entry spans K1 (phytonadione) and K2 menaquinones; keep UNII null unless the record is split to a specific vitamer.",
        }
    ]


def test_verify_iqm_file_reports_phosphatidylinositol_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("phosphatidylinositol class entry should not hit GSRS as one exact substance")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("phosphatidylinositol class entry should not hit GSRS as one exact substance")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "phosphatidylinositol": {
                "standard_name": "Phosphatidylinositol",
                "category": "fatty_acids",
                "cui": "C0031621",
                "forms": {
                    "phosphatidylinositol standard": {
                        "aliases": ["phosphoinositides"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "phosphatidylinositol",
            "name": "Phosphatidylinositol",
            "reason": "generic phosphatidylinositol entry spans multiple lipid molecular species; keep UNII null unless the record is split to a specific phosphatidylinositol molecule.",
        }
    ]


def test_verify_iqm_file_reports_flower_pollen_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("generic flower pollen entry should not hit GSRS as one exact botanical source")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("generic flower pollen entry should not hit GSRS as one exact botanical source")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "flower_pollen": {
                "standard_name": "Flower Pollen Extract",
                "category": "herbs",
                "cui": "C4073752",
                "forms": {
                    "flower pollen extract": {
                        "aliases": ["flower pollen", "pollen extract"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "flower_pollen",
            "name": "Flower Pollen Extract",
            "reason": "generic flower pollen extract entry spans mixed or unspecified botanical pollen sources; keep UNII null unless the record is split to a specific source such as Secale cereale pollen.",
        }
    ]


def test_verify_iqm_file_reports_hawthorn_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("generic hawthorn entry should not hit GSRS as one exact botanical or constituent")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("generic hawthorn entry should not hit GSRS as one exact botanical or constituent")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "hawthorn": {
                "standard_name": "Hawthorn (Crataegus)",
                "category": "herbs",
                "cui": "C0885252",
                "forms": {
                    "hawthorn (unspecified)": {
                        "aliases": ["hawthorn", "crataegus"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "hawthorn",
            "name": "Hawthorn (Crataegus)",
            "reason": "generic hawthorn entry spans berry, leaf, flower, and extract forms; keep UNII null unless the record is split to a specific botanical part or constituent.",
        }
    ]


def test_verify_iqm_file_reports_ganoderic_acids_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("ganoderic acids entry should not hit GSRS as reishi")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("ganoderic acids entry should not hit GSRS as reishi")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "ganoderic_acids": {
                "standard_name": "Ganoderic Acids",
                "category": "herbs",
                "cui": "C3180310",
                "forms": {
                    "ganoderic acids (unspecified)": {
                        "aliases": ["ganoderic acids", "reishi triterpenes"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "ganoderic_acids",
            "name": "Ganoderic Acids",
            "reason": "ganoderic acids entry spans multiple reishi triterpenoid constituents; keep UNII null unless the record is split to a specific ganoderic acid molecule.",
        }
    ]


def test_verify_iqm_file_reports_glucosinolates_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("glucosinolates entry should not hit GSRS as broccoli")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("glucosinolates entry should not hit GSRS as broccoli")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "glucosinolates": {
                "standard_name": "Glucosinolates",
                "category": "antioxidants",
                "cui": "C0017767",
                "forms": {
                    "glucosinolates (unspecified)": {
                        "aliases": ["glucosinolates", "broccoli glucosinolates"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "glucosinolates",
            "name": "Glucosinolates",
            "reason": "glucosinolates entry spans many crucifer-derived precursor compounds; keep UNII null unless the record is split to a specific glucosinolate such as glucoraphanin.",
        }
    ]


def test_verify_iqm_file_reports_isothiocyanates_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("isothiocyanates entry should not hit GSRS as broccoli")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("isothiocyanates entry should not hit GSRS as broccoli")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "isothiocyanates": {
                "standard_name": "Isothiocyanates",
                "category": "antioxidants",
                "cui": "C0206359",
                "forms": {
                    "isothiocyanates (unspecified)": {
                        "aliases": ["isothiocyanates", "broccoli isothiocyanates"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "isothiocyanates",
            "name": "Isothiocyanates",
            "reason": "isothiocyanates entry spans many reactive glucosinolate-derived products; keep UNII null unless the record is split to a specific isothiocyanate such as sulforaphane or PEITC.",
        }
    ]


def test_verify_iqm_file_reports_bioflavonoids_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("generic bioflavonoids entry should not hit GSRS as citrus bioflavonoids")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("generic bioflavonoids entry should not hit GSRS as citrus bioflavonoids")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "bioflavonoids": {
                "standard_name": "Bioflavonoids",
                "category": "antioxidants",
                "cui": "C0005492",
                "forms": {
                    "unspecified": {
                        "aliases": ["bioflavonoids"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "bioflavonoids",
            "name": "Bioflavonoids",
            "reason": "generic bioflavonoids entry spans multiple flavonoid families and plant sources; keep UNII null unless the record is split to a specific source such as citrus bioflavonoids.",
        }
    ]


def test_verify_iqm_file_reports_saccharomyces_boulardii_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("saccharomyces boulardii entry should not hit GSRS as generic brewer's yeast")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("saccharomyces boulardii entry should not hit GSRS as generic brewer's yeast")

    report = verify_iqm_file(
        {
            "_metadata": {},
            "saccharomyces_boulardii": {
                "standard_name": "Saccharomyces Boulardii",
                "category": "probiotics",
                "cui": "C0772093",
                "forms": {
                    "saccharomyces boulardii (unspecified)": {
                        "aliases": ["saccharomyces boulardii", "S. cerevisiae var. boulardii"],
                    }
                },
            },
        },
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "key": "saccharomyces_boulardii",
            "name": "Saccharomyces Boulardii",
            "reason": "GSRS collapses Saccharomyces boulardii to generic Saccharomyces cerevisiae / brewer's yeast; keep UNII null unless a reviewed exact probiotic strain identity is available.",
        }
    ]


def test_verify_flat_file_reports_florastor_as_governed_null_without_lookup():
    from api_audit.verify_unii import verify_flat_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("Florastor brand row should not hit GSRS as generic brewer's yeast")

        def get_full_substance(self, *_args, **_kwargs):
            raise AssertionError("Florastor brand row should not hit GSRS as generic brewer's yeast")

    report = verify_flat_file(
        {
            "backed_clinical_studies": [
                {
                    "id": "BRAND_FLORASTOR",
                    "standard_name": "Florastor",
                    "external_ids": {},
                }
            ]
        },
        "backed_clinical_studies",
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "id": "BRAND_FLORASTOR",
            "name": "Florastor",
            "reason": "brand row maps to Saccharomyces boulardii CNCM I-745 literature, not to one reviewed GSRS substance identity; keep UNII null.",
        }
    ]


def test_collect_iqm_search_terms_prioritizes_top_level_and_form_aliases():
    from api_audit.verify_unii import _collect_iqm_search_terms

    entry = {
        "aliases": ["black elderberry", "elderberry fruit extract"],
        "forms": {
            "extract": {
                "aliases": ["elderberry", "sambucol"],
            }
        },
    }

    terms = _collect_iqm_search_terms(entry, "elderberry")

    assert terms[0] == "elderberry"
    assert "elderberry fruit extract" in terms
    assert "sambucol" in terms


def test_verify_iqm_file_reports_alpha_gpc_as_governed_null_before_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, name, cas=None):
            raise AssertionError("alpha gpc should be governed-null before GSRS lookup")

    data = {
        "_metadata": {},
        "alpha_gpc": {
            "standard_name": "Alpha GPC",
            "forms": {
                "standard": {
                    "aliases": [
                        "Alpha GPC",
                        "alpha-glyceryl phosphoryl choline",
                        "choline alfoscerate",
                    ],
                }
            },
        },
    }

    report = verify_iqm_file(data, FakeClient(), apply=True)

    assert report["not_found"] == []
    assert report["filled"] == []
    assert report["rejected"] == []
    assert report["governed_null"] == [
        {
            "key": "alpha_gpc",
            "name": "Alpha GPC",
            "reason": "current GSRS search collapses Alpha GPC to choline-related records rather than one reviewed exact alpha-glycerophosphocholine substance identity",
        }
    ]


def test_verify_iqm_file_reports_alpha_gpc_as_governed_null_even_if_alias_would_match():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, name, cas=None):
            raise AssertionError("alpha gpc should be governed-null before GSRS lookup")

    data = {
        "_metadata": {},
        "alpha_gpc": {
            "standard_name": "Alpha GPC",
            "forms": {
                "standard": {
                    "aliases": [
                        "Alpha GPC",
                        "choline alfoscerate",
                    ],
                }
            },
        },
    }

    report = verify_iqm_file(data, FakeClient(), apply=True)

    assert report["filled"] == []
    assert report["verified"] == []
    assert report["rejected"] == []
    assert report["governed_null"] == [
        {
            "key": "alpha_gpc",
            "name": "Alpha GPC",
            "reason": "current GSRS search collapses Alpha GPC to choline-related records rather than one reviewed exact alpha-glycerophosphocholine substance identity",
        }
    ]


def test_verify_iqm_file_reports_curated_governed_null_without_lookup():
    from api_audit.verify_unii import verify_iqm_file

    class FakeClient:
        def search_substance(self, *_args, **_kwargs):
            raise AssertionError("governed-null IQM entry should not hit live lookup")

    data = {
        "_metadata": {},
        "glutathione_peroxidase": {
            "standard_name": "Glutathione Peroxidase",
            "forms": {
                "glutathione peroxidase enzyme": {
                    "aliases": ["glutathione peroxidase"],
                }
            },
        },
    }

    report = verify_iqm_file(data, FakeClient(), apply=False)

    assert report["governed_null"] == [
        {
            "key": "glutathione_peroxidase",
            "name": "Glutathione Peroxidase",
            "reason": "enzyme entry resolves to glutathione in GSRS; keep UNII null rather than collapsing the enzyme to its substrate.",
        }
    ]
