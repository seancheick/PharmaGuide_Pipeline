# Metformin and levothyroxine: proposal for Dr. Pham

Status: **proposal only. Nothing here is applied, and no mapping has changed.** Her review (E5) said the packet did not specify the class changes, so she could not approve one. This names them, by RxCUI, inside the boundaries she set. RxNorm lists were read from RxNav on 2026-11-03.

The existing reviewed copy and caution severity stay as they are: metformin and vitamin B12 (`DEP_METFORMIN_VITAMINB12`), and levothyroxine with calcium and iron (`DSI_LEVOTHYROXINE_CALCIUM`, `DSI_LEVOTHYROXINE_IRON`, `DEP_LEVOTHYROXINE_CALCIUM`, `DEP_LEVOTHYROXINE_IRON`).

## What happens today

- These rows are keyed to the ingredient RxCUI: metformin 6809, levothyroxine 10582.
- `MedicationClassBridge.resolve` matches on the selected, generic and ingredient RxCUIs. A brand or combination reaches them only when the online lookup returned its ingredients. The offline alias list holds only Motrin.
- Metformin 6809 is in `class:diabetes_meds`. Rules gate on `hypoglycemics_high_risk`, `hypoglycemics_lower_risk` and `hypoglycemics_unknown`, and no crosswalk connects them. So those gates don't fire from the medication alone.
- Levothyroxine 10582 is in no class. Rules gate on `thyroid_medications`, so those gates don't fire from the medication alone either.

## Part 1: identity, which medicines count as metformin or levothyroxine

This adds offline aliases to the ingredient, so the existing reviewed rows also fire when the online lookup fails. It adds no class and no new warning text.

### Metformin, aliased to 6809

| RxCUI | Concept | Type | Proposed | Products in RxNorm |
|---|---|---|---|---|
| 1372692 | Kazano | BN | Yes | 2 |
| 1372706 | Jentadueto | BN | Yes | 5 |
| 1372730 | Kombiglyze | BN | Yes | 3 |
| 1372738 | Janumet | BN | Yes | 5 |
| 151827 | Glucophage | BN | Yes | 4 |
| 1545151 | Invokamet | BN | Yes | 8 |
| 1592713 | Xigduo | BN | Yes | 5 |
| 1664316 | Synjardy | BN | Yes | 8 |
| 1992686 | Segluromet | BN | Yes | 4 |
| 2359280 | Trijardy | BN | Yes | 4 |
| 2677156 | Zituvimet | BN | Yes | 5 |
| 405304 | Riomet | BN | Yes | 1 |
| 602411 | Actoplus Met | BN | Yes | 2 |
| 645109 | Glumetza | BN | Yes | 2 |
| 1007411 | chlorpropamide / metformin | MIN | No, no product | 0 |
| 1008476 | metformin / ropinirole | MIN | No, no product | 0 |
| 1043562 | metformin / saxagliptin | MIN | Yes | 6 |
| 1243019 | linagliptin / metformin | MIN | Yes | 10 |
| 1368384 | alogliptin / metformin | MIN | Yes | 4 |
| 1486436 | dapagliflozin / metformin | MIN | Yes | 10 |
| 1545149 | canagliflozin / metformin | MIN | Yes | 16 |
| 1664314 | empagliflozin / metformin | MIN | Yes | 16 |
| 1992684 | ertugliflozin / metformin | MIN | Yes | 8 |
| 2117292 | dapagliflozin / metformin / saxagliptin | MIN | No, no product | 0 |
| 2281864 | empagliflozin / linagliptin / metformin | MIN | Yes | 8 |
| 285129 | glyburide / metformin | MIN | Yes | 3 |
| 352381 | glipizide / metformin | MIN | Yes | 3 |
| 607999 | metformin / pioglitazone | MIN | Yes | 4 |
| 614348 | metformin / rosiglitazone | MIN | Yes | 5 |
| 729717 | metformin / sitagliptin | MIN | Yes | 20 |
| 802646 | metformin / repaglinide | MIN | Yes | 2 |
| 235743 | metformin hydrochloride | PIN | Yes | 134 |

Not included: any diabetes medicine without metformin in it (for example sitagliptin alone). `class:diabetes_meds` is not used as the selector, so metformin's B12 rule doesn't spread to the rest of that class.

### Levothyroxine, aliased to 10582

