"""Batch 2: parent-scoped Panax quinquefolius clues on IQM ginseng's American form."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import data_batch  # noqa: E402

PATH = Path(__file__).resolve().parents[2] / "data" / "ingredient_quality_map.json"
FORM = "american ginseng (panax quinquefolius)"
blob = data_batch.load(PATH)
form = blob["ginseng"]["forms"][FORM]
assert form["source_form_aliases"] == ["panax quinquefolium l. rhizome extract"]
form["source_form_aliases"] = [
    "panax quinquefolium l. rhizome extract",
    "panax quinquefolius rhizome extract",
    "panax quinquefolius root extract",
]
print(data_batch.save(PATH, blob))
