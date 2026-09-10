"""Assembling the frozen benchmark set: the guards that keep it worth having.

A benchmark is only evidence if nobody could have leaned on the answer. These
cover the three ways that quietly stops being true — a prefilled gold record, a
second reading by the same person, and a reading taken after seeing what the
model said — plus the ordinary mistakes that would otherwise be found at
scoring time, when re-shooting is the only fix.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from prepare_holdout_set import _gold_is_filled, main  # noqa: E402


def _photo(directory: Path, name: str) -> Path:
    """A distinct image: two identical files are one photograph, not two."""
    path = directory / f"{name}.jpg"
    image = Image.new("RGB", (120, 90), "white")
    ImageDraw.Draw(image).text((8, 8), name, fill="black")
    image.save(path)
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    source = tmp_path / "captures"
    source.mkdir()
    for name in ("front", "facts", "other"):
        _photo(source, name)
    assert main(["init", str(tmp_path / "set")]) == 0
    return tmp_path


def _add(root: Path, key: str, *photos: str, split: str = "development",
         case: str = "unit_mg", family: str = "Northwind/magnesium") -> int:
    argv = ["add", str(root / "set"), "--key", key, "--family", family,
            "--split", split, "--case", case]
    for photo in photos:
        argv += ["--photo", str(root / "captures" / f"{photo}.jpg")]
    return main(argv)


def test_a_new_set_starts_empty_and_ready(workspace: Path) -> None:
    manifest = json.loads((workspace / "set/manifest.json").read_text())

    assert manifest["schema_version"] == "submission_holdout_v1"
    assert manifest["products"] == []
    assert (workspace / "set/photos").is_dir()
    assert (workspace / "set/gold").is_dir()


def test_a_gold_record_arrives_blank(workspace: Path) -> None:
    assert _add(workspace, "a", "front", "facts") == 0

    gold = json.loads((workspace / "set/gold/a.json").read_text())
    # A prefilled template is the fastest way to turn a check into a rubber
    # stamp, so every value a human must read is empty and every checker is a
    # placeholder.
    assert gold["identity"] == {"brand": "", "product_name": "", "barcode_digits_seen": ""}
    assert [c["checker"] for c in gold["checked_by"]] == [
        "<initials of first checker>", "<initials of second checker>"
    ]
    assert all(c["model_output_seen"] is False for c in gold["checked_by"])


def test_photographs_are_hashed_into_the_manifest(workspace: Path) -> None:
    _add(workspace, "a", "front", "facts")

    entry = json.loads((workspace / "set/manifest.json").read_text())["products"][0]
    assert entry["split"] == "development"
    assert entry["cases"] == ["unit_mg"]
    assert len(entry["photos"]) == 2
    assert all(len(p["sha256"]) == 64 for p in entry["photos"])


def test_one_photograph_cannot_stand_for_two_products(workspace: Path) -> None:
    _add(workspace, "a", "front", "facts")

    assert _add(workspace, "b", "front", split="holdout", case="glare") == 2
    # The scorer refuses this too, but finding out then means re-shooting.
    assert not (workspace / "set/photos/b").exists()
    assert not (workspace / "set/gold/b.json").exists()


def test_the_same_photograph_twice_is_not_two_photographs(workspace: Path) -> None:
    assert _add(workspace, "a", "other", "other") == 2
    assert not (workspace / "set/photos/a").exists()


def test_a_refused_add_leaves_nothing_behind(workspace: Path) -> None:
    _add(workspace, "a", "front")

    assert _add(workspace, "b", "facts", case="not_a_real_case") == 2
    assert _add(workspace, "a", "other") == 2

    # Files no manifest row mentions are invisible to `status`, so a half
    # written add would be a set nobody can see is wrong.
    assert sorted(p.name for p in (workspace / "set/photos").iterdir()) == ["a"]
    assert sorted(p.name for p in (workspace / "set/gold").iterdir()) == ["a.json"]


def test_a_product_is_never_silently_replaced(workspace: Path) -> None:
    _add(workspace, "a", "front")

    assert _add(workspace, "a", "facts") == 2
    entry = json.loads((workspace / "set/manifest.json").read_text())["products"]
    assert len(entry) == 1


def test_unsafe_product_key_cannot_escape_the_set(workspace: Path) -> None:
    assert _add(workspace, "../outside", "front") == 2
    assert not (workspace / "outside").exists()
    assert not (workspace.parent / "outside").exists()


def test_family_is_explicit_brand_line_metadata(workspace: Path) -> None:
    root = workspace / "set"
    assert main([
        "add", str(root), "--key", "a", "--family", "Northwind",
        "--split", "development", "--case", "unit_mg", "--photo",
        str(workspace / "captures/front.jpg"),
    ]) == 2
    assert json.loads((root / "manifest.json").read_text())["products"] == []


def _fill_gold(root: Path, key: str, first: str, second: str,
               *, model_seen: bool = False) -> None:
    path = root / "set/gold" / f"{key}.json"
    gold = json.loads(path.read_text())
    for slot, checker in zip(gold["checked_by"], (first, second)):
        slot.update(checker=checker, checked_at="2026-09-10T00:00:00Z",
                    model_output_seen=model_seen and checker == first)
    _complete_gold(gold)
    path.write_text(json.dumps(gold, indent=2))


def _complete_gold(gold: dict) -> None:
    """Make the fixture satisfy the canonical gold schema, not just status."""
    gold["identity"].update(
        brand="Northwind", product_name="Magnesium Glycinate",
        barcode_digits_seen=None,
    )
    gold["serving"].update(
        size="2 capsules", servings_per_container="30",
        basis_text="2 capsules", amount={"value": 200, "unit_text": "mg"},
    )
    gold["other_ingredients"] = {"text": None, "disclosure_hint": "unknown"}
    gold["rows"] = [{
        "display_name": "Magnesium", "amount": {"value": 200, "unit_text": "mg"},
        "owner": None, "parent_index": None, "is_blend_header": False,
        "percent_dv": None, "form_text": None, "readable": True,
    }]


def _gold_filled(capsys) -> int:
    line = next(l for l in capsys.readouterr().out.splitlines() if "gold filled" in l)
    return int(line.split()[2])


def test_one_person_reading_twice_is_not_two_checks(workspace: Path, capsys) -> None:
    _add(workspace, "a", "front")
    _fill_gold(workspace, "a", "SB", "SB")

    main(["status", str(workspace / "set")])
    # The second reading exists to catch what the first one's eye slid over.
    assert _gold_filled(capsys) == 0


def test_a_checker_who_saw_the_model_does_not_count(workspace: Path, capsys) -> None:
    _add(workspace, "a", "front")
    _fill_gold(workspace, "a", "SB", "JD", model_seen=True)

    main(["status", str(workspace / "set")])
    assert _gold_filled(capsys) == 0


def test_two_independent_readings_count(workspace: Path, capsys) -> None:
    _add(workspace, "a", "front")
    _fill_gold(workspace, "a", "SB", "JD")

    main(["status", str(workspace / "set")])
    assert _gold_filled(capsys) == 1


def test_status_names_what_is_still_missing(workspace: Path, capsys) -> None:
    _add(workspace, "a", "front")

    main(["status", str(workspace / "set")])
    out = capsys.readouterr().out
    assert "needs 19 more" in out and "needs 40 more" in out
    # Naming the thin cases is the difference between a list of chores and a
    # number that never moves.
    assert "glare" in out and "unit_CFU" in out


def _record(root: Path, dsld_id: str, rows: list[dict]) -> Path:
    blobs = root / "blobs"
    blobs.mkdir(exist_ok=True)
    (blobs / f"{dsld_id}.json").write_text(json.dumps({
        "dsld_id": dsld_id, "brand_name": "Northwind",
        "product_name": "Magnesium Glycinate",
        "serving_info": {"basis_count": 2.0, "basis_unit": "capsule"},
        "label_record": {"source_name": "NIH DSLD", "source_date": "2019-01-01",
                         "formula_fingerprint": "f" * 64},
        "proprietary_blend_detail": {"has_proprietary_blends": False},
        "ingredients": rows,
        # The printed panel, which is what a photograph shows and what the
        # comparison reads. `ingredients` is the scored actives subset.
        "display_ingredients": [
            {"label_display_name": row["raw_source_text"],
             "exact_dose_text": f"{row['quantity']:g} {row['unit']}",
             "raw_source_path": f"ingredientRows[{index}]"}
            for index, row in enumerate(rows)],
    }), encoding="utf-8")
    return blobs


def _valid_draft(rows: list[dict]) -> dict:
    fixture = (Path(__file__).parents[1] / "submission_review" / "fixtures"
               / "label_draft_v1_cases.json")
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
    draft = json.loads(json.dumps(next(c for c in cases if c.get("valid"))["payload"]))
    template = draft["ingredient_rows"][0]
    built = []
    for row in rows:
        made = json.loads(json.dumps(template))
        made["display_name"]["value"] = row["name"]
        if row["value"] is None:
            # A blend child with no disclosed dose has no amount, not an
            # amount whose value is null.
            made["amount"] = None
        else:
            made["amount"]["value"] = {"value": row["value"], "unit_text": row["unit"]}
        made["parent_index"] = None
        made["is_blend_header"] = False
        built.append(made)
    draft["ingredient_rows"] = built
    return draft


def test_comparing_a_draft_never_writes_a_value_into_gold(workspace: Path, capsys) -> None:
    """The whole safeguard, in one test.

    `diff` reads a model's draft. It may print rows for a person to settle and
    nothing else: the gold record must be byte-identical afterwards and still
    count as unfilled, or a model's reading has quietly become the answer.
    """
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    gold = root / "gold" / "northwind-mag.json"
    before = gold.read_bytes()

    blobs = _record(workspace, "500", [
        {"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg", "forms": []}])
    draft = workspace / "draft.json"
    draft.write_text(json.dumps(_valid_draft(
        [{"name": "Magnesium", "value": 400.0, "unit": "mg"}])), encoding="utf-8")

    assert main(["diff", "--dsld-id", "500", "--draft", str(draft),
                 "--blobs-dir", str(blobs)]) == 0
    assert "200 mg" in capsys.readouterr().out
    assert gold.read_bytes() == before

    assert main(["status", str(root)]) == 0
    assert "gold filled    0 / 1" in capsys.readouterr().out


def test_a_file_that_is_not_a_draft_is_refused_with_a_message(workspace: Path, capsys) -> None:
    blobs = _record(workspace, "501", [
        {"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg", "forms": []}])
    junk = workspace / "junk.json"
    junk.write_text(json.dumps({"schema_version": "label_draft_v1", "not": "a draft"}),
                    encoding="utf-8")
    assert main(["diff", "--dsld-id", "501", "--draft", str(junk),
                 "--blobs-dir", str(blobs)]) == 2
    assert "not a valid label_draft_v1" in capsys.readouterr().err


def test_a_missing_record_or_draft_is_refused_not_guessed(workspace: Path, capsys) -> None:
    blobs = _record(workspace, "502", [])
    assert main(["diff", "--dsld-id", "999", "--draft", str(workspace / "nope.json"),
                 "--blobs-dir", str(blobs)]) == 2
    assert "no catalog record 999" in capsys.readouterr().err


def test_a_reference_sourced_gold_counts_as_filled(workspace: Path, capsys) -> None:
    """`status` must agree with the loader about what a complete gold is.

    benchmark.load_gold accepts one checker when the record names an
    independent source. This predicate hard-coded two, so every correctly
    imported reference record was reported blank forever and the set could
    never read as complete.
    """
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    gold_path = root / "gold" / "northwind-mag.json"
    gold = json.loads(gold_path.read_text())
    _complete_gold(gold)
    gold["sourced_from"] = {
        "source_name": "NIH DSLD", "source_record_id": "500",
        "formula_fingerprint": "a" * 64, "imported_at": "2026-09-10T00:00:00Z",
        "disagreements_resolved": 0,
    }
    gold["checked_by"] = [{"checker": "ab", "checked_at": "2026-09-10T00:00:00Z",
                           "human": True, "independent": True,
                           "model_output_seen": False, "confirmed_physical_label": True}]
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    assert main(["status", str(root)]) == 0
    assert "gold filled    1 / 1" in capsys.readouterr().out


def test_a_reference_gold_without_physical_confirmation_is_not_filled(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    gold_path = root / "gold" / "northwind-mag.json"
    gold = json.loads(gold_path.read_text())
    _complete_gold(gold)
    gold["sourced_from"] = {
        "source_name": "NIH DSLD", "source_record_id": "500",
        "formula_fingerprint": "a" * 64, "imported_at": "2026-09-10T00:00:00Z",
        "disagreements_resolved": 0,
    }
    gold["checked_by"] = [{"checker": "ab", "checked_at": "2026-09-10T00:00:00Z",
                           "human": True, "independent": True, "model_output_seen": False}]
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    assert main(["status", str(root)]) == 0
    assert "gold filled    0 / 1" in capsys.readouterr().out


def test_status_accepts_two_confirmers_on_reference_gold(workspace: Path, capsys) -> None:
    """Reference gold may have one or more distinct human confirmations."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    gold_path = root / "gold" / "northwind-mag.json"
    gold = json.loads(gold_path.read_text())
    _complete_gold(gold)
    gold["sourced_from"] = {
        "source_name": "NIH DSLD", "source_record_id": "500",
        "formula_fingerprint": "a" * 64, "imported_at": "2026-09-10T00:00:00Z",
        "disagreements_resolved": 0,
    }
    gold["checked_by"] = [
        {"checker": "ab", "checked_at": "2026-09-10T00:00:00Z", "human": True,
         "independent": True, "model_output_seen": False,
         "confirmed_physical_label": True},
        {"checker": "cd", "checked_at": "2026-09-10T00:00:00Z", "human": True,
         "independent": True, "model_output_seen": False,
         "confirmed_physical_label": True},
    ]
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    assert main(["status", str(root)]) == 0
    assert "gold filled    1 / 1" in capsys.readouterr().out


