#!/usr/bin/env python3
"""Tests for PubChem verification safety and reporting."""

import json
import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_verify_flat_file_skips_polyethylene_glycol_entry_before_lookup():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            raise AssertionError("polyethylene glycol should be skipped before lookup")

    data = {
        "harmful_additives": [
            {
                "id": "ADD_POLYETHYLENE_GLYCOL",
                "standard_name": "Polyethylene Glycol (PEG)",
                "aliases": ["polyethylene glycol", "PEG", "macrogol"],
                "external_ids": {},
            }
        ]
    }

    report = verify_flat_file(data, "harmful_additives", FakeClient(), apply=False)

    assert report["cas_filled"] == []
    assert report["cid_filled"] == []
    assert report["governed_null"][0]["id"] == "ADD_POLYETHYLENE_GLYCOL"


def test_verify_flat_file_skips_polyvinylpyrrolidone_entry_before_lookup():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            raise AssertionError("polyvinylpyrrolidone should be skipped before lookup")

    data = {
        "harmful_additives": [
            {
                "id": "ADD_POLYVINYLPYRROLIDONE",
                "standard_name": "Polyvinylpyrrolidone (PVP)",
                "aliases": ["polyvinylpyrrolidone", "PVP", "povidone"],
                "external_ids": {},
            }
        ]
    }

    report = verify_flat_file(data, "harmful_additives", FakeClient(), apply=False)

    assert report["cas_filled"] == []
    assert report["cid_filled"] == []
    assert report["governed_null"][0]["id"] == "ADD_POLYVINYLPYRROLIDONE"


def test_verify_flat_file_skips_multi_compound_entry_before_lookup():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, *_args, **_kwargs):
            raise AssertionError("multi-compound entry should be skipped before lookup")

    data = {
        "harmful_additives": [
            {
                "id": "ADD_NITRITES",
                "standard_name": "Sodium Nitrite/Nitrate",
                "aliases": ["sodium nitrite", "sodium nitrate"],
                "external_ids": {},
            }
        ]
    }

    report = verify_flat_file(data, "harmful_additives", FakeClient(), apply=False)

    assert report["skipped"][0]["id"] == "ADD_NITRITES"


def test_verify_flat_file_reports_cid_mismatch():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            assert name == "Acesulfame Potassium (Ace-K)"
            return {
                "cid": 11074431,
                "cas": "55589-62-3",
                "cas_all": ["55589-62-3"],
                "synonyms": ["Acesulfame Potassium", "Ace-K", "55589-62-3"],
                "properties": None,
            }

    data = {
        "harmful_additives": [
            {
                "id": "ADD_ACESULFAME_K",
                "standard_name": "Acesulfame Potassium (Ace-K)",
                "aliases": ["acesulfame potassium", "ace-k"],
                "external_ids": {"cas": "55589-62-3", "pubchem_cid": 999},
            }
        ]
    }

    report = verify_flat_file(data, "harmful_additives", FakeClient(), apply=False)

    assert report["cid_mismatch"] == [
        {
            "id": "ADD_ACESULFAME_K",
            "name": "Acesulfame Potassium (Ace-K)",
            "existing_cid": 999,
            "pubchem_cid": 11074431,
        }
    ]


def test_verify_iqm_file_validates_existing_form_ids():
    from api_audit.verify_pubchem import verify_iqm_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            assert name == "magnesium glycinate"
            return {
                "cid": 84645,
                "cas": "14783-68-7",
                "cas_all": ["14783-68-7"],
                "synonyms": ["magnesium glycinate", "14783-68-7"],
                "properties": None,
            }

    data = {
        "magnesium": {
            "standard_name": "Magnesium",
            "forms": {
                "magnesium glycinate": {
                    "external_ids": {"cas": "14783-68-7", "pubchem_cid": 1},
                    "aliases": ["magnesium bisglycinate"],
                }
            },
        },
        "_metadata": {},
    }

    report = verify_iqm_file(data, FakeClient(), apply=False)

    assert report["form_cid_mismatch"] == [
        {
            "ingredient": "Magnesium",
            "form": "magnesium glycinate",
            "existing_cid": 1,
            "pubchem_cid": 84645,
        }
    ]


def test_verify_flat_file_apply_does_not_write_non_curated_ambiguous_match():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            if name == "Hydrogenated Starch Hydrolysate":
                return None
            if name == "HSH":
                return {
                    "cid": 447027,
                    "cas": None,
                    "cas_all": [],
                    "synonyms": ["HSH"],
                    "properties": None,
                }
            return None

    entry = {
        "id": "ADD_HSH",
        "standard_name": "Hydrogenated Starch Hydrolysate",
        "aliases": ["HSH"],
        "external_ids": {},
    }
    report = verify_flat_file({"harmful_additives": [entry]}, "harmful_additives", FakeClient(), apply=True)

    assert report["changes_applied"] == 0
    assert entry["external_ids"] == {}


