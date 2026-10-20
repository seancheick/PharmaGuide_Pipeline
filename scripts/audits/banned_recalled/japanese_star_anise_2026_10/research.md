# Japanese star anise: evidence receipts (2026-10-20)

Entry: `HIGH_RISK_JAPANESE_STAR_ANISE` in `banned_recalled_ingredients.json`. Sources below were read
on 2026-10-20 by an agent (not clinician-reviewed). Applied by `apply.py`; `data_batch.py check
--expect ingredients/HIGH_RISK_JAPANESE_STAR_ANISE` reports 1 entry changed and 0 problems.

## Identity

- **GSRS UNII 96MVO223I9, "ILLICIUM ANISATUM WHOLE"**, fetched as a full record from the GSRS API.
  - structurallyDiverse; Schisandraceae / Illicium / anisatum.
  - Names: Illicium anisatum L., Illicium religiosum, Illicium japonicum, Badianifera anisatum,
    Japanese star anise [HOC].
  - Codes: NCBI Taxonomy 124794, POWO 554492-1, GRIN 19797.
  - `verify_unii.py` reports no mismatch.
- **UMLS CUI C0949938, "Illicium anisatum"** (MSH, semantic type Plant). `verify_cui.py --cui` and
  the file run both report VERIFIED. The worktree has no `.env`, so the UMLS key was loaded from the
  main checkout's `.env`. Without it the verifier reports every CUI as "not found", including the
  existing star anise C0949939.
- **Trap:** a GSRS name search for "Japanese star anise" returns STAR ANISE (XKC1657P78, Illicium
  verum), and that record lists "ILLICIUM ANISATUM [HPUS]" as a synonym. Identity here comes from
  the Illicium anisatum record, never from a name search.
- **Aliases:** "japanese star anise", "illicium anisatum", "illicium religiosum" and "illicium
  japonicum". All are GSRS names; the 2002 English order (below) defines Japanese Star Anise with
  the same synonyms. Left out:
  - "shikimmi" and "skimmi": the "skimmi" stem also names Skimmia, a different genus.
  - "shikimi": UMLS maps it to an unrelated protein.

## Sources

- **FDA news release P03-67 (2003-09-10)**, archived at
  `web.archive.org/web/20050115085515/http://www.fda.gov/bbs/topics/NEWS/2003/NEW00941.html`.
  - Japanese star anise "has long been recognized as toxic in many countries" and "should be used
    for decorative purposes only".
  - FDA considers Chinese star anise GRAS as a spice or flavoring, and "Japanese star anise is not
    GRAS".
  - The two cannot be distinguished visually once dried or processed.
  - FDA would monitor imports so that Japanese star anise is not labeled for food use.
  - This is an advisory, not a ban.
- **PMID 22484123** (Shen 2012): anisatin in Japanese star anise "can cause epilepsy, hallucinations,
  and nausea"; its signal is typically more than 1000 times larger in Japanese than in Chinese star
  anise.
- **PMID 12014240** (Biessels 2002, Dutch; title only, no abstract): "Epileptic seizure after a cup
  of tea: intoxication with Japanese star anise."
- **PMID 12617067** (Vandenberghe 2003, French; title only): a first generalized tonic-clonic seizure
  after ingestion of Japanese star anise.
- `verify_all_citations_content.py --changed-since origin/main`: 3 of 3 PMIDs match.

## Status decision

- **Not `banned`.** No current prohibition was found.
  - Commission Decision 2002/75/EC (special conditions on star anise imports) is "No longer in
    force, Date of end of validity: 11/08/2003" according to EUR-Lex.
  - The Food (Star Anise from Third Countries) (Emergency Control) (England) Order 2002 (SI
    2002/334) implemented that decision. It barred importing Japanese star anise for human
    consumption, but legislation.gov.uk shows only its original version and its basis has expired,
    so it is not cited as current.
  - FDA's 2003 release is an advisory. Under Sean's D10 standard (2026-09-26), an advisory is not a
    ban.
- **`high_risk`, `legal_status_enum: under_review`.** A toxic, non-GRAS plant with documented
  seizures and no food use. The US row is `under_review`, because no source gives a final legal
  classification for supplements.
- **Copy:** "Do not use it", matched to the risk. Japanese star anise has no supervised or
  beneficial use, and FDA restricts it to decorative use. `test_safety_copy_production`'s strict
  validator and the copy-versus-evidence check (Q64) pass.

## Behavior

- **Before:** a row named Japanese star anise or Illicium anisatum took the GRAS `star_anise`
  identity whenever DSLD filed it under the group "Star Anise", and stayed unmapped otherwise. In
  both cases it got no warning.
- **After:** the row matches this entry. Its safety gate is CAUTION (B0_HIGH_RISK_SUBSTANCE) and
  `product_safety_status` is `caution`, and it no longer takes the `star_anise` identity.
  - On a single-ingredient label, quality is `not_scored`, because the label has no scorable active.
  - Chinese star anise rows ("Star Anise extract", "Chinese Star Anise", "Illicium verum fruit
    extract") are unchanged: still `star_anise` with `no_known_catalog_concern`.
  - Pinned by `scripts/tests/test_japanese_star_anise_high_risk_20261020.py`. Before the entry it
    had 7 failures, with the 3 controls passing; after, 10 of 10 pass.
- **Corpus:** no label in `~/Downloads/PharmaGuide_Datasets/staging/brands` names Illicium anisatum,
  Japanese star anise, Illicium religiosum or Illicium japonicum (raw census for "illicium",
  "anisatum", "star anise" and "badian"). This is a dormant guard.
- **Replay:** 18 labels (the 10 star anise products plus 8 controls), main `e55b6ccef` against this
  branch, `snapshot --full --blob`: 0 changed. Receipts are in
  `~/pg_quality/star_anise_safety_20261020/replay_jsa/`.
