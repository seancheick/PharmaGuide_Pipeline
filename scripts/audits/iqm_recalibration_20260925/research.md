# B12 family evidence receipt — verified 2026-09-25

Scope: source verification for oral/sublingual B12 calibration and immediate correction of unsupported absorption claims. This receipt is not clinician approval and does not itself override a score lock.

## Clinical sources

- https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/ — NIH Office of Dietary Supplements, Dietary supplements section, read live. Guidance does not establish absorption differences among supplemental forms, or an efficacy advantage for sublingual over oral delivery. It gives dose-dependent oral absorption examples; these are not direct measurements of mucosal sublingual absorption.
- https://pubmed.ncbi.nlm.nih.gov/14616423/ — Sharabi et al., 2003, *Replacement therapy for vitamin B12 deficiency: comparison between the sublingual and oral route.* Live EFetch through `api_audit.pubmed_client`; full parsed receipt in `b12_pubmed.json`. Thirty participants with low cobalamin; 500 mcg daily oral or sublingual cobalamin versus a B-complex group; serum cobalamin increased over four weeks with no significant between-group difference. This was an efficacy/serum-response comparison, not a measurement of methylcobalamin-specific absorption or intrinsic-factor bypass. Abstract excerpt: “There was no significant difference in concentrations between the treatment groups.” No retraction/concern/erratum flags in the fetched record.
- https://pubmed.ncbi.nlm.nih.gov/18709891/ — Carmel, 2008, review of fortification/supplementation and B12 bioavailability. Resolves to the expected topic. It discusses dose and malabsorption limits, not a comparative trial proving one ordinary supplemental cobalamin superior to another. It cannot justify the exact numerical separation 8/10/11 or a sublingual absorption fraction.

Disposition: remove unsupported sublingual 0.20/0.15 point estimates and their 0.10–0.40 / 0.10–0.30 ranges. Use the existing unknown representation, explain the efficacy result, and do not replace the numbers with oral values masquerading as direct sublingual measurements. Preserve the existing consumer identity descriptions. Numerical score recalibration is distinct from this factual correction and awaits reconciliation of the explicit C2 pins.

## Chemical identity

Live repository `PubChemClient` and `GSRSClient`, no cache, returned the records in `b12_live_identity.json`:

- Methylcobalamin: GSRS BR1SN1JS2W, METHYLCOBALAMIN; PubChem 10898559, methyl/carbanide ligand representation, CAS 13422-55-4, formula C63H91CoN13O14P. This supports the existing methyl compound identity, not a sublingual bioavailability advantage.
- Hydroxocobalamin: GSRS Q40X8H422O, HYDROXOCOBALAMIN; PubChem 44475014, CAS 13422-51-0. Hydroxo identity remains distinct from methyl and cyano forms; injectable indications do not establish superior oral uptake.
- Cyanocobalamin: GSRS P6YC3EG204, Cyanocobalamin; PubChem name search returned 166596686, formula C63H88CoN14O14P, with the same UNII in its record. Metal coordination/charge representations can differ among PubChem records. Do not replace an existing identifier with the first name-search CID.
- Adenosylcobalamin: PubChem 70678541, CAS 13870-90-1, adenosyl-containing corrinoid structure; GSRS name lookup returned no approved result. No new UNII is invented and no identifier is changed. Further exact-structure adjudication would be needed before adding an identifier.

No chemical identity or alias is changed by the absorption-only correction. Existing parent/compound identifiers are preserved. The sublingual record is a delivery format of the corresponding compound, not a newly identified chemical entity.

## Neighbor disposition and remaining decisions

Both sublingual records have unsupported fractional claims: correct them together as one delivery-family defect. The four oral records have dose-dependent absorption descriptions, but the numerical score separation and methyl/MTHFR/“used directly without conversion” language need a separate complete calibration correction. The unidentified B12 form has unsupported marketing/MTHFR language too; do not use it as evidence of an advantage. No score has yet been raised to satisfy a target total.
