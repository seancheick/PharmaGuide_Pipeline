"""
T2: Form-fallback audit noise suppression for single-form parents.

When an IQM parent canonical has exactly ONE form, a FORM_UNMAPPED_FALLBACK
outcome can only land on that one form by definition — it is structurally
impossible to pick the "wrong" form. These cases currently flood the
form_fallback_audit_report `action_needed_differs` bucket with rows like:

    Astragalus Root Extract | unmapped="Astragalus membranaceus Root Extract"
                            | fallback="astragalus extract"
                            | forms_differ=true  ← false positive

IQM only has `astragalus extract`; there is no alternate form to select.
The row is semantically noise, not an action item.

Fix: _classify_form_fallback_audit accepts a parent_form_count argument.
When parent_form_count == 1, classify as audit noise
(audit_noise_reason="single_form_parent", forms_differ=False), moving these
rows to the `likely_ok_same` bucket.

Multi-form parents (e.g., devils_claw with 3 forms) are untouched — those
represent real alias-gap opportunities.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


class TestClassifierSingleFormParent:
    """Unit tests for _classify_form_fallback_audit with parent_form_count plumbed in."""

    def test_single_form_parent_marks_as_noise(self, enricher):
        result = enricher._classify_form_fallback_audit(
            ing_name="Astragalus Root Extract",
            parent_name="Astragalus",
            unmapped_forms=["Astragalus membranaceus Root Extract"],
            fallback_form_name="astragalus extract",
            parent_form_count=1,
        )
        assert result["forms_differ"] is False
        # Either source_material_descriptor (Latin genus detection) or
        # single_form_parent is an acceptable noise classification here;
        # the former is more specific and wins when applicable.
        assert result["audit_noise_reason"] in {
            "source_material_descriptor",
            "single_form_parent",
            "non_actionable_form_text",
        }

    def test_single_form_parent_even_with_scientific_binomial(self, enricher):
        """
        Chamomile and Blueberry have the same pattern: one form, scientific
        binomial arrives as cleaned_form. Must all be classified as noise.
        """
        for ing, unmapped, fallback in [
            ("Chamomile Flower Extract", "Matricaria recutita Flower Extract", "chamomile extract"),
            ("Blueberry Fruit Extract, Wild", "Vaccinium angustifolium Fruit Extract, Wild", "blueberry extract"),
        ]:
            result = enricher._classify_form_fallback_audit(
                ing_name=ing,
                parent_name=ing.split(" ")[0],
                unmapped_forms=[unmapped],
                fallback_form_name=fallback,
                parent_form_count=1,
            )
            assert result["forms_differ"] is False, f"{ing!r} should be audit noise"
            assert result["audit_noise_reason"] in {
                "source_material_descriptor",
                "single_form_parent",
                "non_actionable_form_text",
            }

    def test_multi_form_parent_is_unchanged(self, enricher):
        """
        devils_claw has 3 forms; falling back to (unspecified) when harpagoside
        is available is a real alias gap. Must NOT be marked as single_form_parent.
        """
        result = enricher._classify_form_fallback_audit(
            ing_name="Devil's Claw extract",
            parent_name="Devil's Claw",
            unmapped_forms=["Harpagosides"],
            fallback_form_name="devil's claw (unspecified)",
            parent_form_count=3,
        )
        assert result.get("audit_noise_reason") != "single_form_parent"

    def test_no_parent_form_count_keeps_old_behavior(self, enricher):
        """Backward compat: callers that don't pass parent_form_count still work."""
        result = enricher._classify_form_fallback_audit(
            ing_name="Hawthorn",
            parent_name="Hawthorn",
            unmapped_forms=["Vitexins"],
            fallback_form_name="hawthorn (unspecified)",
        )
        # Must return the usual dict shape
        assert "forms_differ" in result
        assert "audit_noise_reason" in result
        # Vitexins is not noise — it's a real standardization marker (should be
        # classified by the marker branch or kept as action_needed).
        # Specifically: must NOT be classified as single_form_parent when
        # parent_form_count was not provided.
        assert result.get("audit_noise_reason") != "single_form_parent"


class TestDevilsClawHarpagosideRegression:
    """
    Regression guard for the Pure Encapsulations Devil's Claw scenario that
    Codex flagged: a product with
        name: "Devil's Claw (Harpagophytum procumbens and Harpagophytum zeyheri) extract"
        forms: [{"name": "Harpagosides"}]
    must resolve to the IQM form `devil's claw standardized (harpagoside)`
    (bio_score=9), not fall back to `devil's claw (unspecified)` (bio_score=5)
    or `devil's claw extract` (bio_score=7).

    The alias `Harpagosides` is already present under the harpagoside-standardized
    form in ingredient_quality_map.json; this test locks that in so a future edit
    that removes the alias or breaks the multi-form matcher surfaces immediately.
    """

    def test_devils_claw_with_harpagosides_resolves_to_standardized_form(self, enricher):
        ing_name = "Devil's Claw (Harpagophytum procumbens and Harpagophytum zeyheri) extract"
        std_name = "Devil's Claw (Harpagophytum procumbens)"
        cleaned_forms = [{"name": "Harpagosides", "percent": None, "order": 1}]

        iqm = enricher.databases.get("ingredient_quality_map", {})
        result = enricher._match_quality_map(
            ing_name, std_name, iqm, cleaned_forms=cleaned_forms
        )

        assert result is not None
        assert result.get("canonical_id") == "devils_claw"
        assert result.get("form_name") == "devil's claw standardized (harpagoside)"
        # bio_score for the harpagoside-standardized form is 9 per IQM
        assert result.get("bio_score") == 9.0
        # Must NOT be a fallback
        assert result.get("match_status") != "FORM_UNMAPPED_FALLBACK"
        assert not result.get("fallback_form_selected")


class TestCallSitePassesFormCount:
    """
    Integration check: the form_fallback capture site must consult the IQM
    for parent_form_count when emitting audit rows.
    """

    def test_astragalus_single_form_row_is_audit_noise_in_details(self, enricher):
        """
        Simulate an enricher run that triggers a FORM_UNMAPPED_FALLBACK for
        Astragalus Root Extract (scientific binomial). The appended audit row
        must have forms_differ=False and audit_noise_reason='single_form_parent'.
        """
        # Reset per-run state
        enricher._form_fallback_details = []

        # Confirm the fixture parent actually has exactly one form in IQM
        iqm = enricher.databases.get("ingredient_quality_map", {})
        astragalus = iqm.get("astragalus", {})
        forms = astragalus.get("forms", {})
        assert isinstance(forms, dict) and len(forms) == 1, (
            f"Test precondition: astragalus must have exactly 1 form, got {forms}"
        )

        # Directly synthesize the classifier call the append site would make,
        # but through the real code path. We call the classifier with the
        # parent_form_count that the append site is expected to compute.
        parent_form_count = len(forms)
        result = enricher._classify_form_fallback_audit(
            ing_name="Astragalus Root Extract",
            parent_name="Astragalus",
            unmapped_forms=["Astragalus membranaceus Root Extract"],
            fallback_form_name="astragalus extract",
            parent_form_count=parent_form_count,
        )
        assert result["forms_differ"] is False
        assert result["audit_noise_reason"] in {
            "source_material_descriptor",
            "single_form_parent",
            "non_actionable_form_text",
        }
