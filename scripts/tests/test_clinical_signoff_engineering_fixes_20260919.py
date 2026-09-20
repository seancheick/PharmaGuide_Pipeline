"""Regression tests for the 2026-09-19 clinical sign-off engineering fixes.

PharmaGuide's Phase-3 clinical review returned 17 products to engineering with
three named defect classes (review packet, 2026-09-19):

1. Quantified-row survival — "Fish Oil 75188/243713 and Bulk 1340 must not hit
   a 'no dose/no eligible row' gate when their labels contain explicit
   amounts." Root cause (75188/243713): ``_is_zero_dose_omega_molecular_form_attribute``
   only recognized deliverable-format children (ethyl esters, triglycerides),
   not DHA/EPA molecular constituents — so the dosed "Total Omega-3 Fatty
   Acids 300 mg" owner row was skipped as a nutrition-fact rollup and its
   dose-less DHA/EPA children were promoted with qty=0.0. Verified against the
   live DSLD v9 API: record 75188 carries a dosed parent row
   (UNII 71M78END5S) with DHA/EPA as ``forms`` children.

2. Specification-child parsing — "<1 ppm ginkgolic acid must never become a
   separately dosed active." Ginkgolic acid on extract labels (EMA Ginkgo
   spec: max 5 ppm) is a contaminant limit inside the extract specification,
   not an ingredient dose. A ppm/ppb-quantity active row is always a
   specification limit.

3. Standardization-marker modeling — "Pueraria mirifica -> miroestrol and
   ashwagandha extract -> withaferin A should preserve the botanical/extract
   as the primary dose-bearing identity rather than converting the
   standardization constituent into an unresolved standalone ingredient."
   Live DSLD 216948 models Miroestrol 16 mcg / Isoflavonoids 16 mcg as
   nestedRows of the dosed "standardized Pueraria mirifica root extract
   80 mg" parent; live DSLD 232718 models Withaferin A 12 mg with a
   from-prefixed "Ashwagandha extract" form. The IQM gains marker-grade
   canonical identities so the constituent resolves conservatively instead
   of quarantining the product.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _make_dsld_product(product_id: int, name: str, ingredient_rows: list) -> dict:
    return {
        "id": product_id,
        "fullName": name,
        "brandName": "TestBrand",
        "bundleName": name,
        "upcSku": "",
        "servingsPerContainer": "30",
        "netContents": "",
        "targetGroups": [],
        "userGroups": [],
        "physicalState": "Softgel",
        "thumbnail": "",
        "ingredientRows": ingredient_rows,
        "otheringredients": {"text": "", "ingredients": []},
        "statements": [],
        "claims": [],
        "servingSizes": [{"order": 1, "quantity": 1, "unit": "Softgel"}],
        "contacts": [],
    }


def _row(name, qty, unit, **extra):
    row = {
        "name": name,
        "category": extra.pop("category", "fatty acid"),
        "ingredientGroup": extra.pop("ingredientGroup", name),
        "quantity": [
            {
                "quantity": qty,
                "unit": unit,
                "servingSizeOrder": 1,
                "servingSizeQuantity": 1,
                "operator": "=",
                "dailyValueTargetGroup": [],
                "servingSizeUnit": "Softgel",
            }
        ],
        "nestedRows": extra.pop("nestedRows", []),
        "forms": extra.pop("forms", []),
        "alternateNames": extra.pop("alternateNames", []),
    }
    row.update(extra)
    return row


# ---------------------------------------------------------------------------
# 1. Quantified-row survival: dosed omega aggregate owner must survive
# ---------------------------------------------------------------------------


class TestDosedOmegaOwnerSurvival:
    """GNC Women's Ultra Mega Fish Oil 75188: 'Total Omega-3 Fatty Acids
    300 mg' with DHA/EPA as zero-dose forms children. The dosed parent is the
    EPA+DHA amount (scoring_input_contract._printed_epa_dha_owner contract)
    and must survive the nutrition-fact rollup skip.
    """

    def test_owner_predicate_recognizes_dha_epa_constituent_children(self, normalizer):
        """_is_dosed_omega_aggregate_owner must treat zero-dose DHA/EPA
        molecular constituents as attributes of the dosed omega total —
        the same contract it already applies to ethyl-esters/triglycerides
        deliverable-format children.
        """
        owner = _row(
            "Total Omega-3 Fatty Acids",
            300,
            "mg",
            ingredientGroup="Omega-3",
            uniiCode="71M78END5S",
            forms=[
                {"name": "Docosahexaenoic Acid", "prefix": None},
                {"name": "Eicosapentaenoic Acid", "prefix": None},
            ],
        )
        source_path = "ingredientRows[1]"
        assert normalizer._is_dosed_omega_aggregate_owner(owner, source_path) is True

    def test_full_pipeline_keeps_dosed_omega_total_row(self, normalizer):
        """End-to-end: the 300 mg row must appear in cleaned active output
        with its dose intact; the DHA/EPA forms must remain attributes of it
        (not promoted as dose-less standalone actives above it).
        """
        rows = [
            _row("Total Omega-3 Fatty Acids", 300, "mg", ingredientGroup="Omega-3",
                 uniiCode="71M78END5S",
                 forms=[
                     {"name": "Docosahexaenoic Acid", "prefix": None},
                     {"name": "Eicosapentaenoic Acid", "prefix": None},
                 ]),
        ]
        product = _make_dsld_product(75188, "Fish Oil", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        names_and_doses = {
            (r.get("name"), r.get("quantity"), r.get("unit")) for r in actives
        }
        assert any(
            name and "omega-3" in str(name).lower() and qty == 300
            for name, qty, _ in names_and_doses
        ), f"dosed omega total lost: {names_and_doses}"

    def test_deliverable_format_children_still_recognized(self, normalizer):
        """No regression: ethyl-esters/triglycerides children keep the
        original owner-predicate behavior.
        """
        owner = _row(
            "Omega-3 Fatty Acids", 600, "mg", ingredientGroup="Omega-3",
            forms=[
                {"name": "Ethyl Esters", "prefix": None},
                {"name": "Triglycerides", "prefix": None},
            ],
        )
        assert normalizer._is_dosed_omega_aggregate_owner(
            owner, "ingredientRows[0]"
        ) is True


# ---------------------------------------------------------------------------
# 2. Specification-child parsing: ppm/ppb rows are spec limits, never actives
# ---------------------------------------------------------------------------


class TestSpecificationLimitRows:
    """Life Extension Ginkgo Biloba Certified Extract (328464, archived
    snapshot): 'Ginkgolic Acid <1 ppm' is an extract specification limit
    (EMA refined-extract spec: max 5 ppm ginkgolic acids), not a dosed
    ingredient. Stale upstream snapshots transcribed it as a qty=1.0 ppm
    active row, which quarantined the product.
    """

    def _ginkgo_rows(self):
        return [
            _row(
                "Ginkgo biloba leaf extract", 120, "mg",
                category="herb",
                ingredientGroup="Ginkgo",
                forms=[{"name": "standardized to 24% ginkgo flavone glycosides", "prefix": None}],
            ),
            _row("Ginkgolic Acid", 1.0, "ppm", category="plant",
                 ingredientGroup="Ginkgolic Acid"),
        ]

    def test_ppm_active_row_is_not_score_eligible(self, normalizer):
        product = _make_dsld_product(328464, "Ginkgo Biloba Certified Extract 120 mg", self._ginkgo_rows())
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        ginkgolic = [r for r in actives if "ginkgolic" in str(r.get("name", "")).lower()]
        assert ginkgolic, "ginkgolic row must remain in the label record"
        assert all(
            r.get("score_eligible_by_cleaner") is not True
            for r in ginkgolic
        ), f"ppm spec-limit row became scoreable: {ginkgolic}"

    def test_ppm_row_lands_in_display_ledger_as_specification_limit(self, normalizer):
        product = _make_dsld_product(328464, "Ginkgo Biloba Certified Extract 120 mg", self._ginkgo_rows())
        cleaned = normalizer.normalize_product(product)
        display = cleaned.get("display_ingredients") or []
        spec_rows = [r for r in display if "ginkgolic" in str(r.get("raw_source_text", "")).lower()]
        assert spec_rows, "ginkgolic row must be visible in the display ledger"
        assert all(
            r.get("display_type") == "specification_limit" and r.get("score_included") is False
            for r in spec_rows
        ), f"unexpected display classification: {spec_rows}"

    def test_ginkgo_extract_dose_survives(self, normalizer):
        product = _make_dsld_product(328464, "Ginkgo Biloba Certified Extract 120 mg", self._ginkgo_rows())
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        ginkgo = [r for r in actives if "ginkgo" in str(r.get("name", "")).lower()]
        assert any(
            r.get("quantity") == 120 and r.get("score_eligible_by_cleaner") is True
            for r in ginkgo
        ), f"dosed ginkgo extract row lost or ineligible: {ginkgo}"

    def test_ppb_rows_also_excluded(self, normalizer):
        rows = [
            _row("Ginkgo biloba leaf extract", 120, "mg", category="herb",
                 ingredientGroup="Ginkgo"),
            _row("Ginkgolic Acid", 1.0, "ppb", category="plant",
                 ingredientGroup="Ginkgolic Acid"),
        ]
        product = _make_dsld_product(999001, "Ginkgo Extract", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        ginkgolic = [r for r in actives if "ginkgolic" in str(r.get("name", "")).lower()]
        assert all(r.get("score_eligible_by_cleaner") is not True for r in ginkgolic)

    def test_microgram_and_milligram_rows_unaffected(self, normalizer):
        """A constituent genuinely dosed in mcg (standardization marker) or
        mg must NOT be swept up by the spec-limit guard.
        """
        rows = [
            _row("Miroestrol", 16, "mcg", category="plant",
                 ingredientGroup="Miroestrol"),
            _row("Vitamin B12", 500, "mcg", category="vitamin",
                 ingredientGroup="Vitamin B12"),
        ]
        product = _make_dsld_product(999002, "Marker Test", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        by_name = {str(r.get("name", "")).lower(): r for r in actives}
        assert by_name.get("miroestrol", {}).get("score_eligible_by_cleaner") is True
        assert by_name.get("vitamin b12", {}).get("score_eligible_by_cleaner") is True

    def test_colloidal_silver_ppm_stays_scoreable(self, normalizer):
        """Team negative control (2026-09-19 review, instruction #2): the unit
        alone must never determine row role. Colloidal Silver 20 PPM (241744)
        legitimately describes its marketed material in ppm/concentration
        terms. Live DSLD 241744 models the row as Silver 20 mcg per 1 mL —
        but a hypothetical top-level 'Silver 20 ppm' row with NO extract
        parent, NO contaminant vocabulary, and NO limit text must also stay
        score-eligible. Only structural/contextual evidence creates a spec
        limit.
        """
        rows = [
            _row("Silver", 20, "ppm", category="mineral",
                 ingredientGroup="Silver"),
        ]
        product = _make_dsld_product(241744, "Colloidal Silver 20 PPM", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        silver = [r for r in actives if "silver" in str(r.get("name", "")).lower()]
        assert silver, "top-level silver ppm row must survive"
        assert all(
            r.get("score_eligible_by_cleaner") is True
            and r.get("cleaner_row_role") == "active_scorable"
            for r in silver
        ), f"colloidal silver swallowed by spec-limit rule: {silver}"

    def test_colloidal_silver_real_mcg_shape_stays_scoreable(self, normalizer):
        """The actual live DSLD 241744 row shape: Silver 20 mcg per 1 mL
        serving. Trivially score-eligible; pinned so the unit-lookalike
        family can never be swept by future spec-limit widening.
        """
        rows = [
            _row("Silver", 20, "mcg", category="mineral",
                 ingredientGroup="Silver"),
        ]
        product = _make_dsld_product(241744, "Colloidal Silver 20 PPM", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        silver = [r for r in actives if "silver" in str(r.get("name", "")).lower()]
        assert silver and all(r.get("score_eligible_by_cleaner") is True for r in silver)

    def test_nested_under_extract_parent_is_sufficient_context(self, normalizer):
        """The archived 328464 shape: Ginkgolic Acid 1 ppm nested under
        'Ginkgo biloba Leaf Extract'. Structural provenance alone (even
        without contaminant vocabulary) classifies the row as a spec limit.
        """
        rows = [
            _row("Ginkgo biloba Leaf Extract", 120, "mg", category="herb",
                 ingredientGroup="Ginkgo"),
            _row("Contaminant X", 2.0, "ppm", category="plant",
                 ingredientGroup="Contaminant X",
                 parentBlend="Ginkgo biloba Leaf Extract",
                 isNestedIngredient=True),
        ]
        product = _make_dsld_product(999003, "Extract Spec Test", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        contaminant = [r for r in actives if "contaminant x" in str(r.get("name", "")).lower()]
        assert contaminant and all(
            r.get("score_eligible_by_cleaner") is not True for r in contaminant
        ), f"extract-nested ppm row not treated as spec limit: {contaminant}"


# ---------------------------------------------------------------------------
# 3. Standardization-marker modeling: constituents resolve, parent keeps dose
# ---------------------------------------------------------------------------


class TestStandardizationMarkerModeling:
    """PM Phytogen (216948) and Longevity A.I. (232718): the standardization
    constituent must resolve to a conservative marker identity instead of
    quarantining the product, and the botanical/extract parent keeps the
    dose-bearing identity.
    """

    def _pm_phytogen_rows(self):
        return [
            _row("Folate", 333, "mcg DFE", category="vitamin",
                 ingredientGroup="Folate",
                 nestedRows=[
                     _row("Folic Acid", 200, "mcg", category="vitamin",
                          ingredientGroup="Folic Acid"),
                 ]),
            _row("standardized Pueraria mirifica root extract", 80, "mg",
                 category="herb", ingredientGroup="Pueraria mirifica",
                 nestedRows=[
                     _row("Miroestrol", 16, "mcg", category="plant",
                          ingredientGroup="Miroestrol"),
                     _row("Isoflavonoids", 16, "mcg", category="plant",
                          ingredientGroup="Isoflavonoids"),
                 ]),
        ]

    def test_pueraria_parent_survives_with_dose(self, normalizer):
        product = _make_dsld_product(216948, "PM Phytogen Complex", self._pm_phytogen_rows())
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        parent = [r for r in actives if "pueraria" in str(r.get("name", "")).lower()]
        assert parent, "dosed Pueraria parent row lost"
        assert any(r.get("quantity") == 80 for r in parent)

    def test_miroestrol_resolves_as_constituent_under_parent(self, normalizer):
        product = _make_dsld_product(216948, "PM Phytogen Complex", self._pm_phytogen_rows())
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        miro = [r for r in actives if "miroestrol" in str(r.get("name", "")).lower()]
        assert miro, "miroestrol row must survive (not be dropped silently)"
        row = miro[0]
        # Nested constituent of the dosed extract: parent provenance preserved.
        assert "pueraria" in str(row.get("parentBlend") or "").lower()
        # Scoring model: marker child of the parent extract — it must not
        # surface as an independent unresolved identity.
        assert row.get("cleaner_row_role") == "standardization_marker", (
            f"expected standardization_marker role, got "
            f"{row.get('cleaner_row_role')!r} with keys "
            f"{sorted(k for k in row if 'role' in k or 'marker' in k)}"
        )

    def test_withaferin_from_ashwagandha_preserves_botanical_provenance(self, normalizer):
        rows = [
            _row("Withaferin A", 12, "mg", category="herb",
                 ingredientGroup="Withanolide",
                 forms=[{"name": "Ashwagandha extract", "prefix": "from"}]),
        ]
        product = _make_dsld_product(232718, "Longevity A.I.", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        wf = [r for r in actives if "withaferin" in str(r.get("name", "")).lower()]
        assert wf, "withaferin row lost"
        row = wf[0]
        forms_text = str(row.get("forms") or "").lower()
        assert "ashwagandha" in forms_text or "ashwagandha" in str(
            row.get("standardName") or ""
        ).lower() or "ashwagandha" in str(row.get("marker_of") or "").lower(), (
            f"botanical provenance lost from withaferin row: "
            f"forms={row.get('forms')!r}"
        )
        assert row.get("quantity") == 12

    def test_non_standardized_botanical_child_not_forced_to_marker(self, normalizer):
        """Normal-botanical control: only STANDARDIZED extract parents create
        marker children. A plain botanical extract's nested constituent must
        keep ordinary active handling.
        """
        rows = [
            _row("Milk thistle extract", 150, "mg", category="herb",
                 ingredientGroup="Milk Thistle",
                 nestedRows=[
                     _row("Silymarin", 105, "mg", category="plant",
                          ingredientGroup="Silymarin"),
                 ]),
        ]
        product = _make_dsld_product(999004, "Plain Botanical Test", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        sily = [r for r in actives if "silymarin" in str(r.get("name", "")).lower()]
        assert sily, "nested silymarin row lost"
        assert all(
            r.get("cleaner_row_role") != "standardization_marker"
            and r.get("score_eligible_by_cleaner") is True
            for r in sily
        ), f"non-standardized botanical child misclassified: {sily}"


# ---------------------------------------------------------------------------
# 4. Omega family + independent-dose controls
# ---------------------------------------------------------------------------


class TestOmegaFamilyAndIndependentDoses:
    """243713 is the same GNC fish-oil defect family as 75188; and a label
    that declares EPA/DHA amounts independently must keep those quantified
    children (the aggregate-owner rule must not collapse real doses).
    """

    @pytest.mark.parametrize("product_id,name", [
        (75188, "GNC Women's Ultra Mega Fish Oil"),
        (243713, "GNC Fish Oil"),
    ])
    def test_gnc_fish_oil_family_keeps_dosed_parent(self, normalizer, product_id, name):
        rows = [
            _row("Total Omega-3 Fatty Acids", 300, "mg", ingredientGroup="Omega-3",
                 uniiCode="71M78END5S",
                 forms=[
                     {"name": "Docosahexaenoic Acid", "prefix": None},
                     {"name": "Eicosapentaenoic Acid", "prefix": None},
                 ]),
        ]
        product = _make_dsld_product(product_id, name, rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        assert any(
            "omega-3" in str(r.get("name", "")).lower() and r.get("quantity") == 300
            for r in actives
        ), f"{product_id}: dosed omega parent lost"

    def test_independently_dosed_epa_dha_children_survive(self, normalizer):
        """Team instruction #11, negative control: a fish oil whose label
        declares EPA and DHA amounts separately (Nordic Naturals style) must
        keep BOTH quantified children. The parent-owner rule exists for
        zero-dose attribute children only.
        """
        rows = [
            _row("Total Omega-3 Fatty Acids", 300, "mg", ingredientGroup="Omega-3",
                 nestedRows=[
                     _row("DHA", 200, "mg", category="fatty acid",
                          ingredientGroup="Docosahexaenoic Acid"),
                     _row("EPA", 100, "mg", category="fatty acid",
                          ingredientGroup="Eicosapentaenoic Acid"),
                 ]),
        ]
        product = _make_dsld_product(999005, "Independent Dose Fish Oil", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        dha = [r for r in actives if str(r.get("name", "")).lower() == "dha"]
        epa = [r for r in actives if str(r.get("name", "")).lower() == "epa"]
        assert dha and epa, f"independently dosed EPA/DHA children lost: {[r.get('name') for r in actives]}"
        assert any(r.get("quantity") == 200 for r in dha), f"DHA dose lost: {dha}"
        assert any(r.get("quantity") == 100 for r in epa), f"EPA dose lost: {epa}"
        assert all(r.get("score_eligible_by_cleaner") is True for r in dha + epa)


# ---------------------------------------------------------------------------
# 5. No fabricated doses: %DV backfill and unit heuristics are forbidden
# ---------------------------------------------------------------------------


class TestNoFabricatedDoses:
    """Team instructions #6 and #7: a row with populated %DV but zero amount
    (Gummie Multi 13041) must never have a dose back-calculated from %DV; a
    corrupted unit (E2: 'Vitamin A 900 mg RAE', 'Vitamin D3 100 mg') must
    never be silently converted mg->mcg on plausibility.
    """

    def test_no_dose_backfilled_from_percent_dv(self, normalizer):
        rows = [
            _row("Vitamin C", 0, "NP", category="vitamin",
                 ingredientGroup="Vitamin C"),
        ]
        # Attach a %DV the way DSLD does for the corrupted gummy record.
        rows[0]["quantity"][0]["dailyValueTargetGroup"] = [
            {"percent": 30.0, "targetGroup": "Adults and Children 4 years and above"}
        ]
        product = _make_dsld_product(13041, "Gummie Multi Vitamin Daily Formula", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        vc = [r for r in actives if str(r.get("name", "")).lower() == "vitamin c"]
        if not vc:
            pytest.fail("vitamin c row vanished entirely; expected it retained as dose-less")
        for r in vc:
            assert r.get("score_eligible_by_cleaner") is not True, (
                "zero-dose row with %DV became scoreable"
            )
            # The %DV must not have been converted into an amount.
            assert not (isinstance(r.get("quantity"), (int, float)) and r.get("quantity") and r.get("quantity") > 0), (
                f"dose fabricated from %DV: quantity={r.get('quantity')}"
            )

    def test_corrupted_unit_never_auto_converted(self, normalizer):
        """E2 case: Formula VM-2000 (231334) reports Vitamin A 6000 mcg DFE
        (wrong unit family) and Prenatal Advantage (328644) Vitamin A
        1300 mg RAE. Whatever the label says, the cleaner must NOT apply a
        plausibility-based mg->mcg conversion; the unit passes through so a
        reviewed label correction can own the fix.
        """
        rows = [
            _row("Vitamin A", 1300, "mg RAE", category="vitamin",
                 ingredientGroup="Vitamin A"),
            _row("Vitamin D3", 100, "mg", category="vitamin",
                 ingredientGroup="Vitamin D"),
        ]
        product = _make_dsld_product(328644, "Prenatal Advantage", rows)
        cleaned = normalizer.normalize_product(product)
        actives = cleaned.get("activeIngredients") or []
        by_name = {str(r.get("name", "")).lower(): r for r in actives}
        va = by_name.get("vitamin a")
        vd = by_name.get("vitamin d3") or by_name.get("vitamin d")
        assert va is not None and vd is not None, f"rows lost: {sorted(by_name)}"
        # mg-family units must survive as printed (no silent mcg rewrite).
        assert str(va.get("unit", "")).lower().startswith("mg"), (
            f"Vitamin A unit rewritten: {va.get('unit')!r}"
        )
        assert str(vd.get("unit", "")).lower().startswith("mg"), (
            f"Vitamin D3 unit rewritten: {vd.get('unit')!r}"
        )
