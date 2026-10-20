"""Label wordings of real standardization claims the note did not recognize.

From the 25 products whose label stated the percentage in other words (PR201
measurement), each class verified as a real standardization claim:
- "95% Curcumin" (turmeric rows 16374, 1851, 228978, 3514, 69625, 82607): the
  label's own claim, shown as written (curcumin, not curcuminoids).
- Sensoril "10% (Withanolide) Glycoside Conjugates" (182627, 232923, 328399,
  328514, ...): Sensoril is standardized to >=10% withanolide glycoside
  conjugates and >=32% oligosaccharides.
- "3% Salidrosides" (241941): a Rhodiola standardization marker.
- A bare "80%" whose row name is the compound "Silymarin" (328072, 328076,
  332136).
A percentage that names no compound stays unrecognized.
"""
import pytest


@pytest.mark.parametrize("notes, raw, note", [
    ("Turmeric root extract (Form: 95% Curcumin Note: 150 mg) PlantPart: root", "Turmeric root extract", "95% curcumin"),
    ("std. to 32% oligosaccharides, 10% glycoside conjugates", "Sensoril", "10% glycoside conjugates"),
    ("std. to 10% withanolide glycoside conjugates", "Sensoril", "10% withanolide glycoside conjugates"),
    ("Rhodiola rosea root extract (Form: 3% Salidrosides) PlantPart: root", "Rhodiola rosea root extract", "3% salidrosides"),
    ("80%", "Silymarin", "80% silymarin"),
    # Not verifiable: no compound named, a brand name, or a typo naming another marker.
    ("min. 95%", "Bioperine", None),
    ("95%, 25:1, equivalent to 3,750mg of turmeric", "Turmeric Rhizome Extract", None),
    ("std. to 32% oligosaccharides, 10% Oligosaccharides", "Sensoril", None),
    ("80%", "Milk Thistle extract", None),
])
def test_a_verified_label_wording_is_recognized(notes, raw, note):
    from build_final_db import _compute_standardization_note
    assert _compute_standardization_note({"notes": notes, "raw_source_text": raw}) == note
