#!/usr/bin/env python3
"""The 2026-08-18 reconciliation utility, after the assessment-axis hoist.

`build_manifest` produces two kinds of evidence change, and they get their axis
from different places:

* a **replacement** record is newly authored evidence and names its own axis;
* a **retained** record is the form's existing evidence with sources filtered,
  so the axis already on the form stands and must not be re-authored.

Treating both as replacements crashed the utility on the first retained form
(``KeyError: ('algae_oil', 'algae oil (dha)')``), because only the three
replacement forms are listed in ``REPLACEMENT_AXES``.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from iqm_form_evidence import FORM_AXIS_FIELD, validate_iqm_form  # noqa: E402


@pytest.fixture(scope="module")
def reconciliation():
    path = (
        SCRIPTS_DIR
        / "audits"
        / "form_evidence_20260813"
        / "apply_final_reconciliation.py"
    )
    spec = importlib.util.spec_from_file_location("apply_final_reconciliation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manifest(reconciliation):
    iqm = reconciliation._load_object(reconciliation.IQM_PATH)
    rows = reconciliation._load_rows(reconciliation.LEDGER_PATH)
    return iqm, reconciliation.build_manifest(iqm, rows)


def _changes_by_key(manifest: dict) -> dict:
    return {
        (change["ingredient_key"], change["form_key"]): change
        for change in manifest["changes"]
    }


def test_replacement_evidence_carries_its_own_axis(manifest, reconciliation):
    _iqm, built = manifest
    key = ("hmb", "hmb calcium salt (hmb-ca)")

    change = _changes_by_key(built)[key]

    assert change["set"][FORM_AXIS_FIELD] == reconciliation.REPLACEMENT_AXES[key]
    assert "axis" not in change["set"]["form_evidence"]


def test_retained_evidence_keeps_the_axis_already_on_its_form(manifest):
    """The form that crashed the builder, kept as the named regression."""
    iqm, built = manifest
    key = ("algae_oil", "algae oil (dha)")

    change = _changes_by_key(built)[key]

    assert "form_evidence" in change["set"]
    assert FORM_AXIS_FIELD not in change["set"], (
        "a retained record must not re-author the axis its form already owns"
    )
    assert iqm[key[0]]["forms"][key[1]][FORM_AXIS_FIELD] == "systemic_bioavailability"


def test_every_proposed_change_validates_against_its_owning_form(
    manifest, reconciliation
):
    """The builder validates internally; this proves it across all 89 forms.

    A retained record that silently lost its axis would still be written, so
    the whole manifest is re-checked the way the database would see it.
    """
    iqm, built = manifest
    problems: list[str] = []
    for change in built["changes"]:
        ingredient_key, form_key = change["ingredient_key"], change["form_key"]
        set_values = change.get("set", {})
        if "form_evidence" not in set_values:
            continue
        form = dict(iqm[ingredient_key]["forms"][form_key])
        form.update(set_values)
        problems.extend(
            validate_iqm_form(form, label=f"{ingredient_key}::{form_key}")
        )

    assert problems == []
    assert built["summary"]["audited_forms"] == 89
