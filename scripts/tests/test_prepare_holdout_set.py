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
        made["is_blend_header"] = bool(row.get("blend_header"))
        made["parent_index"] = row.get("parent_index")
        if row.get("form_text"):
            made["form_text"] = {"status": "read", "value": row["form_text"],
                                 "confidence": None, "sources": []}
        else:
            made["form_text"] = None
        # Only a row that prints a %DV carries one. Copying the template's
        # onto every row read a blend header as "48% DV".
        if row.get("percent_dv") is None:
            made["percent_dv"] = None
        else:
            made["percent_dv"]["value"] = row["percent_dv"]
        if row["value"] is None:
            # A blend child with no disclosed dose has no amount, not an
            # amount whose value is null.
            made["amount"] = None
        else:
            made["amount"]["value"] = {"value": row["value"], "unit_text": row["unit"]}
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
        "dsld_id": dsld_id, "brand_name": "Example Brand",
        "product_name": "Magnesium Glycinate 200 mg",
        "serving_info": {"basis_count": 2.0, "basis_unit": "capsule"},
        "label_record": {"source_name": "NIH DSLD", "source_record_id": dsld_id,
                         "source_date": "2019-01-01",
                         "formula_fingerprint": formula_fingerprint(panel)},
        "proprietary_blend_detail": {"has_proprietary_blends": True},
        "ingredients": [{"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg",
                         "forms": [], "raw_source_path": "ingredientRows[0]",
                         "dailyValue": 48.0}],
        "display_ingredients": panel,
        "inactive_ingredients": [{"label_display": "Vegetable cellulose"},
                                 {"label_display": "rice flour"}],
    }), encoding="utf-8")
    return blobs


def _bind(draft: dict, root: Path, key: str) -> dict:
    """Make a fixture draft a reading of one product's own photographs.

    The pinned fixture describes photographs that are not in any holdout set.
    Content is identity, so its evidence is rewritten to this product's photo
    hashes, and every photo id it cites follows.
    """
    entry = next(p for p in json.loads((root / "manifest.json").read_text())["products"]
                 if p["product_key"] == key)
    photos = entry["photos"]
    old_ids = list(draft["evidence_snapshot"])
    mapping = {old: photos[i]["photo_id"] for i, old in enumerate(old_ids)}
    draft["evidence_snapshot"] = {photos[i]["photo_id"]: photos[i]["sha256"]
                                  for i in range(len(old_ids))}

    def swap(value):
        if isinstance(value, dict):
            if value.get("photo_id") in mapping:
                value["photo_id"] = mapping[value["photo_id"]]
            for child in value.values():
                swap(child)
        elif isinstance(value, list):
            for child in value:
                swap(child)

    swap({k: v for k, v in draft.items() if k != "evidence_snapshot"})
    for sent, photo in zip(draft["sent_inputs"], photos):
        sent["original_sha256"] = sent["sent_sha256"] = photo["sha256"]
        sent.pop("crop", None)
    return draft


def _panel_draft(root: Path, *, magnesium: float = 200.0) -> Path:
    # A faithful reading of the panel: the blend is a header and its child
    # hangs under it. A flat reading is a real disagreement, not a fixture nit.
    draft = _valid_draft([
        {"name": "Magnesium", "value": magnesium, "unit": "mg", "percent_dv": 48.0},
        {"name": "Herbal Blend", "value": 450.0, "unit": "mg", "blend_header": True},
        {"name": "Ashwagandha", "value": None, "unit": None, "parent_index": 1},
    ])
    # The panel prints no directions, so --no-statements stays an honest answer.
    draft["statements"] = []
    if (root / "set" / "manifest.json").exists() and any(
            e["product_key"] == "northwind-mag"
            for e in json.loads((root / "set" / "manifest.json").read_text())["products"]):
        draft = _bind(draft, root / "set", "northwind-mag")
    path = root / "panel-draft.json"
    path.write_text(json.dumps(draft), encoding="utf-8")
    return path


def test_an_imported_record_is_what_the_scorer_accepts(workspace: Path, capsys) -> None:
    """The writer's acceptance test is the scorer's own loader, not a copy."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
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
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
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
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    blobs = _panel_record(workspace, "702")
    blob_path = blobs / "702.json"
    tampered = json.loads(blob_path.read_text())
    tampered["label_record"]["formula_fingerprint"] = "b" * 64
    blob_path.write_text(json.dumps(tampered), encoding="utf-8")

    assert _import(root, "northwind-mag", "702", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "does not match its own panel" in capsys.readouterr().err


def test_an_invalid_barcode_is_refused_before_writing_gold(workspace: Path, capsys) -> None:
    """Gold must use the same check-digit identity owner as submissions."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    gold_path = root / "gold" / "northwind-mag.json"
    before = gold_path.read_bytes()
    blobs = _panel_record(workspace, "702b")

    assert _import(root, "northwind-mag", "702b", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--barcode", "123456789013",
                   "--no-statements") == 2
    assert "valid UPC/EAN/GTIN" in capsys.readouterr().err
    assert gold_path.read_bytes() == before


