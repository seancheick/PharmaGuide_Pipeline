# Upper-limit bound Daily Values (`daily_values.json::upper_limit_bound_dvs`)

Added November 4, 2026 under the integrator's ruling: a printed %DV can rule out an excess against an upper limit, never show one. Read directly from the sources on that date.

- Current: 21 CFR 101.9(c)(8)(iv), [2024 edition](https://www.govinfo.gov/content/pkg/CFR-2024-title21-vol2/xml/CFR-2024-title21-vol2-sec101-9.xml), column "Adults and children ≥ 4 years".
- Pre-2016: 21 CFR 101.9(c)(8)(iv), [2015 edition](https://www.govinfo.gov/content/pkg/CFR-2015-title21-vol2/xml/CFR-2015-title21-vol2-sec101-9.xml). Its table isn't split by group, so these apply to the adult row only. Other target groups stay held.

Values are in the limit's own unit from `rda_optimal_uls.json`. Bound is the higher of the two.

| Canonical id | Current, as printed | Pre-2016, as printed | Bound | Limit unit |
|---|---|---|---|---|
| calcium | 1,300 mg | 1,000 mg | 1,300 | mg |
| iron | 18 mg | 18 mg | 18 | mg |
| vitamin_a | 900 mcg RAE | 5,000 IU = 1,500 mcg RAE | 1,500 | mcg RAE |
| vitamin_c | 90 mg | 60 mg | 90 | mg |
| vitamin_d | 20 mcg | 400 IU = 10 mcg | 20 | mcg |
| vitamin_e | 15 mg = 30 mg all rac | 30 IU = 27.3 mg | 30 | mg alpha-tocopherol |
| vitamin_b3_niacin | 16 mg NE | 20 mg | 20 | mg NE |
| vitamin_b6_pyridoxine | 1.7 mg | 2.0 mg | 2 | mg |
| vitamin_b9_folate | 400 mcg DFE | 400 mcg = up to 680 mcg DFE | 680 | mcg DFE |
| phosphorus | 1,250 mg | 1,000 mg | 1,250 | mg |
| iodine | 150 mcg | 150 mcg | 150 | mcg |
| magnesium | 420 mg | 400 mg | 420 | mg |
| zinc | 11 mg | 15 mg | 15 | mg |
| selenium | 55 mcg | 70 mcg | 70 | mcg |
| copper | 0.9 mg | 2.0 mg | 2,000 | mcg |
| manganese | 2.3 mg | 2.0 mg | 2.3 | mg |
| molybdenum | 45 mcg | 75 mcg | 75 | mcg |
| chloride | 2,300 mg | 3,400 mg | 3,400 | mg |

Conversions, none invented here:
- Vitamin A: 0.3 mcg RAE per IU retinol, `unit_conversions.json::vitamin_a_retinol`. Total activity, so it also bounds the preformed share.
- Vitamin E: 1 mg alpha-tocopherol = 2 mg all rac, current 101.9(c)(8)(iv) note 4. 1,100 IU synthetic = 1,000 mg, `rda_optimal_uls.json` note.
- Folate: 1 mcg folic acid = 1.7 mcg DFE, the conversion the stored 1,700 mcg DFE limit uses. The pre-2016 400 mcg could be all folic acid.

Agent review. The 13 records in `nutrients` are unchanged, so unit repair reads what it read before.