def test_verify_flat_file_rejects_constituent_pubchem_match_for_generic_botanical():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            assert name == "Ashwagandha"
            return {
                "cid": 161671,
                "cas": "30655-48-2",
                "cas_all": ["30655-48-2"],
                "synonyms": [
                    "Ashwagandha",
                    "Withania somnifera",
                    "Withanolide D",
                    "30655-48-2",
                ],
                "properties": None,
            }

    entry = {
        "id": "BOT_ASHWAGANDHA",
        "standard_name": "Ashwagandha",
        "latin_name": "Withania somnifera",
        "aliases": ["Withania somnifera", "ashwagandha root extract"],
        "external_ids": {"cas": "30655-48-2", "pubchem_cid": 161671},
    }

    report = verify_flat_file({"botanical_ingredients": [entry]}, "botanical_ingredients", FakeClient(), apply=True)

    assert report["cas_filled"] == []
    assert report["cid_filled"] == []
    assert report["changes_applied"] == 2
    assert entry["external_ids"] == {}


def test_verify_flat_file_skips_normalized_umbrella_name_with_parenthetical():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, *_args, **_kwargs):
            raise AssertionError("normalized umbrella entry should be skipped before lookup")

    report = verify_flat_file(
        {
            "harmful_additives": [
                {
                    "id": "ADD_SUGAR_ALCOHOLS",
                    "standard_name": "Sugar Alcohols (Polyols)",
                    "aliases": ["mannitol", "xylitol"],
                    "external_ids": {},
                }
            ]
        },
        "harmful_additives",
        FakeClient(),
        apply=False,
    )

    assert report["skipped"][0]["id"] == "ADD_SUGAR_ALCOHOLS"


def test_verify_flat_file_treats_numeric_string_cid_as_same_value():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            assert name == "Vanillin"
            return {
                "cid": 1183,
                "cas": "121-33-5",
                "cas_all": ["121-33-5"],
                "synonyms": ["Vanillin", "121-33-5"],
                "properties": None,
            }

    report = verify_flat_file(
        {
            "harmful_additives": [
                {
                    "id": "ADD_VANILLIN",
                    "standard_name": "Vanillin",
                    "aliases": ["vanillin"],
                    "external_ids": {"cas": "121-33-5", "pubchem_cid": "1183"},
                }
            ]
        },
        "harmful_additives",
        FakeClient(),
        apply=False,
    )

    assert report["cid_mismatch"] == []


def test_verify_flat_file_governs_hsh_mixture_without_lookup():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            raise AssertionError("governed-null HSH entry should not hit PubChem")

    report = verify_flat_file(
        {
            "harmful_additives": [
                {
                    "id": "ADD_HSH",
                    "standard_name": "Hydrogenated Starch Hydrolysate",
                    "aliases": ["HSH"],
                    "external_ids": {},
                }
            ]
        },
        "harmful_additives",
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "id": "ADD_HSH",
            "name": "Hydrogenated Starch Hydrolysate",
            "reason": "sugar-alcohol mixture; no single authoritative PubChem compound",
            "expected_cas": None,
            "expected_cid": None,
        }
    ]


def test_verify_iqm_file_skips_non_compound_formulations_before_lookup():
    from api_audit.verify_pubchem import verify_iqm_file

    class FakeClient:
        def search_compound(self, *_args, **_kwargs):
            raise AssertionError("non-compound IQM formulation should be skipped before lookup")

    report = verify_iqm_file(
        {
            "vitamin_c": {
                "standard_name": "Vitamin C",
                "forms": {
                    "vitamin C with bioflavonoids": {
                        "aliases": ["vitamin c complex", "bioflavonoid vitamin c"]
                    },
                    "vitamin c (unspecified)": {
                        "aliases": ["vitamin c"]
                    },
                },
            },
            "_metadata": {},
        },
        FakeClient(),
        apply=False,
    )

    skipped_forms = {(item["ingredient"], item["form"]) for item in report["forms_skipped"]}
    assert ("Vitamin C", "vitamin C with bioflavonoids") in skipped_forms
    assert ("Vitamin C", "vitamin c (unspecified)") in skipped_forms