def test_physical_confirmation_and_a_statements_decision_are_both_required(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    blobs = _panel_record(workspace, "703")
    draft = _panel_draft(workspace)

    assert _import(root, "northwind-mag", "703", draft, blobs, "--no-statements") == 2
    assert "--confirmed-physical-label" in capsys.readouterr().err

    assert _import(root, "northwind-mag", "703", draft, blobs,
                   "--confirmed-physical-label") == 2
    assert "a claim nobody made" in capsys.readouterr().err


def test_a_refused_import_leaves_the_gold_and_manifest_untouched(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
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
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
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
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    (root / "freeze.json").write_text("{}", encoding="utf-8")
    blobs = _panel_record(workspace, "706")
    assert _import(root, "northwind-mag", "706", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "frozen" in capsys.readouterr().err


def test_the_comparison_covers_everything_gold_takes_from_the_record(workspace: Path, capsys) -> None:
    """Zero disagreements has to mean more than "names and doses agree".

    Gold takes nesting, forms and identity from the record too. If those were
    never compared, one confirmation would be attesting to fields nobody
    checked against the package.
    """
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    blobs = _panel_record(workspace, "710")

    flat = _valid_draft([
        {"name": "Magnesium", "value": 200.0, "unit": "mg", "percent_dv": 48.0},
        {"name": "Herbal Blend", "value": 450.0, "unit": "mg"},   # header read as a row
        {"name": "Ashwagandha", "value": None, "unit": None},     # child read as flat
    ])
    flat["statements"] = []
    flat = _bind(flat, root, "northwind-mag")
    path = workspace / "flat.json"
    path.write_text(json.dumps(flat), encoding="utf-8")

    assert _import(root, "northwind-mag", "710", path, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    error = capsys.readouterr().err
    assert "blend_header" in error and "nesting" in error


def test_disclosure_hint_is_never_claimed_from_a_record(workspace: Path, capsys) -> None:
    """It is a scored field, and a record cannot say what the panel printed."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    blobs = _panel_record(workspace, "711")
    assert _import(root, "northwind-mag", "711", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 0
    capsys.readouterr()
    gold = json.loads((root / "gold" / "northwind-mag.json").read_text())
    assert gold["other_ingredients"]["disclosure_hint"] is None
    assert gold["other_ingredients"]["text"] == "Vegetable cellulose, rice flour"


def test_a_brand_the_manifest_does_not_share_is_refused_before_freeze(workspace: Path, capsys) -> None:
    """Freeze refuses this; catching it here saves finding out at the end."""
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Northwind/magnesium") == 0
    blobs = _panel_record(workspace, "712")
    assert _import(root, "northwind-mag", "712", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "can never be frozen" in capsys.readouterr().err


def test_a_malformed_record_id_is_refused_as_a_message(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "713")
    assert _import(root, "northwind-mag", "../secret", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "invalid catalog record id" in capsys.readouterr().err


def test_a_placeholder_reviewer_is_refused(workspace: Path, capsys) -> None:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts") == 0
    blobs = _panel_record(workspace, "714")
    assert main(["import-reference", str(root), "--key", "northwind-mag",
                 "--dsld-id", "714", "--draft", str(_panel_draft(workspace)),
                 "--reviewer", "   ", "--blobs-dir", str(blobs),
                 "--confirmed-physical-label", "--no-statements"]) == 2
    assert "initials of a real person" in capsys.readouterr().err



def _write_draft(workspace: Path, name: str, draft: dict) -> Path:
    path = workspace / name
    path.write_text(json.dumps(draft), encoding="utf-8")
    return path


def _panel_rows(**overrides) -> list[dict]:
    rows = [
        {"name": "Magnesium", "value": 200.0, "unit": "mg", "percent_dv": 48.0},
        {"name": "Herbal Blend", "value": 450.0, "unit": "mg", "blend_header": True},
        {"name": "Ashwagandha", "value": None, "unit": None, "parent_index": 1},
    ]
    return rows


def _setup(workspace: Path, dsld_id: str) -> tuple[Path, Path]:
    root = workspace / "set"
    assert _add(workspace, "northwind-mag", "front", "facts",
                family="Example Brand/magnesium") == 0
    return root, _panel_record(workspace, dsld_id)


def test_a_draft_of_other_photographs_is_refused(workspace: Path, capsys) -> None:
    """The comparison is only independent if it read THIS product's photos.

    An unbound draft could be of a different bottle, or a reading of the
    record itself; either would let "no disagreements" confirm nothing.
    """
    root, blobs = _setup(workspace, "720")
    unbound = _valid_draft(_panel_rows())
    unbound["statements"] = []
    draft = _write_draft(workspace, "unbound.json", unbound)

    assert _import(root, "northwind-mag", "720", draft, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "not a reading of this product's photographs" in capsys.readouterr().err


def test_an_in_progress_transcription_is_never_overwritten(workspace: Path, capsys) -> None:
    """Only a pristine template may be replaced. A half-done human reading
    is not complete gold, so the filled-gold check alone does not protect it."""
    root, blobs = _setup(workspace, "721")
    gold_path = root / "gold" / "northwind-mag.json"
    partial = json.loads(gold_path.read_text())
    partial["identity"]["brand"] = "Example Brand"
    partial["rows"][0]["display_name"] = "Magnesium"
    gold_path.write_text(json.dumps(partial), encoding="utf-8")
    before = gold_path.read_bytes()

    assert _import(root, "northwind-mag", "721", _panel_draft(workspace), blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "already holds a transcription" in capsys.readouterr().err
    assert gold_path.read_bytes() == before


def test_no_statements_is_refused_when_the_photograph_shows_one(workspace: Path, capsys) -> None:
    root, blobs = _setup(workspace, "722")
    draft = _bind(_valid_draft(_panel_rows()), root, "northwind-mag")
    assert draft["statements"], "the fixture draft reads a printed direction"
    path = _write_draft(workspace, "with-statement.json", draft)

    assert _import(root, "northwind-mag", "722", path, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "statement" in capsys.readouterr().err


def test_typed_statements_must_match_what_the_photograph_shows(workspace: Path, capsys) -> None:
    root, blobs = _setup(workspace, "723")
    path = _write_draft(workspace, "with-statement.json",
                        _bind(_valid_draft(_panel_rows()), root, "northwind-mag"))

    assert _import(root, "northwind-mag", "723", path, blobs,
                   "--confirmed-physical-label",
                   "--statement", "Keep out of reach of children at all times.") == 2
    capsys.readouterr()
    assert _import(root, "northwind-mag", "723", path, blobs,
                   "--confirmed-physical-label",
                   "--statement", "Take two capsules daily with food.") == 0


def test_a_refusal_never_shows_the_model_reading(workspace: Path, capsys) -> None:
    """The confirmer must not be anchored by a model value.

    A refusal names the rows and the record's value, and sends the person to
    the package. Printing what the model read would hand them the answer.
    """
    root, blobs = _setup(workspace, "724")
    assert _import(root, "northwind-mag", "724", _panel_draft(workspace, magnesium=2000.0),
                   blobs, "--confirmed-physical-label", "--no-statements") == 2
    error = capsys.readouterr().err
    assert "Magnesium" in error and "200 mg" in error
    assert "2000" not in error


def test_an_empty_operator_value_is_refused_as_a_message(workspace: Path, capsys) -> None:
    root, blobs = _setup(workspace, "725")
    for flag in ("--serving-size", "--servings-per-container", "--statement"):
        code = _import(root, "northwind-mag", "725", _panel_draft(workspace), blobs,
                       "--confirmed-physical-label", flag, "   ",
                       *(["--no-statements"] if flag != "--statement" else []))
        assert code == 2, flag
        assert "empty" in capsys.readouterr().err, flag


def test_reference_import_rechecks_actual_photo_bytes(workspace: Path, capsys) -> None:
    root, blobs = _setup(workspace, "726")
    path = _panel_draft(workspace)
    entry = json.loads((root / "manifest.json").read_text())["products"][0]
    (root / entry["photos"][0]["path"]).write_bytes(b"replaced photograph")
    assert _import(root, "northwind-mag", "726", path, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "photo" in capsys.readouterr().err.lower()


def test_reference_refusal_does_not_leak_an_invented_row_name(workspace: Path, capsys) -> None:
    root, blobs = _setup(workspace, "727")
    path = _panel_draft(workspace)
    draft = json.loads(path.read_text())
    draft["ingredient_rows"][0]["display_name"]["value"] = "INVENTED MODEL ANSWER"
    path.write_text(json.dumps(draft))
    assert _import(root, "northwind-mag", "727", path, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "INVENTED MODEL ANSWER" not in capsys.readouterr().err


def test_partial_warning_cannot_confirm_no_statements(workspace: Path, capsys) -> None:
    root, blobs = _setup(workspace, "728")
    draft = _bind(_valid_draft(_panel_rows()), root, "northwind-mag")
    draft["statements"][0]["status"] = "partial"
    path = _write_draft(workspace, "partial-warning.json", draft)
    assert _import(root, "northwind-mag", "728", path, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert "statement" in capsys.readouterr().err


def test_escaped_gold_path_is_refused_before_any_write(workspace: Path, monkeypatch) -> None:
    import prepare_holdout_set as module
    root, blobs = _setup(workspace, "729")
    path = _panel_draft(workspace)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["products"][0]["gold"] = "../outside.json"
    (workspace / "outside.json").write_text(json.dumps(module.gold_template("northwind-mag")))
    (root / "manifest.json").write_text(json.dumps(manifest))
    writes = []
    original = module._atomic_write_json
    def record_write(target, payload, **kwargs):
        writes.append(target)
        return original(target, payload, **kwargs)
    monkeypatch.setattr(module, "_atomic_write_json", record_write)
    assert _import(root, "northwind-mag", "729", path, blobs,
                   "--confirmed-physical-label", "--no-statements") == 2
    assert writes == []
