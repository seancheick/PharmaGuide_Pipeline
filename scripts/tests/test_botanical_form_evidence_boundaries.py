"""Form-quality credit must not exceed evidence printed on the label."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    ("label", "parent", "expected_form"),
    [
        ("Milk Thistle Extract", "milk_thistle", "milk thistle (unspecified)"),
        ("Valerian root extract", "valerian", "valerian (unspecified)"),
        ("Ginkgo biloba extract", "ginkgo", "ginkgo (unspecified)"),
        ("Boswellia serrata extract", "boswellia", "boswellia (unspecified)"),
        ("Saw Palmetto Berry Extract", "saw_palmetto", "saw palmetto (unspecified)"),
    ],
)
def test_generic_botanical_extracts_do_not_receive_standardized_form_credit(
    enricher: SupplementEnricherV3,
    label: str,
    parent: str,
    expected_form: str,
) -> None:
    match = enricher._match_quality_map(
        label,
        label,
        enricher.databases["ingredient_quality_map"],
        cleaner_canonical_id=parent,
    )

    assert match is not None
    assert match["canonical_id"] == parent
    assert match["form_id"] == expected_form
