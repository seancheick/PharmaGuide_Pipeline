# Species-swap aliases — October 19, 2026

Problem (from the #181 audit): after ADR-0005 a DSLD `ingredientGroup` cannot replace an identity
whose exact curated alias is the printed name. These printed spellings were not curated aliases, so
the group still swapped the plant.

Scan: `scan_group_repairs.py` over the identity lane's merged-tree capture
(`~/pg_quality/identity_line_20261019/cand_aeae4534b.jsonl.records`, 3,596 labels) lists every row
a group still repairs away from the cleaner's id where the printed name (preparation words
removed) names the cleaner's id: 201 label/identity pairs, 1,319 rows (`scan_aeae4534b.out`).

## Entries (one receipt each)

| Entry | Added alias | Label evidence | Identity facts already in data | Verdict |
|---|---|---|---|---|
| IQM `wheatgrass` | "wheat grass juice powder", "organic wheat grass juice powder", "wheatgrass juice" | 12 rows printed "Wheat Grass juice powder" / "Wheatgrass Juice, Powder" (", Powder" is stripped by `strip_label_identity_qualifiers`), DSLD group "Couch Grass", no forms (202705, 206489, 247106, 259853, 27203, 27807, 289060, 289077, 309388, 31063, 31148, 78306) | wheatgrass alias "Triticum aestivum"; couch_grass is Elymus repens (UNII 8K1MK5E1FY), a different genus | fixed |
| IQM `barley_grass` | "barley grass juice" | 17 rows "Barley Grass Juice[, Powder]" / "Barley grass juice", group "Barley" (e.g. 289060, 297644, 326696) | barley_grass is young barley grass (form aliases "barley grass juice powder", "young barley grass"); barley_unspecified is "Barley (Unspecified Plant Part)" | fixed |
| botanical `green_bell_pepper` | "green bell pepper powder" | 317964 "Green Bell Pepper powder", group "Capsicum" | notes: Capsicum annuum unripe fruit, sweet pepper, no capsaicin; NHA_CHILI_PEPPER is the pungent chili | fixed |

No new identifier or clinical claim; each alias is the entry's own name plus a preparation word
printed on the label.

## Siblings checked (same scan), dispositions

- "Wild Cherry Fruit Extract" black_cherry → dark_sweet_cherry (294293-5): the label's form is
  "Prunus avium Fruit Extract" (sweet cherry), so the repair is **correct**; the curated alias
  "wild cherry fruit" on black_cherry (Prunus serotina) is ambiguous. Queued for the identity owner.
- "Grape leaf extract" grape_leaf → grape (28968, 28969), "Broccoli sprout powder" broccoli_sprout
  → broccoli (82403): the printed name already is an exact alias of the cleaner's id; #181's
  `_label_spells_identity` guard treats a label containing every word of the group's standard
  name ("Grape", "Broccoli") as naming the group, so a more specific part loses. Precedence in
  `identity_integrity.resolve_identity`; left for the identity owner (the same guard keeps the
  pinned ginger projection).
- "Pumpkin seed[ powder/extract]" pumpkin_seed → pumpkin (34 rows): botanical `pumpkin` itself
  carries seed aliases ("pumpkin seed", "pumpkin seed oil", "cucurbita pepo seed extract"), so the
  fruit and seed are conflated in data. Needs an alias split; queued.
- "Green Onion" green_onion → onion (146): scallion identity (Allium fistulosum vs immature
  A. cepa) unresolved; queued.
- Synonym/role refinements (ginkgo_biloba → ginkgo, papaya powder, protease, BLEND_* →
  BLEND_GENERAL, red cabbage colorant → cabbage food) and recorded decisions (knotweed →
  resveratrol, green tea): unchanged.

## Measurement

Replay of every raw label printing one of the new spellings (43) plus 150 controls, main 625e90425
vs candidate (`replay.py snapshot --full --blob`, `compare --all-paths`): 31 products change, all
identity corrections (wheat grass 12 rows, barley grass 19 incl. 2 cleaner rows "Barley Grass
Juice, Fermented", bell pepper 1); **0 score, 0 interaction rule, 0 safety-status changes**;
0 controls changed.
