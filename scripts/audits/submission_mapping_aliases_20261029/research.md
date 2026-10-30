# Submission mapping aliases — 2026-10-29

Probe: the 10 transcribed submissions (S13–S16, S18–S23) run through clean → enrich → score
(`replay.py snapshot --full`, origin/main 0c49a381c). Seven scored with nothing unmapped; inactives all
resolved (sweeteners and syrups match `harmful_additives`). Three were blocked by the completeness gate.
Agent review (Claude Opus 5.5); no clinician review needed (aliases onto existing, already-reviewed forms).

| Printed row (label) | Blocker | Owner form | Identity check | Aliases added |
|---|---|---|---|---|
| Folate (as 6S-5-Methyltetrahydrofolate calcium salt) — C4 Sport (S22) | `disclosed_form_unmapped` | `vitamin_b9_folate` / `metafolin` (calcium salt of L-5-MTHF) | PubChem CID 135564391 Levomefolate Calcium, IUPAC (6S) | `6S-5-Methyltetrahydrofolate calcium salt` |
| Creatine Nitrate (as NO3-T®) — C4 Sport (S22) | `disclosed_form_unmapped` | `creatine_monohydrate` (Creatine parent) / `creatine nitrate` | PubChem CID 25231507 Creatine Nitrate; label prints NO3-T® as the creatine nitrate trademark (ThermoLife) | `NO3-T`, `NO3-T creatine nitrate` |
| Citrulline Malate 2:1 — Woke AF Miami (S23) | `identity_conflict` (unmapped at Clean) | `l_citrulline` / `l-citrulline malate` | PubChem CID 162762 Citrulline malate; form note already covers stated ratios | `citrulline malate 2:1`, `l-citrulline malate 2:1` |

Result on this branch: S22 not_scored → scored 58.6; S23 not_scored → scored 67.7; the other 8 unchanged.
Corpus blast radius: 0 cleaned corpus products contain any of the new alias strings.
Not in this batch: S14 (RenewLife) strain identities and printed CFU totals — handed to the
probiotic-detection session (brand-named blend headers).