def test_status_does_not_call_malformed_reference_gold_filled(workspace: Path, capsys) -> None:
    """A malformed sourced_from value must not bypass the canonical loader."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front") == 0
    gold_path = root / "gold" / "northwind-mag.json"
    gold = json.loads(gold_path.read_text())
    gold["identity"]["brand"] = "Northwind"
    gold["sourced_from"] = "not-an-object"
    gold["checked_by"] = [{"checker": "ab", "checked_at": "2026-09-10T00:00:00Z",
                            "human": True, "independent": True,
                            "model_output_seen": False,
                            "confirmed_physical_label": True}]
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    assert main(["status", str(root)]) == 0
    assert "gold filled    0 / 1" in capsys.readouterr().out


def _import(root: Path, key: str, dsld_id: str, draft: Path, blobs: Path, *extra: str) -> int:
    return main(["import-reference", str(root), "--key", key, "--dsld-id", dsld_id,
                 "--draft", str(draft), "--reviewer", "sb", "--blobs-dir", str(blobs),
                 *extra])


def _panel_record(root: Path, dsld_id: str) -> Path:
    """A catalog record whose stored fingerprint matches its own panel."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parents[1]))
    from label_record_contract import formula_fingerprint

    panel = [
        {"label_display_name": "Magnesium", "exact_dose_text": "200 mg", "label_order": 0,
         "raw_source_path": "ingredientRows[0]", "display_type": "mapped_ingredient",
         "nested_depth": 0, "parent_label": None},
        {"label_display_name": "Herbal Blend", "exact_dose_text": "450 mg", "label_order": 1,
         "raw_source_path": "ingredientRows[1]", "display_type": "structural_container",
         "nested_depth": 0, "parent_label": None},
        {"label_display_name": "Ashwagandha", "exact_dose_text": "", "label_order": 2,
         "raw_source_path": "ingredientRows[1].nestedRows[0]",
         "display_type": "mapped_ingredient", "nested_depth": 1,
         "parent_label": "Herbal Blend"},
    ]
    blobs = root / "blobs"
    blobs.mkdir(exist_ok=True)
    (blobs / f"{dsld_id}.json").write_text(json.dumps({
        "dsld_id": dsld_id, "brand_name": "Northwind", "product_name": "Magnesium Glycinate",
        "serving_info": {"basis_count": 2.0, "basis_unit": "capsule"},
        "label_record": {"source_name": "NIH DSLD", "source_record_id": dsld_id,
                         "source_date": "2019-01-01",
                         "formula_fingerprint": formula_fingerprint(panel)},
        "proprietary_blend_detail": {"has_proprietary_blends": True},
        "ingredients": [{"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg",
                         "forms": [], "raw_source_path": "ingredientRows[0]",
                         "dailyValue": 48.0}],
        "display_ingredients": panel,
        "inactive_ingredients": [{"label_display": "Vegetable cellulose"}],
    }), encoding="utf-8")
    return blobs


