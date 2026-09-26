# Anthranoid laxative re-sourcing — evidence receipts (2026-09-25)

Scope: cascara and senna interaction rules (ghost PMIDs), cascara identity and inactive policy in
banned_recalled, aloe_ferox literature record. Every source below was read on 2026-09-25 by an agent
(not clinician-reviewed). Quotes are verbatim.

## Ghost PMIDs (PubMed efetch via verify_all_citations_content.fetch_articles)

| PMID | Real topic | Was cited for |
|---|---|---|
| 32876395 | "Isolation of six anthraquinone diglucosides from cascara sagrada bark by high-performance countercurrent chromatography" (J Sep Sci 2020) | every cascara sub-rule: pregnancy, liver, kidney, digoxin, pregnancy_lactation |
| 36702448 | "Cassiae Semen: A comprehensive review..." (Cassia obtusifolia / C. tora seeds; J Ethnopharmacol 2023) | senna kidney_disease and cardiac_glycosides |

Both name the subject (cascara bark; MeSH "senna plant") but support none of the claims they were
cited for. The subject-only overlap check in verify_interaction_rules_citations.py passed both.

## Replacement sources

- **EU herbal monograph, Rhamnus purshiana DC., cortex** — EMA/HMPC/726270/2016, Final Rev.1, adopted
  6 May 2020. `https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-rhamnus-purshiana-dc-cortex-revision-1_en.pdf`
  - 4.3: contraindicated in "Pregnancy and lactation".
  - 4.4: "Patients taking cardiac glycosides, antiarrhythmic medicinal products, medicinal products
    inducing QT-prolongation, diuretics, adrenocorticosteroids or liquorice root, have to consult a
    doctor"; "Patients with kidney disorders should be aware of possible electrolyte imbalance."
  - 4.5: "Hypokalaemia (resulting from long-term laxative abuse) potentiates the action of cardiac
    glycosides and interacts with antiarrhythmic medicinal products. Concomitant use with diuretics,
    adrenocorticosteroids and liquorice root may enhance loss of potassium."
  - 4.6: pregnancy contraindicated "because of experimental data concerning a genotoxic risk of
    several anthranoids, e.g. emodin and aloe-emodin"; lactation contraindicated because "active
    metabolites, such as rhein, were excreted in breast milk in small amounts".
  - 4.8: "Long term use may lead to water and electrolyte imbalance and may result in albuminuria and
    haematuria." 4.9: "Chronic ingested overdoses of anthranoid containing medicinal products may lead
    to toxic hepatitis."
  - 5.1: cascarosides "are converted by the bacteria of the large intestine into the active
    metabolites (mainly emodin-9-anthrone)". No prostaglandin/nitric-oxide or uterine statement.
  - 5.3: "several hydroxyl anthracene derivatives were mutagenic and genotoxic in several in vitro
    test systems, however this was not proven in in vivo systems."
- **EU herbal monographs, Senna alexandrina Mill., folium** (EMA/HMPC/625849/2015) **and fructus**
  (EMA/HMPC/228761/2016), both Final Rev.1, adopted 25 September 2018. Sections 4.3–4.6, 4.8 and 4.9
  carry the same wording as cascara above (kidney disorders, hypokalaemia potentiates cardiac
  glycosides, albuminuria/haematuria, pregnancy and lactation contraindicated).
  - folium: `https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-senna-alexandrina-mill-cassia-senna-l-cassia-angustifolia-vahl-folium-revision-1_en.pdf`
  - fructus: `https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-senna-alexandrina-mill-cassia-senna-l-cassia-angustifolia-vahl-fructus-revision-1_en.pdf`
- **NIH LiverTox: Cascara** — NBK548113 (esummary: chapter "Cascara"), last update 23 January 2017.
  Read through the in-app browser (NCBI answers curl with a captcha page). "Cascara is generally safe
  and well tolerated, but can cause adverse events including clinically apparent liver injury when
  used in high doses for longer than recommended periods." "Use of cascara in the recommended doses
  for a limited period of time has been associated with few side effects, most of which are mild and
  transient."
  "With longer term use of high doses of cascara, however, adverse events have been described
  including several cases of clinically apparent liver injury." "Liver injury from long term cascara
  use is rare"; "severe cases with acute liver failure and development of ascites and portal
  hypertension have been described." No rodent or hepatocyte data.
- **LactMed: Cascara Sagrada** — NBK501328 (esummary: "Cascara Sagrada"), last revision 17 May 2021,
  read through the in-app browser.
  "Maternal cascara intake might cause loose stools in some breastfed infants and should be avoided."
  Cascara "was qualitatively detected in the breastmilk of 5 of 10 women".
- **LANOXIN (digoxin) tablet label**, DailyMed setid d91e3646-4c63-4512-ab22-db39c085c4dc, effective
  2024-12-05: "Low body weight, advanced age or impaired renal function, hypokalemia, hypercalcemia, or
  hypomagnesemia may predispose to digoxin toxicity."
- Existing senna sources re-resolved by esummary: NBK547922 = LiverTox "Senna"; NBK501349 = LactMed
  "Senna".

## Regulatory facts

- **67 FR 31125** (FR doc 02-11510, 9 May 2002; PMID 12001972). In 1998 (63 FR 33592) FDA moved aloe,
  bisacodyl, cascara and senna from category I to category III and requested mutagenicity,
  genotoxicity and carcinogenicity data on aloe and cascara. Final conclusion: "Based on the lack of
  data and information and the failure of interested persons to submit any new data from
  carcinogenicity studies, the agency has determined that the stimulant laxative ingredients aloe
  ... and cascara sagrada ... should be deemed not generally recognized as safe and effective",
  reclassified to category II (nonmonograph). The rule covers OTC drug products labeled for laxative
  use. It states no genotoxicity or tumorigenicity finding.
- **21 CFR 172.510(b)** (eCFR versioner API, title 21 current to 2026-09-24): lists "Cascara sagrada |
  Rhamnus purshiana DC" as a natural flavoring substance with no limitation; also lists aloe, senna
  (Alexandria) and rhubarb root. It does not list casanthranol (0 hits), which ADD_CASCARA_SAGRADA
  still aliases; no raw DSLD label mentions casanthranol.

## Identity (GSRS full records)

- **4VBP01X99F** = FRANGULA PURSHIANA BARK: names include CASCARA SAGRADA [MI], RHAMNI PURSHIANAE
  CORTEX, CASCARA BITTERLESS EXTRACT [FHFI]; CAS 8015-89-2; part: bark; parent FRANGULA PURSHIANA
  WHOLE (E9S376T0H5); constituents cascarosides A–F.
- **3SJ3U7J6V2** = Casanthranol: fraction "anthranol glycoside" of the bark; CAS 8024-48-4; USP
  monograph drug. Same parent plant, but a purified fraction, not the bark.

## Measurements

- Raw DSLD labels (15,414 under PharmaGuide_Datasets/staging/brands): 0 carry uniiCode 4VBP01X99F or
  3SJ3U7J6V2; 0 list cascara under otheringredients. Frozen v41 enriched corpus (15,412 products): 23
  cascara products, all active rows.
