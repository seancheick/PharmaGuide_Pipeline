from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


DATA_PATH = ROOT / "scripts" / "data" / "other_ingredients.json"


def _other_ingredients_by_id() -> dict[str, dict]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["other_ingredients"]}


@pytest.fixture(scope="module")
def other_ingredients() -> dict[str, dict]:
    return _other_ingredients_by_id()


@pytest.fixture
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def test_capsule_generic_does_not_claim_hpmc_or_pullulan_aliases(other_ingredients: dict[str, dict]) -> None:
    capsule = other_ingredients["OI_CAPSULE_GENERIC"]
    aliases = {alias.lower() for alias in capsule.get("aliases", [])}

    forbidden = {
        "hydroxypropyl methylcellulose",
        "hydropropyl methylcellulose",
        "hydroxy propyl methyl cellulose",
        "hypromellose capsules",
        "pullulan capsule",
        "pullulan polysaccharide",
        "organic vegetable pullulan capsules",
    }
    leaked = forbidden & aliases
    assert not leaked, f"generic Capsule entry must not claim specific chemistry aliases: {leaked}"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Hydroxypropyl Methylcellulose", "Hydroxypropyl Methylcellulose"),
        ("Pullulan Capsule", "Pullulan"),
        ("Purified Water", "Purified Water"),
        ("Deionized Water", "Deionized Water"),
        ("Distilled Water", "Deionized Water"),
        ("Carboxymethyl Cellulose", "Carboxymethyl Cellulose"),
        ("Cellulose Gum", "Cellulose Gum"),
        ("Sodium Carboxymethylcellulose", "Sodium Carboxymethylcellulose"),
        ("CMC", "Carboxymethyl Cellulose"),
    ],
)
def test_inactive_alias_batch1_exact_resolution(
    normalizer: EnhancedDSLDNormalizer,
    label: str,
    expected: str,
) -> None:
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(label)
    assert mapped is True
    assert standard_name == expected
