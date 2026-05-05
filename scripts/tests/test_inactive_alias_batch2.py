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


def test_kollidon_and_natural_glaze_do_not_claim_generic_or_shellac_aliases(
    other_ingredients: dict[str, dict]
) -> None:
    kollidon_aliases = {alias.lower() for alias in other_ingredients["PII_KOLLIDON"].get("aliases", [])}
    assert "crospovidone" not in kollidon_aliases
    assert "kollidon cl" not in kollidon_aliases
    assert "polyvinylpyrrolidone" not in kollidon_aliases
    assert "povidone" not in kollidon_aliases

    natural_glaze_aliases = {alias.lower() for alias in other_ingredients["PII_NATURAL_GLAZE"].get("aliases", [])}
    assert "confectioner's glaze" not in natural_glaze_aliases


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("povidone", "Povidone"),
        ("crospovidone", "Crospovidone"),
        ("shellac", "Shellac"),
        ("confectioner's glaze", "Shellac"),
        ("natural glaze", "Natural Glaze"),
        ("kollidon", "Kollidon (Polyvinylpyrrolidone)"),
    ],
)
def test_inactive_alias_batch2_exact_resolution(
    normalizer: EnhancedDSLDNormalizer,
    label: str,
    expected: str,
) -> None:
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(label)
    assert mapped is True
    assert standard_name == expected
