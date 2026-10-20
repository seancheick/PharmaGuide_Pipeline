# Star anise is not anise — receipt (2026-10-20)

Batch: `scripts/data/ingredient_quality_map.json` entry `anise`; remove the aliases "star anise" and
"illicium verum" from 'anise (unspecified)' (added in cc2b80699, 2026-02-22). No entry, form, identifier or
score is added.

| Item | Verified by content (GSRS API, 2026-10-20) |
|---|---|
| IQM `anise` (UNII 21C2F5E8RE) | GSRS "ANISE", structurallyDiverse plant, part seed, parent substance PIMPINELLA ANISUM WHOLE (HO63CL229O); names include PIMPINELLA ANISUM SEED/FRUIT, ANISEED. |
| botanical `star_anise` (UNII XKC1657P78) | GSRS "STAR ANISE", plant, part seed, parent substance ILLICIUM VERUM WHOLE (52JDS841PX); names include ILLICIUM VERUM SEED, CHINESE STAR ANISE. |

Verdict: different plants (Pimpinella anisum, Apiaceae; Illicium verum, Schisandraceae). The repo already owns
star anise as botanical_ingredients `star_anise` (note: "distinguish from toxic I. anisatum"), so the false aliases
are removed and star anise rows resolve there.

Caution for future curation: GSRS's STAR ANISE record also lists the homeopathic synonym
"ILLICIUM ANISATUM [HPUS]" (Japanese star anise, the neurotoxic species). That synonym list must not be used to map
identity.

Not changed (follow-up): the pipeline has no star anise or Illicium anisatum interaction or warning rule. Adding
one needs its own sourced safety entry.
