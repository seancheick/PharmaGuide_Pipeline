# M. Recent-fix regression report — do the window's fixes survive together on HEAD?

Method: every Tier 1 fix that named a product was checked on the HEAD replay/probe of that product (or a sibling in the sample); pairs that touch the same owner were checked for supersession in `commits/T1_records.md`.

| Fix | Claim | On HEAD | Survives? |
|---|---|---|---|
| a7351548 row-notes form | 311733/306183/306235/307773/311734/67304 read `bcaa 2:1:1` | probe: all six + 295064 read 2:1:1 (bio 15); instantized-named labels read `instantized bcaas`; 31148/59952 unspecified | yes; register count off by one (295064) |
| c6520535 generic BCAA → unspecified | 31148 unspecified 10 | yes | yes |
| 1eab691f re-read under row parent | Maca/Sea buckthorn/Gotu kola released; D21 species held | 310608/311536/330285/307569 held at HEAD (`disclosed_form_unmapped`) | yes |
| 2df4bed2 banned check reads label evidence | 311187 Frangula: B0 penalty | Safety/Hygiene 0, WATCH_FRANGULA | yes |
| 32718da7 designer steroids ship blocked | 33360 | suppressed_safety, BANNED_DIMETHANDROSTENOL critical | yes |
| d36b6052 / 0433c386 high-risk & sole-active additives ship | 182627 scored with RISK_BITTER_ORANGE; 252699 mannitol scored with ADD_SUGAR_ALCOHOLS | 58.3 with both bitter-orange warnings; 56.5 with low additive warning | yes |
| 24bebc01 safety-flag subjects | 182627 keeps bitter-orange hypertension rule | RISK_BITTER_ORANGE + BANNED_BITTER_ORANGE cards | yes |
| 5c9996f4 daily exposure (A10/B2) | 312819 HMB 3.5 → 12.8; 331143 etc. | 312819 Dose 12.8 at HEAD (pre-window 3.5) | yes |
| 25decbf5 per-column merge (A13) | 77225 DHA 200 mg (not carrier 600 mg) | scoring rows: dha 200 mg, algae_oil 600 mg separate; Dose 4.0 | yes |
| 33ba3973 activity units disclosed (A15) | 82372 Transparency +1.5 | Transparency 15/15 | yes |
| 7ee85a26 / a6222c7d P4 beta-carotene | caution ≥ 7,500 mcg RAE | 224794 (7,500) and 213472 (7.5 mg → RAE) caution; 297614 informational | yes; 213472 depends on cb419f41's RAE reading (label NOT ESTABLISHED) |
| 9aeb7fbc / 2da82226 USP attribution | 9080 iron keeps USP via override | Verification 15/15 | yes |
| 8fbfd601 no Dose credit for premium-form count | — | `multi_form_bonus` absent on HEAD sample (present pre-window on 2 products) | yes |
| c85b0d97 / 72a301fc / 4a761c30 probiotic | single strain full credit | 19067 (1 strain): Evidence 6 → 9, Dose 14.5 → 18.2 | yes |
| 1929d398 transparency rescale | multi 15/15 on full disclosure | 180316/270561/12012 Transparency 15.0 | yes |
| f2efb793 authority panel | complete panels 20/20 | 180316, 3565, 270561 Evidence 20 | yes — but display state gap (RR-11) |
| dd2cf1ff/dda033c7/afb71c6c/6a3ab83f parent-relative forms | best form = 15/15 | 336348, 252451, 288632 | yes — RR-01 |
| e9f1a54c omega minimum basis | variable-serving omega scored at min | 259484 Dose 20 (fixed 1/day) | yes — RR-03 conflict with Task 2 |
| ff77935e / 4c4400c1 owner scoping | adjuncts do not carry Evidence | 1179/14168/282638/… fell to 0 not-covered | yes — RR-05 |
| 28178b54 FiberSMART → resistant dextrin, scored | 233404 scored | scored 40.4 but Formulation 0 | yes for identity; RR-07 hijack |
| 88ef0a98 → eb3eb510 plant parts | nettle root BP only; dandelion root diuretic | HEAD twin forms + tests consistent | yes (checked, no regression) |
| ce8c38fa → 7dbbf677 registry | subject registry holds the id | stamp fixed at source; fallback remains | yes (redundant fallback, L-6) |
| 05c2ec25 → 14bdcede revert, b999a29b → c480dcac revert | net zero | — | reverted pairs, no residue |

Conflicts found: RR-03 (basis), RR-01 vs RECONCILIATION C1, RR-02 vs C9, RR-05 (owner scoping × zero-in-total). Accidental reverts: none found. Schema drift from the window: none on the core; blob gained `dailyValue` on rows (declared? — verified by the row-shape gate passing in the suite).