| RxCUI | Concept | Type | Proposed | Products in RxNorm |
|---|---|---|---|---|
| 1189101 | Thyro-Tabs | BN | Ask her | 9 |
| 1421051 | ThyroKare | BN | Ask her | 1 |
| 217006 | Euthyrox | BN | Yes | 11 |
| 217996 | Levo-T | BN | Yes | 12 |
| 218002 | Levoxyl | BN | Yes | 11 |
| 224920 | Synthroid | BN | Yes | 12 |
| 2473277 | Thyquidity | BN | Yes | 1 |
| 2626051 | Ermeza | BN | Yes | 1 |
| 2675679 | Thyrocryn | BN | Ask her | 1 |
| 284910 | Unithroid | BN | Yes | 12 |
| 57213 | Thyrolar | BN | Ask her | 3 |
| 728656 | Tirosint | BN | Yes | 30 |
| 1007890 | levothyroxine / potassium iodide | MIN | No, no product | 0 |
| 465675 | levothyroxine / liothyronine | MIN | Ask her | 8 |
| 1372638 | levothyroxine sodium anhydrous | PIN | Yes | 0 |
| 40144 | levothyroxine sodium | PIN | Yes | 168 |

Not included: liothyronine 10814, its brands, and desiccated thyroid. She said identical timing instructions should not transfer to every thyroid drug without evidence.

## Part 2: class gates, which go beyond calcium, iron and B12

A class mapping would make the medication alone fire every rule below. She reviewed only the interactions named above, so these are listed for her decision and are not proposed by default.

### Metformin into `hypoglycemics_lower_risk`

The app's own option label already places metformin here ("Metformin, Ozempic, etc."), so these rules already reach someone who picked that option. Mapping would reach anyone who only added the medication.

| Rule | Severity | Evidence |
|---|---|---|
| `RULE_INGREDIENT_ALOE_VERA` | monitor | theoretical |
| `RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES` | monitor | probable |
| `RULE_IQM_BERBERINE_DIABETES` | caution | established |
| `RULE_IQM_BITTER_MELON_DIABETES` | monitor | probable |
| `RULE_IQM_CHROMIUM_GLUCOSE` | monitor | probable |
| `RULE_IQM_CINNAMON_GLUCOSE` | monitor | probable |
| `RULE_IQM_FENUGREEK_DIABETES` | monitor | probable |
| `RULE_IQM_GLUCOMANNAN_DIABETES` | monitor | probable |
| `RULE_INGREDIENT_GINSENG` | monitor | probable |
| `RULE_IQM_GYMNEMA_DIABETES` | monitor | probable |
| `RULE_IQM_PSYLLIUM_DIABETES` | monitor | established |
| `RULE_IQM_VANADIUM_DIABETES` | monitor | probable |
| `RULE_IQM_NIACIN_DIABETES` | caution | established |
| `RULE_IQM_TRIBULUS_METABOLIC` | monitor | limited |
| `RULE_IQM_BLACK_SEED_OIL_DIABETES` | monitor | probable |
| `RULE_IQM_DANDELION_KIDNEY` | monitor | theoretical |
| `RULE_IQM_STINGING_NETTLE_DIABETES` | monitor | probable |
| `RULE_IQM_OLIVE_LEAF_DIABETES` | monitor | probable |

### Levothyroxine into `thyroid_medications`

| Rule | Severity | Evidence |
|---|---|---|
| `RULE_IQM_CHROMIUM_GLUCOSE` | caution | probable |
| `RULE_IQM_GLUCOMANNAN_DIABETES` | caution | theoretical |
| `RULE_IQM_IODINE_PREGNANCY_EXCESS` | monitor | probable |
| `RULE_IQM_IRON_HYPERTENSION` | caution | established |
| `RULE_IQM_MAGNESIUM_HYPERTENSION` | caution | probable |
| `RULE_IQM_CALCIUM` | caution | established |
| `RULE_IQM_ZINC` | caution | theoretical |
| `RULE_INGREDIENT_GENISTEIN__THYROID` | caution | probable |
| `RULE_IQM_BACOPA_THYROID` | caution | theoretical |
| `RULE_IQM_ALCAR_THYROID` | caution | theoretical |
| `RULE_IQM_L_TYROSINE_THYROID` | caution | theoretical |

## Questions for Dr. Pham

1. Metformin aliases as marked "Yes". Approve, or strike any?
2. Levothyroxine aliases as marked "Yes". Approve, or strike any?
3. Levothyroxine and liothyronine combinations (465675, Thyrolar 57213) contain levothyroxine, but she said not to transfer timing instructions to every thyroid drug. Include them for calcium and iron, or leave them out?
4. Thyro-Tabs 1189101, ThyroKare 1421051 and Thyrocryn 2675679 look like veterinary products from their RxNorm entries. That isn't verified, so they are held. Leave them out?
5. Aliasing to 10582 also carries the other rows keyed to it (coffee, magnesium, soy), not only calcium and iron. Is that acceptable? Those rows already fire for anyone whose ingredient lookup succeeded.
6. Metformin into `hypoglycemics_lower_risk`: yes, no, or only named rules?
7. Levothyroxine into `thyroid_medications`: yes, no, or only named rules?

A code test fails if a clinical crosswalk is added without sign-off, on purpose. It stays in place until she answers.
