# Schema v5.0.0 Field Reference

## Valid Enums

### `status`
| Value | Trigger | Scoring impact |
|---|---|---|
| `banned` | FDA/DEA ban, controlled substance, drug exclusion rule | FAIL (disqualify) |
| `recalled` | FDA recall, product scope | FAIL (disqualify) |
| `high_risk` | FDA warning letter, NDI rejection, contaminant above threshold | -10 points |
| `watchlist` | International bans, restricted use, FDA monitoring | -5 points |

### `legal_status_enum`
| Value | When to use |
|---|---|
| `adulterant` | Illegal pharmaceutical spiked into supplement |
| `controlled_substance` | DEA Schedule I-V |
| `not_lawful_as_supplement` | Drug exclusion rule (21 USC 321(ff)(3)(B)) or not a dietary ingredient |
| `restricted` | Legal with restrictions in some jurisdictions |
| `banned_federal` | Outright federal FDA/DEA ban |
| `banned_state` | Banned in specific states (requires `jurisdictions[]`) |
| `high_risk` | Legal but high clinical risk |
| `wada_prohibited` | WADA prohibited in sports |

### `clinical_risk_enum`
| Value | When to use |
|---|---|
| `critical` | Life-threatening, death risk, severe cardiovascular/CNS events |
| `high` | Serious harm potential — hospitalization level |
| `moderate` | Significant risk — adverse events expected |
| `low` | Minor risk — caution only |
| `dose_dependent` | Risk changes significantly by dose — applies to dual-use botanicals |

### `match_mode`
| Value | When to use |
|---|---|
| `active` | Entry participates in ingredient matching (default for all new entries) |
| `disabled` | Entry skipped by matcher (class-level entries, umbrella categories) |
| `historical` | Kept for reference, no longer matched (terminated product-specific recalls) |

### `entity_type`
| Value | When to use |
|---|---|
| `ingredient` | A specific substance (most common) |
| `contaminant` | Adulterant/spiking agent illegally added |
| `class` | Drug class or umbrella group (set `match_mode: disabled`) |
| `product` | Specific product (rare — use `recall_scope` instead) |

### `match_rules.match_type`
| Value | When to use |
|---|---|
| `exact` | Default for most substances |
| `token` | Broad chemical classes where partial matching is acceptable |
| `alias` | When substance is only known by aliases |

### `match_rules.confidence`
| Value | When to use |
|---|---|
| `high` | Exact pharmaceutical name match |
| `medium` | Alias-based match |
| `low` | Token/partial match |

## `source_category` Valid Values

```
pharmaceutical_adulterants     # Prescription drugs spiked into supplements
synthetic_stimulants           # DMAA, DMHA, ephedrine analogs
anabolic_agents                # Steroids, prohormones
sarms                          # Selective androgen receptor modulators
controlled_substances          # DEA Schedule I-V
heavy_metals                   # Lead, arsenic, mercury, cadmium
prescription_drugs             # Rx drugs not spiked but excluded by drug exclusion rule
banned_botanicals              # Herbs banned by FDA (aristolochic acid, etc.)
synthetic_cannabinoids         # Synthetic THC analogs
laxatives_adulterants          # Phenolphthalein, senna overdose in weight-loss products
diuretics_adulterants          # Furosemide, hydrochlorothiazide in supplements
```

## `class_tags` Valid Values

```
pharmaceutical_adulterants
drug_nsaid
drug_diabetes
drug_cardiovascular
drug_pde5_inhibitor
drug_antidepressant
drug_sedative
drug_opioid
drug_stimulant
anabolic_steroids
sarms
heavy_metals
synthetic_stimulants
controlled_substance
banned_botanical
diuretics
laxatives
spiking_agents
```

## References `evidence_grade` Values

| Grade | Meaning |
|---|---|
| `R` | Regulatory source (FDA, DEA, WADA — primary authority) |
| `A` | Randomized controlled trial or meta-analysis |
| `B` | Cohort study, case series, strong observational |
| `C` | Case report, expert opinion, in vitro |

## Complete Required Field Checklist

```
id                          Required, unique, SCREAMING_SNAKE prefix
standard_name               Required, Proper Case
aliases                     Required, list (min 1)
reason                      Required, 1 sentence
status                      Required, enum: banned|recalled|high_risk|watchlist
class_tags                  Required, list (min 1)
match_rules                 Required object:
  .exclusions               list (can be empty [])
  .case_sensitive           bool
  .priority                 int (1=highest)
  .match_type               enum: exact|token|alias
  .confidence               enum: high|medium|low
  .negative_match_terms     list (can be empty [])
legal_status_enum           Required, enum
clinical_risk_enum          Required, enum
jurisdictions               Required, list (min 1):
  .region                   string
  .level                    enum: federal|state|international
  .status                   enum: banned|restricted
  .effective_date           ISO date or null
  .source                   object with type, citation, accessed_date
  .jurisdiction_type        enum: country|state|region
  .jurisdiction_code        ISO 3166 (US, CA, GB, etc.)
  .last_verified_date       ISO date
references_structured       Required, list (min 1):
  .type                     enum: fda_enforcement|fda_advisory|pubmed|...
  .title                    string
  .url                      string or omit if no URL
  .evidence_grade           enum: R|A|B|C
  .date                     ISO date
  .supports_claims          list
  .evidence_summary         string (1-2 sentences)
source_category             Required, string
entity_type                 Required, enum
review                      Required object:
  .status                   enum: validated|needs_review|pending
  .last_reviewed_at         ISO date
  .next_review_due          ISO date (6 months from today for new)
  .reviewed_by              string
  .change_log               list of {date, change, by}
supersedes_ids              null or list of old IDs this replaces
regulatory_date             Required, ISO date YYYY-MM-DD
regulatory_date_label       Required, human label string
match_mode                  Required, enum: active|disabled|historical
recall_scope                null (ingredient-level) or string (product name)
```
