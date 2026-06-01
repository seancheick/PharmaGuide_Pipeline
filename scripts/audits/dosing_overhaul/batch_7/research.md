# Batch 7 — optimal-uls bioactive expansion + Inositol correction

8 new non-botanical bioactives added to rda_optimal_uls.json (generic dose path; 16-row data[]
grid; rda_ai = effective-dose lower bound; content-verified references[]). Inositol range corrected.
Full-file citation verify: 51 match / 2 mononym partial / 0 mismatch / 0 not_found.

| Ingredient | unit | range | anchor | PMIDs | note |
|---|---|---|---|---|---|
| Citicoline | mg | 250-500 | 250 | 33978188, 26179181 | Cognizin |
| Betaine Anhydrous (TMG) | mg | 2500-6000 | 2500 | 31809615, 36501070 | >=4 g/day raises LDL (safety flag) |
| Glycine | mg | 3000-15000 | 3000 | 22529837 | (mechanism ref 25533534 dropped — animal/SCN) |
| Essential Amino Acids | mg | 6000-15000 | 6000 | 29796648, 32806711 | |
| Pantethine | mg | 600-900 | 600 | 24600231, 21925346 | B5 derivative, lipid-lowering |
| Urolithin A | mg | 500-1000 | 500 | 35584623, 35050355 | Mitopure, GRAS |
| Bovine Colostrum | mg | 10000-60000 | 10000 | 38361147, 27462401 | milk allergen |
| L-Glutamine | mg | 5000-30000 | 5000 | 39397201 | (2026 narrative review 41752728 dropped) |

Inositol (existing): optimal_range 500-2000 -> **2000-4000** (PCOS guideline dose); data[] rda_ai
500 -> 2000; references added 38163998 (2023 International PCOS Guideline meta-analysis), 29042448.

Dropped weak refs per no-hallucination rigor: glycine 25533534 (animal mechanism), glutamine 41752728
(2026 narrative review). EAA dose range is the softest number (no single dose-response meta isolated).
