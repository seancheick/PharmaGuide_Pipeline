# Label conventions

Two files, two jobs. `reading.json` is what you saw on the photographs, with
where you saw it. `label.json` is the catalog label built from that reading,
plus the few things a reading cannot carry. Owners, if you need to check a
rule against code: `scripts/submission_review/extraction/envelope.py`
(draft), `to_manual_label.py` (reading → label), and
`scripts/product_submission_import.py::_validate_label_payload` (label).

## Contents

1. reading.json: shape
2. reading.json: field by field
3. label.json: what you add
4. Worked example

## 1. reading.json: shape

Exactly these top-level keys (the runtime adds provenance; adding it yourself
is refused): `identity`, `serving`, `ingredient_rows`, `other_ingredients`,
`statements`, `photo_roles`, `discrepancies`, `abstained`, `abstain_reason`,
`overall_confidence`.

A **field** is:

```json
{"value": "Trader Joe's", "status": "read", "confidence": 0.98,
 "sources": [{"photo_id": "<from photos.json>", "supporting_text": "TRADER JOE'S",
              "region": {"x": 0.21, "y": 0.08, "w": 0.55, "h": 0.07}}]}
```

- `status`: `read` (you can read all of it), `partial` (part of it, give what
  you can read), `unreadable` (printed but you cannot read it), `not_present`
  (the label does not print it). Only `read`/`partial` carry a `value` and
  sources; the other two have `value: null`, `sources: []`.
