#!/usr/bin/env python3
"""Guard the hardening of scripts/audits/interaction_rules/_url_rot_fix.py.

That tool repairs citation URLs in the clinical data file. Two past hazards:
  1. it wrote the data file BY DEFAULT (only --dry-run stopped it);
  2. it accepted pubmed_search()[0] with no content check (ghost-reference risk).

These tests lock the fixes at the pure-function boundary (no network): write only
on explicit --apply, and accept a replacement PMID only when its article text is
on-topic. Importing the module runs no network (main() is __main__-gated).
"""
import importlib.util
import pathlib

_P = pathlib.Path(__file__).parent.parent / "audits" / "interaction_rules" / "_url_rot_fix.py"
_spec = importlib.util.spec_from_file_location("_url_rot_fix_under_test", _P)
urf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(urf)


def test_writes_only_with_explicit_apply():
    # default (no args) = dry-run, must NOT write
    assert urf._should_apply(["_url_rot_fix.py"]) is False
    # the OLD footgun: any non--dry-run arg used to trigger a write — now it must not
    assert urf._should_apply(["_url_rot_fix.py", "somethingelse"]) is False
    assert urf._should_apply(["_url_rot_fix.py", "--dry-run"]) is False
    # only --apply writes
    assert urf._should_apply(["_url_rot_fix.py", "--apply"]) is True
    assert urf._should_apply(["_url_rot_fix.py", "--apply", "--dry-run"]) is True


def test_on_topic_accepts_matching_article():
    # article names the ingredient -> on-topic
    assert urf._on_topic(
        "Nigella sativa black seed safety review",
        "Nigella sativa (black seed) oil and its effect on lipid profile: a trial.",
    )
    assert urf._on_topic(
        "Pygeum africanum Prunus africana review",
        "Prunus africana (Pygeum africanum) for benign prostatic hyperplasia.",
    )


def test_on_topic_rejects_ghost_article():
    # real PMID, wrong topic -> must be rejected (the ghost-reference failure mode)
    assert not urf._on_topic(
        "resveratrol safety pharmacology review",
        "Tamoxifen-induced changes in hepatic transposon expression in medaka fish.",
    )
    assert not urf._on_topic(
        "Pygeum africanum Prunus africana review",
        "A randomized controlled trial of statins in cardiovascular disease.",
    )


def test_on_topic_does_not_match_on_generic_words_only():
    # sharing only stopwords ('safety','review','trial') is NOT a topic match
    assert not urf._on_topic(
        "ashwagandha safety review",
        "A clinical trial: safety and review methodology for dietary supplements.",
    )
