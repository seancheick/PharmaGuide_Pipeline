"""#199 audit B2 (October 20, 2026): a whole grape or grape-PAC extract carries trivial
resveratrol unless a percentage is declared, so its entry records no provenance-only marker.
Run from the repo root with $PG_PYTHON, then `scripts/data_batch.py check
scripts/data/botanical_marker_contributions.json --since <ref> --expect botanicals/grape`."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

BMC = "scripts/data/botanical_marker_contributions.json"
bmc = data_batch.load(BMC)
[contrib] = bmc["botanicals"]["grape"]["delivers"]
assert "provenance_without_declaration" not in contrib
contrib["provenance_without_declaration"] = False
data_batch.save(BMC, bmc)
