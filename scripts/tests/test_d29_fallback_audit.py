"""
Sprint D2.9 regression tests — fallback-audit closure.

After the D5.1 pipeline run the user asked for an audit of all
fallbacks across the 20-brand dataset to ensure each fallback lands
on `(unspecified)` **only when the label is truly unspecified**, not
when the label names a specific form that the IQM should have matched.

Audit findings (post-D3.4) — 17 parent-fallback rows + 2 form-DIFFER
rows across 20 brands. Four real gaps were identified:

1. **Cranberry + "Proanthocyanidin" form text** — the generic PAC
   aliases were removed from cranberry in D3.4 to avoid a cross-
   canonical duplicate with the dedicated `pac` stub. But form
   matching is *parent-scoped* after canonical resolution (cranberry
   → look up form within cranberry's forms), so re-adding
   "proanthocyanidin" / "proanthocyanidins" to cranberry's standardized
   form is safe and medically correct — PAC is cranberry's
   standardization marker (same pattern as vitexin/hawthorn).

2. **Cascara Sagrada bark POWDER** — label said "powder" but IQM
   only had an `extract` form. Falling back to the extract form
   overstated bio-availability. Added a dedicated
   `cascara sagrada bark powder` form (bio=4) so powder labels
   score correctly (score = bio + 3 natural = 7).

3. **OCR-typo "Bioperinie" full-string variants** — canonical-level
   resolution missed "Bioperinie(R) Black Pepper Extract" because
   the alias list only had atomic "bioperinie". Added full-string
   variants for OCR typos.

4. **Lactobacillus brevis strain codes** — "Lbr-35" (Garden of Life,
   x21) and "UALbr-02" (Ora, x2) are specific strain identifiers that
   should match the lactobacillus_brevis parent rather than falling
   unresolved. Added as aliases for strain traceability; bio_score
   unchanged (all strains score 8).

Invariant these tests lock in:
  Fallback to (unspecified) SHALL happen only when the label does
  not specify a form or strain. When the label names a form, the
  enricher must match it to the specific form alias.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())


# ---------------------------------------------------------------------------
# D2.9.1 — Cranberry proanthocyanidin form alias restoration
# ---------------------------------------------------------------------------


class TestCranberryProanthocyanidinFormMatch:
    """The cranberry standardized form must contain generic proanthocyanidin
    aliases so form-text "Proanthocyanidin" (parent-resolved to cranberry)
    matches the standardized form (bio=11) instead of falling to unspecified
    (bio=5)."""

    def test_cranberry_standardized_form_has_proanthocyanidin_aliases(self, iqm) -> None:
        cran = iqm.get("cranberry", {}).get("forms", {}).get(
            "cranberry extract (25% proanthocyanidins)", {}
        )
        aliases = [a.lower() for a in cran.get("aliases", [])]
        for req in (
            "proanthocyanidin",
            "proanthocyanidins",
            "cranberry proanthocyanidins",
            "cranberry pacs",
        ):
            assert req in aliases, (
                f"D2.9.1 regression: {req!r} missing from cranberry "
                f"standardized form aliases."
            )

    def test_proanthocyanidin_resolves_to_cranberry_canonical(self, normalizer) -> None:
        """Bare 'Proanthocyanidin' is ambiguous — but cranberry is the most
        commercially relevant canonical (UTI support). This verifies the
        alias routing without asserting a specific form resolution (that
        happens in the enricher's parent-scoped form match)."""
        r = normalizer._resolve_canonical_identity("Proanthocyanidin", raw_name="Proanthocyanidin")
        assert r is not None and r[0] == "cranberry"


# ---------------------------------------------------------------------------
# D2.9.2 — Cascara Sagrada bark powder dedicated form
# ---------------------------------------------------------------------------


class TestCascaraSagradaPowderForm:
    """Label 'Cascara Sagrada bark powder' must route to a dedicated powder
    form (bio=4, conservative), not the extract form (bio=6) which would
    overstate absorption."""

    def test_cascara_powder_form_exists(self, iqm) -> None:
        forms = iqm.get("cascara_sagrada", {}).get("forms", {})
        assert "cascara sagrada bark powder" in forms, (
            "D2.9.2 regression: cascara_sagrada must have dedicated powder form."
        )
        powder = forms["cascara sagrada bark powder"]
        assert powder.get("bio_score") == 4
        assert powder.get("natural") is True
        # score = bio + 3 (natural modifier)
        assert powder.get("score") == 7

    def test_cascara_powder_aliases_cover_label_variants(self, iqm) -> None:
        powder = (
            iqm.get("cascara_sagrada", {})
            .get("forms", {})
            .get("cascara sagrada bark powder", {})
        )
        aliases = [a.lower() for a in powder.get("aliases", [])]
        for req in (
            "cascara sagrada powder",
            "cascara sagrada bark powder",
            "cascara powder",
        ):
            assert req in aliases, (
                f"D2.9.2 regression: {req!r} missing from cascara powder aliases."
            )

    def test_cascara_powder_label_resolves(self, normalizer) -> None:
        r = normalizer._resolve_canonical_identity(
            "Cascara Sagrada bark powder", raw_name="Cascara Sagrada bark powder"
        )
        assert r is not None and r[0] == "cascara_sagrada"


# ---------------------------------------------------------------------------
# D2.9.3 — Piperine OCR-typo full-string aliases
# ---------------------------------------------------------------------------


class TestPiperineBioperineOcrFullStrings:
    """GNC's OCR of the Bioperine(R) trademark produces 'Bioperinie' (extra
    'i'). Canonical resolution for full-string labels must not drop to
    (None, None) on these OCR artifacts."""

    @pytest.mark.parametrize(
        "raw",
        [
            "Bioperinie(R) Black Pepper Extract",
            "Bioperinie Black Pepper Extract",
            "Bioperinie Black Pepper Fruit Extract",
            "BioPerine Black Pepper ext.",
            "BioPerine Black Pepper ext",
        ],
    )
    def test_bioperine_full_string_resolves_to_piperine(self, normalizer, raw) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == "piperine", (
            f"D2.9.3 regression: {raw!r} should resolve to piperine; got {r!r}"
        )

    def test_piperine_ocr_aliases_present(self, iqm) -> None:
        pip = (
            iqm.get("piperine", {})
            .get("forms", {})
            .get("piperine (unspecified)", {})
        )
        aliases = [a.lower() for a in pip.get("aliases", [])]
        for req in (
            "bioperinie black pepper extract",
            "bioperinie black pepper fruit extract",
            "bioperine black pepper ext",
            "bioperine black pepper ext.",
        ):
            assert req in aliases, (
                f"D2.9.3 regression: {req!r} missing from piperine aliases."
            )


# ---------------------------------------------------------------------------
# D2.9.4 — Lactobacillus brevis strain-code traceability
# ---------------------------------------------------------------------------


class TestLactobacillusBrevisStrainCodes:
    """Strain codes 'Lbr-35' (Garden of Life) and 'UALbr-02' (Ora) must
    resolve to lactobacillus_brevis canonical for strain traceability.
    Bio-score remains 8 (same across all strains for now)."""

    @pytest.mark.parametrize(
        "raw",
        [
            "Lactobacillus brevis Lbr-35",
            "L. brevis Lbr-35",
            "Lactobacillus brevis UALbr-02",
            "L. brevis UALbr-02",
        ],
    )
    def test_strain_code_resolves(self, normalizer, raw) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == "lactobacillus_brevis", (
            f"D2.9.4 regression: {raw!r} should resolve to "
            f"lactobacillus_brevis; got {r!r}"
        )

    def test_lbr_strain_aliases_present(self, iqm) -> None:
        form = (
            iqm.get("lactobacillus_brevis", {})
            .get("forms", {})
            .get("lactobacillus brevis (unspecified)", {})
        )
        aliases = [a.lower() for a in form.get("aliases", [])]
        for req in (
            "l. brevis lbr-35",
            "lactobacillus brevis lbr-35",
            "lbr-35",
            "l. brevis ualbr-02",
            "lactobacillus brevis ualbr-02",
            "ualbr-02",
        ):
            assert req in aliases, (
                f"D2.9.4 regression: {req!r} missing from "
                f"lactobacillus_brevis (unspecified) aliases."
            )


# ---------------------------------------------------------------------------
# D2.9 — truly-unspecified labels must still fall to (unspecified)
# ---------------------------------------------------------------------------


class TestTrulyUnspecifiedStillFallsCorrectly:
    """Regression guard: adding form aliases must not cause labels with NO
    form specifier to stop resolving to their (unspecified) fallback."""

    @pytest.mark.parametrize(
        "raw,expected_canonical",
        [
            ("Curcumin", "curcumin"),        # plain — truly unspecified
            ("Lactobacillus brevis", "lactobacillus_brevis"),  # plain strain-less
            ("Hawthorn", "hawthorn"),
            ("Cranberry", "cranberry"),
        ],
    )
    def test_plain_label_still_resolves_to_canonical(
        self, normalizer, raw, expected_canonical
    ) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] == expected_canonical, (
            f"{raw!r} should resolve to {expected_canonical}; got {r!r}"
        )
