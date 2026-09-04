# Immuno-LP20 preparation identity — 2026-09-04

Garden of Life DSLD 241325 declares **Immuno-LP20, 50 mg**, with tyndallized
Lactobacillus plantarum L-137 in its source forms. The same label separately
declares an immune probiotic blend. Neither row may replace the other's dose.

The [House Wellness manufacturer page](https://immuno-lp20.com/) was directly
checked by the identity researcher and parent on 2026-09-04. It distinguishes
the commercial Immuno-LP20 mixture (20% HK L-137, 80% dextrin) from the
heat-treated, nonviable L-137 constituent. Its
[ingredient resource](https://health.housefoods.jp/hk-l-137/exp_tokuchou_1_e.html)
also distinguishes HK L-137 from live organisms. These sources establish
preparation identity, not a new efficacy, safety, absorption, or quality rating.

The correction registers only the exact commercial name in the existing
source-preparation registry. Remove `immuno-lp20` and the ambiguous `lp20`
alias from the whole-species IQM form. Do not alias `HK L-137`, bare L-137,
live L. plantarum, or dextrin to the commercial mixture: their amounts do not
have the same meaning. No exact mixture CID/CAS/UNII has been verified;
leave external IDs empty instead of borrowing species or carrier IDs.

Keep the product's printed 50 mg unchanged. Although the manufacturer's
current specification would arithmetically imply 10 mg constituent and
40 mg dextrin, that decomposition is not separately printed on the inspected
Garden label and is not added to its ingredient rows. No mass-to-CFU conversion
or live-species study credit is introduced. The separate live probiotic blend
must remain detectable.

The old IQM numeric form rating and clinician records are not recalibrated by
this identity change. Research approval for this exact preparation is a
separate, outcome-specific task.

The regression also exposed a shared parsing omission: `heat-treated` (the
manufacturer's wording) was not in the row-owned microbial preparation guard,
although `heat-killed` and `tyndallized` were. Adding that bounded processing
term makes the same source-preparation decision for all three labels. The
guard still requires microbial identity in this row; product prose and
unrelated sibling forms do not establish processing or a replacement identity.

## Cross-brand taxonomy boundary

The expanded manifest-owned clean replay also exposed Doctor's Best 82408,
`Daily Immune Complex With Immuno-LP20`. Its `ingredientRows[5]` retains the
printed 50 mg preparation and the row-owned `heat-killed Lactobacillus
plantarum L-137` form, but DSLD's ingredient group is `TBD`. The supplied
cleaner canonical still incorrectly names the whole organism.

The exact preparation repair previously required resolved organism taxonomy,
even though the row's own form already contradicted that supplied organism.
Eight RED assertions covered missing/TBD taxonomy: six exact-preparation cases
failed to repair, and two unknown-preparation cases incorrectly retained
taxonomy-only identity. The existing identity resolver now recognizes this
same contradiction from the supplied organism plus the row-owned preparation
form. An exact verified registry name is still required to repair; unknown
preparations remain conflicts. No second resolver, sibling evidence or
constituent-dose inference was added. The four-file boundary backstop passed
240 tests, and independent review passed 122 focused cases.

This boundary reproduction uses preserved local cleaned label fields. The
original NIH PDF endpoint was reachable, but the browser screenshot failed;
no second visual verification of that original label is claimed here.
