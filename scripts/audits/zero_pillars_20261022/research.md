# Source checks — zero Dose / Evidence audit, October 22, 2026

Identity and label-unit corrections are source-specific, not global unit heuristics. Original NIH
PDFs were downloaded, rendered and visually checked; private copies and API responses are retained
in `~/pg_quality/zero_pillars_20261022/labels/`. These are agent source checks, not clinical approval.
No new clinical identifier, numerical rating, dose threshold or scoring policy was authored.

| Correction key | Original panel result | Receipt |
| --- | --- | --- |
| 77801 | Iodine153mcg, not153mg; existing automatic cleaner correction corroborated | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/77801.pdf) |
| 78327 | Iodine150mcg, not18mg | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/78327.pdf) |
| 33660 | Selenium200mcg, not25mg | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/33660.pdf) |
| 46729 | Iodine150mcg/100%DV, not100mg/10%DV; retain existing B6 correction | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/46729.pdf) |
| 27807 | Molybdenum75mg conflicts with100%DV on original: preserve printed amount and hold, never guess75mcg. Zeaxanthin190mcg | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/27807.pdf) |
| 802 | Molybdenum75mg conflicts with100%DV on original: preserve and hold | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/802.pdf) |
| 64433 | VitaminD800IU, not800mg | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/64433.pdf) |
| 64821 | VitaminD800IU, not800mg | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/64821.pdf) |
| 273629 | Folicacid200/100mcg and biotin75/37.5mcg, notmg; preserve both serving columns | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/273629.pdf) |
| 66380 | Magnesium125mg, not125mcg; retain existing niacin correction | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/66380.pdf) |
| 64494 | B12600mcg is correct; original prints10000%DV rather than1000% | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/64494.pdf) |
| 241969 | VitaminD125mcg(1000IU) is internally conflicting: preserve and hold, never infer25mcg | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/241969.pdf) |
| 213846 | L-Cystine500mg, not Alpha-Glucan Oligosaccharide; clear unrelated alpha-glucan UNII and preserve printed mass | [NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/213846.pdf) |

## Identity / member checks

- **Cystine:** remove contradictory L-Cystine alias from l_cysteine and veto cystine as a cysteine
  match via existing negative-match owner. Original213846 explains its disulfide structure.
  Live [PubChem cystine](https://pubchem.ncbi.nlm.nih.gov/compound/67678) and
  [cysteine](https://pubchem.ncbi.nlm.nih.gov/compound/5862) API responses confirm distinct formulas
  and InChIs. No new identifier or unreviewed form rating is inserted. All-corpus name/note search
  finds213846,328818,337851,297638; all measured, true cysteine/NAC controls retained. The current
  absence of a reviewed cystine canonical owner remains an explicit hold;213846 blob export is
  correctly refused by the existing unresolved-active ledger guard.
- **Grape skin:** remove skin-only alias from IQM's multi-part whole-grape preparation. It resolves
  to the existing grape botanical, not grape seed research. [NCCIH](https://www.nccih.nih.gov/health/grape-seed-extract)
  identifies grape seed extract as the seed preparation. Explicit seed/multi-part aliases retained.
- **Safflower oil:** remove bare oil alias from CLA80% form. Unmodified oil resolves to its existing
  distinct identity; explicitly qualified CLA preparations retain their form owners.
  [BASF source](https://www.basf.com/us/en/media/news-releases/2011/07/p-10-0057) and
  [technical composition](https://download.basf.com/p1/EN_StaticDocuments_6298/en/Technical_Information)
  distinguish converted CLA preparation from source oil. No new efficacy or bio score.
- **Neumentix:** [232839](https://api.ods.od.nih.gov/dsld/s3/pdf/232839.pdf) explicitly prints
  Neumentix phenolic complexK110-42,900mg, from spearmint aerial extract. Add exact alias to the
  existing spearmint preparation; single-constituent owner retains900mg, not an opaque blend.
  Existing spearmint citations29314866/19585478 content-verifier:2match,0mismatch.
- **CurQfen:** [271115](https://api.ods.od.nih.gov/dsld/s3/pdf/271115.pdf) prints turmeric extract
  with fenugreek; individual amounts unknown. Extend existing exact-reviewed header allowlist.
- **Trisynex:** [19598](https://api.ods.od.nih.gov/dsld/s3/pdf/19598.pdf) lists cetylated fatty
  acids and modified cellulose. Expand reviewed members; cellulose retains inactive/non-scorable
  role. Do not lend1200mg blend total to either member or import unrelated packet panels.
- **Anabolic Muscle Primer:** original [1179](https://api.ods.od.nih.gov/dsld/s3/pdf/1179.pdf),
  [12800](https://api.ods.od.nih.gov/dsld/s3/pdf/12800.pdf),
  [19471](https://api.ods.od.nih.gov/dsld/s3/pdf/19471.pdf) Ravage and
  [14168](https://api.ods.od.nih.gov/dsld/s3/pdf/14168.pdf) Rampant explicitly list yohimbe bark.
 1179/12800 also print HMB. Existing safety/evidence owners now see printed ingredients; parent
  blend masses remain undisclosed per member. Generic forms expansion was rejected because
  DSLD also uses forms for carriers/plant sources; the final code expands exact reviewed names only.
- **Printed volumes:** [213826](https://api.ods.od.nih.gov/dsld/s3/pdf/213826.pdf) prints peppermint
  oil0.2mL. Completed no-benchmark assessment recognizes disclosure through existing quantity owner,
  without density/mass inference.251975/328014 share this measured defect class. Unfinished benchmark
  reviews still receive zero with explicit incomplete-review wording.

## Confirmed controls

329641 is400mg elemental magnesium despite2200mg front-label compound mass.76542 magnesium
hydroxide2.6g is already converted to1083.556mg elemental by the existing owner. Neither is a unit
bug. Historical biotin%DV ratios reflect older300mcg versus current30mcg reference; not a blanket
10x transcription error. Protein labels294273/311852/312355/312356/312357 disclose30g whey ingredient,
not actual protein grams: existing reviewed policy forbids substituting ingredient/powder mass.