def _panel_draft(root: Path, *, magnesium: float = 200.0) -> Path:
    draft = _valid_draft([
        {"name": "Magnesium", "value": magnesium, "unit": "mg"},
        {"name": "Herbal Blend", "value": 450.0, "unit": "mg"},
        {"name": "Ashwagandha", "value": None, "unit": None},
    ])
    path = root / "panel-draft.json"
    path.write_text(json.dumps(draft), encoding="utf-8")
    return path


def test_an_imported_record_is_what_the_scorer_accepts(workspace: Path, capsys) -> None:
    """The writer's acceptance test is the scorer's own loader, not a copy."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "700")
    draft = _panel_draft(workspace)

    assert _import(root, "northwind-mag", "700", draft, blobs,
                   "--confirmed-physical-label", "--barcode", "012345678905",
                   "--serving-size", "2 capsules", "--no-statements") == 0
    capsys.readouterr()

    gold = json.loads((root / "gold" / "northwind-mag.json").read_text())
    assert gold["sourced_from"]["source_name"] == "NIH DSLD"
    assert gold["sourced_from"]["disagreements_resolved"] == 0
    assert gold["checked_by"][0]["confirmed_physical_label"] is True
    assert gold["checked_by"][0]["model_output_seen"] is False
    # The printed panel, with nesting pointing at the real blend header.
    assert [r["display_name"] for r in gold["rows"]] == [
        "Magnesium", "Herbal Blend", "Ashwagandha"]
    assert gold["rows"][2]["parent_index"] == 1
    assert gold["rows"][1]["is_blend_header"] is True
    assert gold["rows"][0]["percent_dv"] == 48.0
    # Digits a person read off the package; the record's own barcode is not it.
    assert gold["identity"]["barcode_digits_seen"] == "012345678905"

    entry = next(p for p in json.loads((root / "manifest.json").read_text())["products"]
                 if p["product_key"] == "northwind-mag")
    assert entry["gold_sha256"] == hashlib.sha256(
        (root / "gold" / "northwind-mag.json").read_bytes()).hexdigest()
    assert main(["status", str(root)]) == 0
    assert "gold filled    1 / 1" in capsys.readouterr().out


def test_any_disagreement_refuses_the_import(workspace: Path, capsys) -> None:
    """Zero disagreements is what makes one confirmer enough.

    With nothing in dispute, no model value reached the record and the
    confirming person had none to be anchored by. One disagreement and that
    is no longer true, so the product takes the two-person route.
    """
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "701")
    draft = _panel_draft(workspace, magnesium=2000.0)

    assert _import(root, "northwind-mag", "701", draft, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    error = capsys.readouterr().err
    assert "1 row(s) disagree" in error and "two-person transcription route" in error
    assert _gold_is_filled(root, next(
        p for p in json.loads((root / "manifest.json").read_text())["products"]
        if p["product_key"] == "northwind-mag")) is False


def test_a_record_whose_fingerprint_does_not_match_its_panel_is_refused(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "702")
    blob_path = blobs / "702.json"
    tampered = json.loads(blob_path.read_text())
    tampered["label_record"]["formula_fingerprint"] = "b" * 64
    blob_path.write_text(json.dumps(tampered), encoding="utf-8")

    assert _import(root, "northwind-mag", "702", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "does not match its own panel" in capsys.readouterr().err


def test_physical_confirmation_and_a_statements_decision_are_both_required(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "703")
    draft = _panel_draft(workspace)

    assert _import(root, "northwind-mag", "703", draft, blobs, "--no-statements") == 2
    assert "--confirmed-physical-label" in capsys.readouterr().err

    assert _import(root, "northwind-mag", "703", draft, blobs,
                   "--confirmed-physical-label") == 2
    assert "a claim nobody made" in capsys.readouterr().err


def test_a_refused_import_leaves_the_gold_and_manifest_untouched(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    gold_path = root / "gold" / "northwind-mag.json"
    before_gold = gold_path.read_bytes()
    before_manifest = (root / "manifest.json").read_bytes()
    blobs = _panel_record(workspace, "704")

    assert _import(root, "northwind-mag", "704", _panel_draft(workspace, magnesium=99.0),
                   blobs, "--confirmed-physical-label", "--no-statements") == 2
    capsys.readouterr()
    assert gold_path.read_bytes() == before_gold
    assert (root / "manifest.json").read_bytes() == before_manifest


def test_a_complete_gold_record_is_never_silently_replaced(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "705")
    draft = _panel_draft(workspace)
    assert _import(root, "northwind-mag", "705", draft, blobs,
                   "--confirmed-physical-label", "--no-statements") == 0
    capsys.readouterr()
    assert _import(root, "northwind-mag", "705", draft, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "dated amendment" in capsys.readouterr().err


def test_importing_into_a_frozen_set_is_refused(workspace: Path, capsys) -> None:
    """Writing gold after a freeze invalidates every result scored against it."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    (root / "freeze.json").write_text("{}", encoding="utf-8")
    blobs = _panel_record(workspace, "706")
    assert _import(root, "northwind-mag", "706", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "frozen" in capsys.readouterr().err
