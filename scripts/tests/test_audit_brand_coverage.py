import json

from audit_brand_coverage import common_word_prefix, scan_folder


def test_common_word_prefix_handles_brand_families_case_insensitively():
    assert common_word_prefix(["CVS Health", "cvs Pharmacy"]) == "CVS"
    assert common_word_prefix(["Goli Bites", "Goli Nutrition"]) == "Goli"


def test_common_word_prefix_fails_closed_when_first_word_differs():
    assert common_word_prefix(["Bayer One A Day", "One A Day Kids"]) == ""


def test_scan_folder_preserves_raw_brand_counts_and_dates(tmp_path):
    (tmp_path / "100.json").write_text(
        json.dumps({"brandName": "MegaFood", "entryDate": "2025-09-25T00:00:00"})
    )
    (tmp_path / "101.json").write_text(
        json.dumps({"brandName": "MegaFood", "entryDate": "2025-08-22"})
    )
    (tmp_path / "broken.json").write_text("not-json")

    names, dates = scan_folder(tmp_path)

    assert names == {"MegaFood": 2}
    assert sorted(dates) == ["2025-08-22", "2025-09-25"]