def test_verify_iqm_file_queries_plain_form_name_before_ingredient_prefixed_variant():
    from api_audit.verify_pubchem import verify_iqm_file

    seen = []

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            seen.append(name)
            if name == "retinol":
                return {
                    "cid": 445354,
                    "cas": "68-26-8",
                    "cas_all": ["68-26-8"],
                    "synonyms": ["retinol", "vitamin a alcohol", "68-26-8"],
                    "properties": None,
                }
            if name == "Vitamin A retinol":
                raise AssertionError("IQM should not try ingredient-prefixed form query before plain form name")
            return None

    verify_iqm_file(
        {
            "vitamin_a": {
                "standard_name": "Vitamin A",
                "forms": {
                    "retinol": {
                        "aliases": ["vitamin a alcohol", "all-trans-retinol"]
                    }
                },
            },
            "_metadata": {},
        },
        FakeClient(),
        apply=False,
    )

    assert seen[0] == "retinol"


def test_verify_iqm_file_limits_alias_fallbacks_for_speed():
    from api_audit.verify_pubchem import verify_iqm_file

    seen = []

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            seen.append(name)
            if name == "selenized yeast":
                return None
            if name == "yeast selenium":
                return None
            if name == "selenium yeast":
                raise AssertionError("IQM should not fan out to a second alias fallback")
            return None

    verify_iqm_file(
        {
            "selenium": {
                "standard_name": "Selenium",
                "forms": {
                    "selenized yeast": {
                        "aliases": ["yeast selenium", "selenium yeast", "food selenium"]
                    }
                },
            },
            "_metadata": {},
        },
        FakeClient(),
        apply=False,
    )

    assert seen == ["selenized yeast", "yeast selenium"]


def test_verify_flat_file_uses_curated_governed_null_policy_without_lookup():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, *_args, **_kwargs):
            raise AssertionError("curated governed-null entry should not hit PubChem")

    report = verify_flat_file(
        {
            "harmful_additives": [
                {
                    "id": "ADD_HFCS",
                    "standard_name": "High Fructose Corn Syrup",
                    "aliases": ["HFCS"],
                    "external_ids": {},
                }
            ]
        },
        "harmful_additives",
        FakeClient(),
        apply=False,
    )

    assert report["governed_null"] == [
        {
            "id": "ADD_HFCS",
            "name": "High Fructose Corn Syrup",
            "reason": "processed mixture; no single authoritative PubChem compound",
            "expected_cas": None,
            "expected_cid": None,
        }
    ]


def test_verify_flat_file_applies_curated_polymer_cas_without_lookup():
    from api_audit.verify_pubchem import verify_flat_file

    class FakeClient:
        def search_compound(self, *_args, **_kwargs):
            raise AssertionError("curated polymer entry should not hit PubChem")

    entry = {
        "id": "ADD_POLYETHYLENE_GLYCOL",
        "standard_name": "Polyethylene Glycol (PEG)",
        "aliases": ["PEG"],
    }

    report = verify_flat_file(
        {"harmful_additives": [entry]},
        "harmful_additives",
        FakeClient(),
        apply=True,
    )

    assert report["changes_applied"] == 1
    assert entry["external_ids"]["cas"] == "25322-68-3"
    assert report["governed_null"] == [
        {
            "id": "ADD_POLYETHYLENE_GLYCOL",
            "name": "Polyethylene Glycol (PEG)",
            "reason": "polymer / non-discrete PubChem substance; curated CAS only",
            "expected_cas": "25322-68-3",
            "expected_cid": None,
        }
    ]


def test_verify_flat_file_prefers_non_ambiguous_alias_before_acronym():
    from api_audit.verify_pubchem import verify_flat_file

    seen = []

    class FakeClient:
        def search_compound(self, name, include_properties=False):
            seen.append(name)
            if name == "Sodium Tripolyphosphate":
                return None
            if name == "pentasodium triphosphate":
                return {
                    "cid": 24455,
                    "cas": "7758-29-4",
                    "cas_all": ["7758-29-4"],
                    "synonyms": ["Pentasodium triphosphate", "STPP", "7758-29-4"],
                    "properties": None,
                }
            if name == "STPP":
                raise AssertionError("non-ambiguous chemical alias should be tried before acronym alias")
            return None

    report = verify_flat_file(
        {
            "harmful_additives": [
                {
                    "id": "ADD_SODIUM_TRIPOLYPHOSPHATE",
                    "standard_name": "Sodium Tripolyphosphate",
                    "aliases": [
                        "sodium tripolyphosphate",
                        "STPP",
                        "E451",
                        "pentasodium triphosphate",
                    ],
                    "external_ids": {},
                }
            ]
        },
        "harmful_additives",
        FakeClient(),
        apply=False,
    )

    assert report["ambiguous_match"] == []
    assert report["cid_filled"] == [
        {
            "id": "ADD_SODIUM_TRIPOLYPHOSPHATE",
            "name": "Sodium Tripolyphosphate",
            "cid": 24455,
        }
    ]
    assert seen == ["Sodium Tripolyphosphate", "pentasodium triphosphate"]