- `supporting_text`: the characters as printed, including case, punctuation
  and marks like ™. It is what the reviewer reads next to the crop, and what
  the OCR grounding check looks for (which misses symbols and curved print;
  that is the checker's limit, not a reason to change the quote).
- `value`: the same words in plain form. Display capitals may be written in
  normal case (`CREATINE Hydrochloride` → `Creatine Hydrochloride`); nothing
  else changes.
- `region`: normalized to the photo as displayed (0–1; x/y top-left, w/h
  size). Draw it around the printed text with a little margin. It becomes the
  crop beside the reviewer's tick, so a wrong or lazy box costs review time.
  Omit it only when you truly cannot place the text.
- `confidence`: your honest 0–1, or null.

An **amount** field's value is `{"value": <number>, "unit_text": "<unit as printed>"}`.

## 2. reading.json: field by field

- **identity.brand / identity.product_name**: split as printed on the front:
  brand `Trader Joe's`, product name `Vitamin D3 125 mcg (5000 IU)`. Keep the
  printed strength in the name when the front prints it as part of the name.
  `identity.barcode_digits_seen`: every digit under the barcode, including
  leading zeros (`0067 1422`, `3 49597 00280 7`), when all are crisp. Some
  digits unreadable → `partial` with what you can read, or null. A `read`
  value that is not a whole GTIN is refused.
- **serving.size**: the phrase as printed (`1 Tablet`). **serving.amount**:
  the same as a number plus unit (`{"value": 1, "unit_text": "Tablet"}`) when
  it is printed that plainly. **serving.servings_per_container**: as printed
  (`250`, `about 60`). **serving.basis_text**: the serving line verbatim.
- **ingredient_rows**: one row per printed line, in printed order.
  - `display_name`: the whole printed name, verbatim, including its
    parenthetical: `Vitamin C (as ascorbic acid)`,
    `Dried Rose Hips (Rosa canina)`.
  - `form_text`: the form, when the row prints one (`(as X)`, or a salt/ester
    in parentheses): `ascorbic acid`, `cholecalciferol`. A Latin binomial or a
    plant part is identity, not a form. A printed "(as X)" with empty
    `form_text` is refused: it is the most common reviewer complaint.
  - `amount`: the printed quantity and unit exactly: `1000` + `mg`, `125` +
    `mcg`. A second unit printed alongside (`(5,000 IU)`) stays in the row's
    display or is noted; the amount is the primary printed quantity. **A
    proprietary blend's total is the blend header's amount; a row that prints
    only a %DV has `amount: null`**, never a number derived from the %.
  - `percent_dv`: the printed %DV number (`1111`), or null. `*`/`†` "Daily
    Value not established" means null.
  - `is_blend_header` / `parent_index`: only a blend or complex header has
    children; children point at the header's index. Never express a form as
    a child row.
  - `status`: `read`, `partial` or `unreadable` for the row as a whole.
- **other_ingredients**: `text` is the full printed list, verbatim, one
  string, without the "Other Ingredients:" heading. `disclosure_hint`:
  - `present`: a list is printed, **wherever it sits**: below the panel, in
    the panel's box, on another side. This is almost always the answer.
  - `declared_none`: the label says there are none.
  - `on_facts_panel`: the inactive ingredients appear only as rows *inside*
    the Supplement Facts table; transcribe them as rows and leave `text` null.
  - `unknown`: no photo shows the list.

  Only `present` carries the list into the label. On S19 a correctly read
  list was marked `on_facts_panel` and titanium dioxide silently vanished;
  `record` now refuses that combination.
- **statements**: one field per printed statement, verbatim: the front's
  "DIETARY SUPPLEMENT" (statement of identity), directions, warnings,
  storage, distributor line, "Gluten Free", "Vegan", seals. Split sentences
  that have different types even when printed together: "Store in a cool,
  dry place. Keep out of reach of children." is a Storage statement and a
  Precautions re: Children statement. Not decorative graphics text (e.g.
  "TABLET SIZE" next to a size diagram), and nothing from shelf signs or other
  bottles in the frame.
- **photo_roles**: one entry per photo: `photo_id`, `declared` (its
  categories from photos.json), `inferred` (`[{"role": ..., "confidence": ...}]`
  from what you see), `readability` (`ok`/`partial`/`unreadable`), `issues`
  (`glare`, `blur`, `cut_off`, `curved`, `dark`, `small_print`).
- **discrepancies**: leave `[]`; the program adds its own findings.
  **abstained**: `false` unless the photos cannot support a label at all
  (then `true` with `abstain_reason`). **overall_confidence**: 0–1 or null.

## 3. label.json: what you add

`label.json` arrives filled from the reading. Add only what `unresolved.json`
names, never change a reading value (fix the reading and record again).

- **ingredientGroup** (every row, including children): the nutrient or
  botanical the row is, in catalog form, not the printed form:
  `Vitamin C`, `Vitamin D` (not "Vitamin D3"), `Vitamin K`, `Folate`,
  `Ashwagandha`, `Rhodiola rosea`, `Rose Hips`, `Flaxseed Oil`. For a blend
  header, the blend's printed name. The enricher uses this to match, so it is
  a judgment call worth flagging when a row is unusual.
- **physicalState**: the dosage form in DSLD's vocabulary, in both keys:
  `{"name": "Tablet or Pill", "langualCodeDescription": "Tablet or Pill"}`.
  Terms: `Capsule`, `Softgel Capsule`, `Tablet or Pill`, `Powder`,
  `Gummy or Jelly`, `Liquid`, `Lozenge`, `Other (e.g. tea bag)`. The
  enricher's delivery path reads `langualCodeDescription` only.
- **productType**: leave it out. It is a DSLD taxonomy call the pipeline only
  cross-checks.
- **servingSizes**: if the reading only had the phrase, add
  `{"minQuantity": 1, "maxQuantity": 1, "unit": "Tablet(s)", "order": 1}` from
  what is printed. Add `minDailyServings`/`maxDailyServings` **only when the
  directions print a daily amount** ("Take one tablet daily" → 1/1; "1 to 2
  daily" → 1/2). When the label prints a ceiling ("not to exceed 5 servings
  per day"), the ceiling is the maximum: it is the most a user is told they
  may take, and this number multiplies every interaction dose threshold, so
  under-stating it under-warns. Flag the choice in your report either way.
- **statements[].type**: replace `Label statement` with the DSLD type that
  fits; the pipeline parses some types (allergens read "Formula re:
  Contains"):
  `Suggested/Recommended/Usage/Directions`, `Precautions re: All Other`,
  `Precautions re: Children`, `Precautions re: Pregnant or Nursing or
  Prescription Medications`, `Precautions re: Allergies`, `Storage`,
  `Formula re: Contains`, `Formulation re: Does NOT Contain`,
  `Formulation re: Vegetarian/Vegan`, `Formulation re: Other`,
  `FDA Statement of Identity`, `FDA Disclaimer Statement`, `Seals/Symbols`,
  `General Statements: All Other Content`. A statement stays one printed
  sentence or block; do not merge warnings and storage into one.
- **otherIngredientsDisclosure / otherIngredients**: already set from the
  reading; fill `otherIngredients` only if unresolved names it.
- **UPC**: there is no UPC field. The barcode lives on the submission and the
  console checks it.

## 4. Worked example

Panel: "Serving Size 1 Tablet · Servings Per Container 250 ·
Vitamin C (as ascorbic acid) 1000 mg 1111% · Dried Rose Hips (Rosa canina)
100 mg *". Rows in reading.json (sources abbreviated):

```json
[{"display_name": {"value": "Vitamin C (as ascorbic acid)", "status": "read", "confidence": 0.97, "sources": [...]},
  "form_text": {"value": "ascorbic acid", "status": "read", "confidence": 0.97, "sources": [...]},
  "amount": {"value": {"value": 1000, "unit_text": "mg"}, "status": "read", "confidence": 0.97, "sources": [...]},
  "percent_dv": {"value": 1111, "status": "read", "confidence": 0.95, "sources": [...]},
  "parent_index": null, "is_blend_header": false, "status": "read"},
 {"display_name": {"value": "Dried Rose Hips (Rosa canina)", "status": "read", "confidence": 0.96, "sources": [...]},
  "form_text": null,
  "amount": {"value": {"value": 100, "unit_text": "mg"}, "status": "read", "confidence": 0.96, "sources": [...]},
  "percent_dv": null, "parent_index": null, "is_blend_header": false, "status": "read"}]
```

label.json then adds `ingredientGroup: "Vitamin C"` and `"Rose Hips"`,
`physicalState` Tablet or Pill, `minDailyServings`/`maxDailyServings` 1 from
"Take one tablet daily", and the statement types.
