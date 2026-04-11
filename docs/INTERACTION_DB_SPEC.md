# PharmaGuide Interaction Database — Engineering Specification

**Document version:** 1.0.0  
**Status:** Draft — pending M0 golden dataset review  
**Author:** Engineering  
**Last updated:** 2026-04-10  
**Target release:** M4 (Flutter widget integration)

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Data Sources & Integration Strategy](#2-data-sources--integration-strategy)
3. [Database Schema](#3-database-schema)
4. [Matching Strategy](#4-matching-strategy)
5. [Severity Scale & Verdict Integration](#5-severity-scale--verdict-integration)
6. [Flutter Integration Plan](#6-flutter-integration-plan)
7. [Build Plan with Milestones](#7-build-plan-with-milestones)
8. [Open Questions & Risks](#8-open-questions--risks)
9. [Out of Scope — Do Not Confuse with v1](#9-out-of-scope--do-not-confuse-with-v1)

---

## 1. Purpose & Scope

### 1.1 Why We Are Building This

PharmaGuide currently scores supplements on ingredient quality, safety, and clinical evidence. That score is product-global — it applies the same way to every user. The interaction feature adds user-scoped context: the same supplement can carry materially different risks depending on what medications the user is already taking, or what other supplements are in their stack.

A user on warfarin asking about fish oil is a qualitatively different safety question than a user with no medications asking the same thing. Today we have no way to surface that. This spec defines the database, matching logic, schema, and Flutter integration for closing that gap at the MVP level.

### 1.2 What This Feature Covers

| Interaction type | Example | Included |
|---|---|---|
| Supplement ↔ Drug | Fish oil + warfarin (anticoagulant potentiation) | Yes |
| Supplement ↔ Supplement | St. John's Wort + 5-HTP (serotonin syndrome risk) | Yes |
| Drug ↔ Drug | Warfarin + aspirin (bleeding risk) | Yes — limited, DrugBank M3 |
| Food ↔ Drug | Grapefruit + statins (CYP3A4 inhibition) | Yes — high-value subset only |
| Food ↔ Supplement | Calcium-rich foods + thyroid medications | Yes — high-value subset only |

The primary value proposition for v1 is **supplement ↔ drug** and **supplement ↔ supplement**, with a limited set of the most clinically important food ↔ drug interactions included as first-class entries rather than a separate system.

### 1.3 What This Feature Does NOT Cover

The following are explicitly out of scope for v1 to avoid scope creep and scope confusion. They are documented in Section 9 with rationale.

- Pharmacogenomic / gene-variant interactions (CYP2D6, CYP2C9 polymorphisms)
- Dose-dependent interaction modeling (risk varies by exact mg)
- Time-of-day separation scheduling (take 4 hours apart recommendations)
- Provider-facing clinical decision support
- Interaction with the arithmetic quality score — the score is product-global; interactions are user-scoped
- Drug ↔ Drug coverage at scale (available in M3 via DrugBank paid tier)
- Pregnancy/lactation-specific interaction flags (distinct feature, deferred)

---

## 2. Data Sources & Integration Strategy

### 2.1 Source Overview and Priority

Integration priority is driven by coverage quality, licensing burden, and build effort. The table below summarizes the five core sources in descending priority order.

| Priority | Source | Covers | License | Effort |
|---|---|---|---|---|
| 1 | supp.ai | Supp ↔ Drug | Academic open | Low — bulk import |
| 2 | NIH ODS Fact Sheets | Supp ↔ Drug (subset) | Public domain | Medium — scrape + curate |
| 3 | NIH LiverTox | Supp/Drug → DILI | Public domain | Medium |
| 4 | ChEMBL (existing audit) | Mechanism of action | CC BY-SA 3.0 | Low — already integrated |
| 5 | UMLS RxNorm | Identifier linkage | UMLS license required | Medium |
| 6 | DrugBank | Drug ↔ Drug | Commercial | High — M3 |

### 2.2 supp.ai (Priority 1)

**What it is:** A curated, machine-learning-assisted database of supplement–drug interactions built by the Allen Institute for AI. The dataset covers approximately 1,600 supplement-drug pairs extracted from clinical literature, with severity and mechanism annotations.

**Fields available in the supp.ai dataset:**
- Supplement name (string, needs normalization to `canonical_id`)
- Drug name (string, needs RXCUI lookup)
- Interaction type (descriptive, maps to our `mechanism` field)
- Evidence level (maps to our `evidence_level` enum)
- Source URL + PubMed IDs where available

**Import strategy:**
1. Download the supp.ai TSV dataset from https://supp.ai (academic download link).
2. Run `scripts/api_audit/normalize_suppai.py` (to be written at M1) to normalize supplement names against `ingredient_quality_map.json` canonical IDs using the existing `rapidfuzz` pipeline.
3. For each supplement name that matches a canonical IQ map entry, write the interaction record to `interactions` with `subject_canonical_id` set.
4. For each drug name, call the UMLS RxNorm API (`/rxcui?name=<drug_name>`) to resolve `object_rxcui`. Log failures to a review queue.
5. Manual review queue for any supp.ai entry where neither the supplement nor the drug resolved automatically.

**Attribution requirement:** supp.ai dataset is academic-open. The app must display "Interaction data partially sourced from supp.ai (Allen Institute for AI)" in the app's data sources disclosure screen. This is a hard requirement before shipping M4.

**Known gap:** supp.ai does not systematically cover supplement ↔ supplement interactions. Those must be sourced from NIH ODS Fact Sheets and manual curation at M0/M1.

### 2.3 NIH ODS Fact Sheets (Priority 2)

**What it is:** The NIH Office of Dietary Supplements publishes per-ingredient fact sheets at ods.od.nih.gov. Each fact sheet contains a "Interactions with Medications" section with clinically reviewed interaction summaries.

**Fields available:**
- Drug class (e.g., "blood thinners", "statins")
- Mechanism description (prose, needs structured extraction)
- Severity signals ("can interfere", "can cause serious problems", "check with healthcare provider")
- Occasionally PMIDs in footnotes

**Import strategy:**
1. Use the existing `scripts/api_audit/` pattern. Write `fetch_ods_interactions.py` that fetches and parses ODS fact sheets for all ingredients in `ingredient_quality_map.json` that have an ODS fact sheet URL.
2. Extract the interactions section with a regex + heuristic parser. This produces semi-structured entries requiring human review before writing to the interactions file.
3. Do not auto-apply. Every ODS-sourced interaction record requires a reviewer sign-off in the `manual_review_queue` before promotion to production.

**Attribution:** Public domain (NIH). No license restriction.

### 2.4 NIH LiverTox (Priority 3)

**What it is:** A database of drug-induced liver injury (DILI) profiles for drugs and herbal products, maintained by NIDDK and NLM. It covers hepatotoxicity likelihood ratings and mechanism notes.

**What we extract from LiverTox:**
- Hepatotoxicity likelihood classification (A/B/C/D/E scale → maps to our `evidence_level`)
- Mechanism of liver injury (mechanism field)
- Drug name → RXCUI linkage via RxNorm
- PMID citations from LiverTox case reports

**Use case:** Creates `object_type = "drug"` or `subject_type = "supplement"` entries with `mechanism = "hepatotoxic potentiation"` for cases where a supplement and drug share hepatotoxic pathways or where a supplement itself has DILI risk that worsens with medications metabolized by the same hepatic route.

**Import strategy:** LiverTox provides a bulk download (XML + JSON). Write `scripts/api_audit/fetch_livertox_interactions.py` to parse the download and generate candidate interaction records. Manual review required before promotion.

### 2.5 ChEMBL Mechanism Data (Priority 4 — Already Partially Available)

**What we already have:** `scripts/api_audit/enrich_chembl_bioactivity.py` already queries ChEMBL for mechanism-of-action data linked to `ingredient_quality_map.json` entries.

**What this adds for interactions:** ChEMBL mechanism data identifies which biological targets a compound acts on (e.g., serotonin transporter inhibition, CYP3A4 inhibition/induction). This enables us to write mechanism-based interaction entries even when direct clinical evidence is thin.

For example: if ChEMBL marks a supplement as a CYP3A4 inhibitor, we can write a theoretical-level interaction entry against any drug in the `drug_classes` lookup table flagged as a CYP3A4 substrate. These receive `evidence_level = "theoretical"` and are treated as informational banners only.

**Integration:** No new import pipeline needed. Extend the existing enrichment audit to extract `mechanism_flag` fields (CYP3A4_inhibitor, serotonin_precursor, anticoagulant_potentiator, etc.) and cross-reference against a small hand-maintained `mechanism_to_drug_class_map.json` table (to be written at M0).

### 2.6 UMLS RxNorm RXCUI (Priority 5 — Identifier Layer)

**What it provides:** RxNorm (part of UMLS) is the authoritative drug identifier registry for US clinical use. RXCUI is the canonical drug concept identifier, analogous to CUI for clinical concepts. It allows us to:
- Identify a drug entered by name and resolve it to a stable RXCUI
- Map RXCUI to drug class (via RxNorm relationship API)
- Match a user's medication entry against interaction DB records

**How to obtain RxCUI for drugs:**
```
GET https://rxnav.nlm.nih.gov/REST/rxcui.json?name=<drug_name>&search=2
```
Response contains `rxnormId` (the RXCUI). No API key required for RxNav (public UMLS service).

**Supplement CUI linkage:** `ingredient_quality_map.json` already contains `cui` and `rxcui` fields for many entries (confirmed above for Vitamin B1: `cui: "C0039840"`, `rxcui: "10454"`). These are the primary identifier for supplement-side matching.

**M2 deliverable:** Run RxNorm enrichment for all ingredients in `ingredient_quality_map.json` that have `cui` but no `rxcui`, and for all drug entries in the interaction DB that were sourced via supp.ai name matching only.

### 2.7 DrugBank (Priority 6 — M3 Only)

**What it provides:** Drug-drug interaction database with ~300K interaction pairs, mechanism annotations, and severity classifications. The free tier (academic XML download) covers a meaningful subset; full coverage requires a commercial license.

**Decision:** Do not integrate DrugBank until M3. The free academic XML is adequate for a first pass at drug-drug interactions for the most common medication classes (statins, SSRIs, anticoagulants, beta-blockers, ACE inhibitors). Commercial license evaluation happens at M3 planning.

**Attribution requirement:** DrugBank free tier requires attribution: "Drug interaction data sourced from DrugBank (https://www.drugbank.com)". Commercial tier has separate terms.

---

## 3. Database Schema

The interaction database lives as a JSON reference file at:
```
scripts/data/drug_nutrient_interactions.json
```

It follows the same `_metadata` contract as all other data files in this pipeline.

### 3.1 Top-Level Structure

```json
{
  "_metadata": {
    "schema_version": "1.0.0",
    "last_updated": "2026-04-10",
    "total_entries": 0,
    "source_breakdown": {
      "supp_ai": 0,
      "nih_ods": 0,
      "livertox": 0,
      "chembl_theoretical": 0,
      "manual_curated": 0,
      "drugbank": 0
    },
    "description": "Drug-nutrient, supplement-supplement, and drug-drug interaction reference database for PharmaGuide v1.",
    "purpose": "user_scoped_interaction_warnings",
    "license_notes": [
      "supp.ai: academic open, attribution required",
      "NIH ODS: public domain",
      "NIH LiverTox: public domain",
      "ChEMBL: CC BY-SA 3.0",
      "DrugBank: commercial license required for full coverage (M3)"
    ],
    "update_frequency": "quarterly",
    "audit_runbook": {
      "validate_command": "python3 scripts/validate_interactions_schema.py scripts/data/drug_nutrient_interactions.json",
      "normalize_suppai_command": "python3 scripts/api_audit/normalize_suppai.py --input data/suppai_download.tsv --output /tmp/suppai_candidates.json",
      "rxnorm_enrich_command": "python3 scripts/api_audit/enrich_rxnorm.py --file scripts/data/drug_nutrient_interactions.json"
    }
  },
  "interactions": [],
  "drug_classes": {},
  "mechanism_flag_map": {}
}
```

### 3.2 Interaction Entry Schema

Each entry in the `interactions` array is a self-contained interaction record. Fields marked **required** must be present for an entry to pass schema validation.

```json
{
  "id": "INTERACTION_SEVERE_FISH_OIL_WARFARIN",

  "subject": "Fish Oil (EPA/DHA)",
  "subject_type": "supplement",
  "subject_canonical_id": "omega_3_fish_oil",
  "subject_cui": "C0016157",
  "subject_rxcui": null,

  "object": "Warfarin",
  "object_type": "drug",
  "object_canonical_id": null,
  "object_cui": "C0043031",
  "object_rxcui": "11289",
  "object_drug_class": "anticoagulants",
  "object_drug_class_rxcui_members": ["11289", "67108", "855314"],

  "mechanism": "Fish oil (EPA/DHA) inhibits platelet aggregation and may potentiate the anticoagulant effect of warfarin, increasing bleeding risk. The effect is dose-dependent but clinically relevant at supplemental doses above 1g/day EPA+DHA.",

  "severity": "moderate",
  "evidence_level": "rct",

  "bidirectional": true,

  "clinical_notes": "INR monitoring is advisable when fish oil supplementation is initiated or dose-changed in patients on warfarin. The FDA and NIH ODS note this interaction explicitly. Not a contraindication but warrants clinical awareness. Most RCTs show modest INR elevation (0.2–0.5 units) at 3–6g/day fish oil.",

  "management_guidance": "Inform prescriber before initiating fish oil supplementation. Monitor INR at first follow-up. Adjust warfarin dose if clinically indicated.",

  "sources": [
    {
      "type": "pubmed",
      "id": "19145785",
      "description": "RCT: fish oil and warfarin INR effect, n=254"
    },
    {
      "type": "pubmed",
      "id": "21735527",
      "description": "Meta-analysis: omega-3 fatty acids and anticoagulation"
    },
    {
      "type": "nih_ods",
      "id": "omega3-HealthProfessional",
      "description": "NIH ODS Omega-3 Fact Sheet for Health Professionals"
    }
  ],

  "flag_name": "INTERACTION_MODERATE_OMEGA3_WARFARIN",

  "subject_standard_names_for_matching": [
    "fish oil",
    "omega-3",
    "omega 3 fatty acids",
    "epa",
    "dha",
    "eicosapentaenoic acid",
    "docosahexaenoic acid"
  ],

  "object_standard_names_for_matching": [
    "warfarin",
    "coumadin",
    "jantoven"
  ],

  "data_provenance": {
    "source": "nih_ods",
    "imported_at": "2026-04-10",
    "reviewed_by": "manual_curation",
    "review_status": "approved",
    "suppai_pair_id": null
  }
}
```

### 3.3 Full Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Stable unique identifier. Format: `INTERACTION_{SEVERITY}_{SUBJECT_SLUG}_{OBJECT_SLUG}`. All caps, underscores. |
| `subject` | string | Yes | Human-readable name of the entity experiencing the effect (usually the supplement). |
| `subject_type` | enum | Yes | `supplement`, `drug`, or `food`. |
| `subject_canonical_id` | string | No | Key in `ingredient_quality_map.json`. Null for drugs as subject or unmatched supplements. |
| `subject_cui` | string | No | UMLS CUI. Format: `C` followed by 7 digits. |
| `subject_rxcui` | string | No | RxNorm RXCUI. Numeric string. Populated for supplements that have pharmacological profiles in RxNorm. |
| `object` | string | Yes | Human-readable name of the entity causing or mediating the effect (usually the drug). |
| `object_type` | enum | Yes | `supplement`, `drug`, or `food`. |
| `object_canonical_id` | string | No | Key in `ingredient_quality_map.json` if object is a supplement. |
| `object_cui` | string | No | UMLS CUI for the object. |
| `object_rxcui` | string | No | RxNorm RXCUI for the object drug. Primary identifier for drug-side matching. |
| `object_drug_class` | string | No | Key in the `drug_classes` lookup table. Enables class-level matching when specific RXCUI is unavailable. |
| `object_drug_class_rxcui_members` | array[string] | No | List of RXCUI values that are members of `object_drug_class`. Redundant for lookup but useful for fast set intersection at match time. |
| `mechanism` | string | Yes | Clinical mechanism explanation. Plain English, 1–4 sentences. No jargon without clarification. |
| `severity` | enum | Yes | `contraindicated`, `severe`, `moderate`, `mild`, `informational`. See Section 5 for full definitions. |
| `evidence_level` | enum | Yes | `meta-analysis`, `rct`, `observational`, `case-report`, `theoretical`. Highest level of available evidence. |
| `bidirectional` | bool | Yes | True if the interaction is symmetric (A affects B AND B affects A). Most interactions are bidirectional for pharmacodynamic purposes. |
| `clinical_notes` | string | Yes | Clinician-facing context. What the prescriber would want to know. May reference dose thresholds where known. |
| `management_guidance` | string | No | What the user should do. Consumer-facing language. Appears in the Flutter `InteractionBanner` body. |
| `sources` | array | Yes | At least one source required. See source object schema below. |
| `flag_name` | string | Yes | Machine-readable flag for traceability in logs and analytics. Format: `INTERACTION_{SEVERITY}_{SUBJECT_SLUG}_{OBJECT_SLUG}`. |
| `subject_standard_names_for_matching` | array[string] | Yes | Lowercase normalized names used for fuzzy matching against catalog entries. |
| `object_standard_names_for_matching` | array[string] | Yes | Lowercase normalized names used for fuzzy matching against user medication entries. |
| `data_provenance` | object | Yes | Audit trail. See provenance object schema below. |

### 3.4 Source Object Schema

```json
{
  "type": "pubmed | doi | drugbank | suppai | nih_ods | livertox | chembl | manual",
  "id": "19145785",
  "description": "Short human-readable description of what the source establishes",
  "url": "https://pubmed.ncbi.nlm.nih.gov/19145785/"
}
```

### 3.5 Provenance Object Schema

```json
{
  "source": "supp_ai | nih_ods | livertox | chembl_theoretical | manual_curated | drugbank",
  "imported_at": "2026-04-10",
  "reviewed_by": "manual_curation | auto_import",
  "review_status": "approved | pending_review | rejected",
  "suppai_pair_id": "1234",
  "drugbank_interaction_id": null,
  "livertox_compound_id": null
}
```

Entries with `review_status = "pending_review"` are excluded from the production build by the schema validator. The validator (`scripts/validate_interactions_schema.py`, to be written at M0) rejects any file containing pending-review entries from being passed to `build_final_db.py`.

### 3.6 Drug Classes Lookup Table

The `drug_classes` object provides a user-facing name and RXCUI member list for each drug class used in interaction entries. This enables the Flutter medication entry flow to display "beta-blockers" rather than a raw RXCUI.

```json
{
  "drug_classes": {
    "anticoagulants": {
      "display_name": "Blood Thinners (Anticoagulants)",
      "description": "Medications that reduce blood clotting, including warfarin and newer direct oral anticoagulants.",
      "rxcui_members": ["11289", "1364435", "1599538", "67108"],
      "example_drug_names": ["warfarin", "apixaban", "rivaroxaban", "dabigatran"],
      "icd10_atc_class": "B01AA"
    },
    "statins": {
      "display_name": "Statins (Cholesterol Medications)",
      "description": "HMG-CoA reductase inhibitors used to lower LDL cholesterol.",
      "rxcui_members": ["36567", "41493", "83367", "301542", "359731"],
      "example_drug_names": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin"],
      "icd10_atc_class": "C10AA"
    },
    "ssris": {
      "display_name": "Antidepressants (SSRIs)",
      "description": "Selective serotonin reuptake inhibitors used for depression and anxiety.",
      "rxcui_members": ["32937", "56795", "68617", "72625", "202433"],
      "example_drug_names": ["sertraline", "fluoxetine", "escitalopram", "paroxetine", "citalopram"],
      "icd10_atc_class": "N06AB"
    },
    "snris": {
      "display_name": "Antidepressants (SNRIs)",
      "description": "Serotonin-norepinephrine reuptake inhibitors used for depression and anxiety.",
      "rxcui_members": ["39786", "61381", "352960"],
      "example_drug_names": ["venlafaxine", "duloxetine", "desvenlafaxine"],
      "icd10_atc_class": "N06AX"
    },
    "beta_blockers": {
      "display_name": "Beta-Blockers (Heart/Blood Pressure Medications)",
      "description": "Medications that block beta-adrenergic receptors, used for hypertension, heart failure, and arrhythmias.",
      "rxcui_members": ["19484", "20352", "33518", "52175", "149"],
      "example_drug_names": ["metoprolol", "atenolol", "carvedilol", "propranolol", "bisoprolol"],
      "icd10_atc_class": "C07AB"
    },
    "ace_inhibitors": {
      "display_name": "ACE Inhibitors (Blood Pressure Medications)",
      "description": "Angiotensin-converting enzyme inhibitors used for hypertension and heart failure.",
      "rxcui_members": ["18867", "29046", "35208", "54552"],
      "example_drug_names": ["lisinopril", "enalapril", "ramipril", "captopril"],
      "icd10_atc_class": "C09AA"
    },
    "thyroid_hormones": {
      "display_name": "Thyroid Medications",
      "description": "Thyroid hormone replacement therapy.",
      "rxcui_members": ["10582", "727374"],
      "example_drug_names": ["levothyroxine", "liothyronine"],
      "icd10_atc_class": "H03AA"
    },
    "maois": {
      "display_name": "MAO Inhibitors (MAOIs)",
      "description": "Monoamine oxidase inhibitors used for depression. Carry severe interaction risk with serotonergic supplements.",
      "rxcui_members": ["7454", "9639"],
      "example_drug_names": ["phenelzine", "tranylcypromine", "selegiline"],
      "icd10_atc_class": "N06AF"
    },
    "immunosuppressants": {
      "display_name": "Immunosuppressants (Transplant / Autoimmune Medications)",
      "description": "Drugs that suppress the immune system, including cyclosporine and tacrolimus.",
      "rxcui_members": ["3008", "9524", "41493"],
      "example_drug_names": ["cyclosporine", "tacrolimus", "mycophenolate"],
      "icd10_atc_class": "L04AA"
    },
    "chemotherapy": {
      "display_name": "Chemotherapy",
      "description": "Cancer treatment medications. Supplement interactions can reduce efficacy or increase toxicity.",
      "rxcui_members": [],
      "example_drug_names": [],
      "icd10_atc_class": "L01",
      "note": "RXCUI member list intentionally sparse — match by drug_class name only for chemotherapy entries."
    }
  }
}
```

### 3.7 Mechanism Flag Map

Used by the ChEMBL theoretical interaction path. Maps a ChEMBL mechanism flag to the drug classes it interacts with at a theoretical level.

```json
{
  "mechanism_flag_map": {
    "cyp3a4_inhibitor": {
      "interacts_with_drug_classes": ["statins", "immunosuppressants", "chemotherapy"],
      "default_severity": "moderate",
      "default_evidence_level": "theoretical",
      "mechanism_template": "{subject} inhibits CYP3A4, the primary metabolic pathway for {object}. This may increase drug plasma levels and the risk of dose-dependent adverse effects."
    },
    "cyp2c9_inhibitor": {
      "interacts_with_drug_classes": ["anticoagulants"],
      "default_severity": "moderate",
      "default_evidence_level": "theoretical",
      "mechanism_template": "{subject} inhibits CYP2C9, reducing warfarin metabolism and potentially increasing INR and bleeding risk."
    },
    "serotonin_precursor": {
      "interacts_with_drug_classes": ["ssris", "snris", "maois"],
      "default_severity": "severe",
      "default_evidence_level": "theoretical",
      "mechanism_template": "{subject} increases serotonin precursor load. Combined with {object}, this can elevate serotonin activity and risk serotonin syndrome."
    },
    "platelet_aggregation_inhibitor": {
      "interacts_with_drug_classes": ["anticoagulants"],
      "default_severity": "moderate",
      "default_evidence_level": "observational",
      "mechanism_template": "{subject} inhibits platelet aggregation, potentially potentiating the anticoagulant effect of {object} and increasing bleeding risk."
    },
    "cyp3a4_inducer": {
      "interacts_with_drug_classes": ["ssris", "immunosuppressants", "statins", "anticoagulants", "chemotherapy"],
      "default_severity": "severe",
      "default_evidence_level": "rct",
      "mechanism_template": "{subject} induces CYP3A4, accelerating the metabolism of {object} and potentially reducing therapeutic drug plasma levels. This is the mechanism underlying the St. John's Wort interaction class."
    }
  }
}
```

### 3.8 Concrete Example: Supplement ↔ Supplement Entry

```json
{
  "id": "INTERACTION_SEVERE_ST_JOHNS_WORT_5HTP",
  "subject": "5-HTP (5-Hydroxytryptophan)",
  "subject_type": "supplement",
  "subject_canonical_id": "5_htp",
  "subject_cui": "C0118922",
  "subject_rxcui": null,
  "object": "St. John's Wort",
  "object_type": "supplement",
  "object_canonical_id": "st_johns_wort",
  "object_cui": "C0032599",
  "object_rxcui": null,
  "object_drug_class": null,
  "object_drug_class_rxcui_members": [],
  "mechanism": "5-HTP is a direct serotonin precursor that increases central serotonin synthesis. St. John's Wort inhibits serotonin reuptake (SSRI-like action) via hypericin and hyperforin. Combined, they produce additive serotonergic stimulation. Serotonin syndrome has been reported with this combination.",
  "severity": "severe",
  "evidence_level": "case-report",
  "bidirectional": true,
  "clinical_notes": "Serotonin syndrome risk. Case reports document this combination causing confusion, agitation, hyperthermia, and tachycardia. The NIH ODS and clinical pharmacology literature flag this pair. The risk is highest at supplemental doses of 5-HTP above 100mg/day combined with therapeutic-dose SJW.",
  "management_guidance": "Do not combine 5-HTP with St. John's Wort. If both are in your stack, remove one. If you are also taking an antidepressant, consult your doctor before taking either supplement.",
  "sources": [
    {
      "type": "pubmed",
      "id": "9690695",
      "description": "Case report: serotonin syndrome with 5-HTP and SJW combination"
    },
    {
      "type": "nih_ods",
      "id": "stjohnswort-HealthProfessional",
      "description": "NIH ODS St. John's Wort Fact Sheet for Health Professionals — interactions section"
    }
  ],
  "flag_name": "INTERACTION_SEVERE_5HTP_ST_JOHNS_WORT",
  "subject_standard_names_for_matching": [
    "5-htp",
    "5 htp",
    "5-hydroxytryptophan",
    "5 hydroxytryptophan",
    "oxitriptan"
  ],
  "object_standard_names_for_matching": [
    "st. john's wort",
    "st johns wort",
    "hypericum perforatum",
    "hypericum"
  ],
  "data_provenance": {
    "source": "manual_curated",
    "imported_at": "2026-04-10",
    "reviewed_by": "manual_curation",
    "review_status": "approved",
    "suppai_pair_id": null
  }
}
```

---

## 4. Matching Strategy

The matching system is the most complex part of the interaction engine. It must connect:
1. A supplement in the catalog (identified by `canonical_id` in `ingredient_quality_map.json`)
2. A user-entered medication (identified by free text, with RXCUI fallback)
3. Interaction records in the database

Matching happens at product-detail-screen render time in Flutter and must complete in under 200ms from local SQLite.

### 4.1 Supplement-Side Matching

When a product detail screen loads, for each ingredient in that product:

**Step 1 — Exact canonical_id match:**
```
ingredient_quality_map[ingredient_key].canonical_id
  → match against interaction_entries[*].subject_canonical_id
  → match against interaction_entries[*].object_canonical_id
```
Highest confidence. Use canonical_id as primary key. If a match is found, proceed to severity evaluation.

**Step 2 — CUI match:**
If canonical_id is null or finds no entries:
```
ingredient.cui → match against subject_cui or object_cui
```
CUI matches are trusted — CUIs are controlled identifiers verified by `scripts/api_audit/verify_cui.py`.

**Step 3 — RXCUI match:**
```
ingredient.rxcui → match against subject_rxcui or object_rxcui
```

**Step 4 — Fuzzy name match (fallback only):**
Normalize `ingredient.standard_name` to lowercase, strip punctuation, then run `rapidfuzz.fuzz.token_sort_ratio` against `subject_standard_names_for_matching`. Accept match if score ≥ 88.

Do not auto-promote a fuzzy match above severity `mild` without a CUI or canonical_id confirmation. Fuzzy-only matches above `moderate` severity must be flagged for review in the app's interaction confidence indicator.

### 4.2 Medication-Side Matching

When a user adds a medication via the Flutter `user_medications` table:

**Step 1 — RXCUI exact match:**
If the user's medication was resolved to an RXCUI (via the in-app medication search calling RxNorm API):
```
user_medication.rxcui → match against object_rxcui
                       → match against object_drug_class_rxcui_members (any element)
```

**Step 2 — Drug class match:**
If RXCUI matches `object_drug_class_rxcui_members` for a drug class, treat all entries with that `object_drug_class` as candidate matches.

**Step 3 — Name fallback:**
If RXCUI lookup fails (offline, user entered "my blood pressure pill"):
- Normalize user input: lowercase, strip articles and descriptors
- Fuzzy match against `object_standard_names_for_matching` arrays (threshold ≥ 85)
- If no fuzzy match: prompt user to select from a `drug_class` picker in the UI ("What type of medication is this?")
- Write the selected drug class to `user_medications.drug_class` for future matching

**Step 4 — Drug class picker fallback:**
The drug class picker is the last resort. It shows the `drug_classes` table with `display_name` and `description` for each class. User selection writes `drug_class` to the local record, enabling class-level interaction matching without requiring RXCUI resolution.

### 4.3 Deduplication Rules

Multiple sources may produce interaction records for the same supplement-drug pair (e.g., supp.ai and NIH ODS both cover fish oil + warfarin). Deduplication rules:

1. **Same subject_canonical_id AND same object_rxcui (or object_drug_class):** these are duplicate pairs.
2. During import, if a duplicate pair is detected, do NOT create two entries. Instead, merge the `sources` arrays from both records into a single entry.
3. The surviving entry uses the higher `evidence_level` of the two (meta-analysis > rct > observational > case-report > theoretical).
4. The surviving entry uses the higher `severity` of the two.
5. Both `data_provenance` records are preserved in a `provenance_history` array (not surfaced in Flutter, but retained for audit).
6. The `id` and `flag_name` of the surviving entry use the winning severity.

**Implementation:** The import scripts write to a staging directory. A deduplication pass (`scripts/deduplicate_interactions.py`, to be written at M1) runs before any file is promoted to `scripts/data/drug_nutrient_interactions.json`.

### 4.4 Conflict Resolution

When two sources disagree on severity or evidence level for the same pair:

| Conflict | Resolution |
|---|---|
| Source A says `moderate`, Source B says `mild` | Use `moderate` (more cautious) |
| Source A says `rct`, Source B says `case-report` | Use `rct` (higher evidence) |
| Source A says `moderate` with `rct`, Source B says `severe` with `case-report` | Use `severe` with `case-report` — severity from most cautious, evidence_level from best available |
| Sources directly contradict on mechanism | Write clinical_notes documenting the disagreement; flag `data_provenance.review_status = "pending_review"` |

The general principle: **never silently downgrade severity when sources conflict**. The most cautious severity always wins. A false positive interaction warning (unnecessary caution) is preferable to a false negative (missed serious interaction) for a consumer safety app.

---

## 5. Severity Scale & Verdict Integration

### 5.1 Five-Tier Severity Definitions

| Tier | Severity | Clinical definition | Example |
|---|---|---|---|
| 1 | `contraindicated` | Combination must be avoided. Evidence of serious harm in clinical use. Prescribers would not co-prescribe. | St. John's Wort + HIV antiretrovirals (reduces drug levels, treatment failure) |
| 2 | `severe` | Combination carries significant risk. Requires medical supervision if continued. Serotonin syndrome, serious bleeding risk, or organ toxicity risk. | 5-HTP + MAOI; kava + hepatotoxic drugs |
| 3 | `moderate` | Combination may alter drug efficacy or increase adverse effects. Prescriber or pharmacist notification advisable. | Fish oil + warfarin; CoQ10 + statins (potential statin efficacy reduction) |
| 4 | `mild` | Minor pharmacokinetic or pharmacodynamic interaction. Monitor for effects; clinical significance usually low. | Vitamin C + aspirin (increased aspirin absorption) |
| 5 | `informational` | No established harm. Documented interaction pathway or theoretical concern. Provided for completeness. | Green tea + iron (reduced non-heme iron absorption) |

### 5.2 Severity Does Not Modify the Arithmetic Score

The interaction system is entirely user-scoped. A supplement's `score_quality_80` and `score_display_100_equivalent` are NOT modified by interaction detection.

**Rationale:** A product score must be product-global and reproducible without user context. A user on warfarin seeing a lower score for fish oil products would be confused when the score changes if they stop their medication. Interactions are a separate concern: they augment the product detail screen with personalized context, not alter the quality rating.

**Implementation consequence:** No changes to `score_supplements.py`, `enrich_supplements_v3.py`, or `build_final_db.py` are required to support the interaction feature. The interaction engine is a standalone read path in Flutter.

### 5.3 Flutter UI Behavior by Severity Tier

| Severity | Banner color | Flutter widget behavior | Dismissible | Deep link |
|---|---|---|---|---|
| `contraindicated` | Red (`#D32F2F`) | Full-width blocking banner at top of product detail screen, above the score card. Non-dismissible. "Do not take this with [medication]." | No | Learn more → clinical_notes modal |
| `severe` | Deep orange (`#E64A19`) | Full-width banner below score card. Persists on re-open. "Talk to your doctor before taking this." | Yes, once per session (reappears on next app open) | Learn more → clinical_notes modal |
| `moderate` | Amber (`#F9A825`) | Compact banner below ingredients list. "This supplement may affect how [medication] works." | Yes, persists dismissed state in local SQLite for 30 days | Learn more → clinical_notes modal |
| `mild` | Blue-grey (`#546E7A`) | Inline chip in the interactions section. "Minor interaction noted." | Yes, persistent dismiss | Tap to expand → clinical_notes modal |
| `informational` | Light grey (`#78909C`) | Collapsed by default in "Interaction Details" accordion. | Always collapsed unless user expands | Expand only |

**Stacking rule:** When a product has multiple interactions for the same medication, only the highest severity banner is shown at the top level. Lower-severity interactions are visible inside the "Interaction Details" section.

### 5.4 Flag Naming Conventions

All interactions in logs, analytics, and crash reports use the `flag_name` field for traceability:

```
INTERACTION_{SEVERITY}_{SUBJECT_SLUG}_{OBJECT_SLUG}
```

- `SEVERITY`: one of `CONTRAINDICATED`, `SEVERE`, `MODERATE`, `MILD`, `INFORMATIONAL`
- `SUBJECT_SLUG`: uppercase snake_case of the supplement canonical_id (e.g., `FISH_OIL`, `ST_JOHNS_WORT`)
- `OBJECT_SLUG`: uppercase snake_case of the drug name or drug class (e.g., `WARFARIN`, `SSRIS`, `ANTICOAGULANTS`)

Examples:
- `INTERACTION_SEVERE_5HTP_MAOIS`
- `INTERACTION_CONTRAINDICATED_ST_JOHNS_WORT_HIV_ANTIRETROVIRALS`
- `INTERACTION_MODERATE_FISH_OIL_WARFARIN`
- `INTERACTION_INFORMATIONAL_GREEN_TEA_IRON`

This naming is enforced by the schema validator at build time.

### 5.5 Disclaimer Language

Every interaction display in Flutter must include the following disclaimer, non-negotiable:

> "This information is for general awareness only and is not medical advice. Always consult your doctor or pharmacist before changing or stopping any medication, supplement, or combination. PharmaGuide does not replace professional medical judgment."

This disclaimer appears as fixed footer text in the `InteractionBanner` widget and as a header in the "Interaction Details" modal. It cannot be hidden or collapsed.

---

## 6. Flutter Integration Plan

### 6.1 New Local SQLite Table: `user_medications`

This table stores the user's current medication list. It is local-only and must never sync to Supabase. Medications are sensitive PHI (personal health information) and the PharmaGuide privacy policy must be updated to explicitly state that medication data stays on-device.

```sql
CREATE TABLE user_medications (
  id              TEXT PRIMARY KEY,      -- UUID generated client-side
  name            TEXT NOT NULL,         -- User-entered or resolved drug name
  rxcui           TEXT,                  -- Resolved RXCUI; null if lookup failed
  drug_class      TEXT,                  -- Key in drug_classes lookup; null if not resolved
  display_name    TEXT NOT NULL,         -- User-visible name (may differ from normalized name)
  started_at      TEXT NOT NULL,         -- ISO 8601 date string (YYYY-MM-DD)
  ended_at        TEXT,                  -- ISO 8601 date string; null = currently taking
  notes           TEXT,                  -- Optional user notes (dose, prescriber)
  created_at      TEXT NOT NULL,         -- ISO 8601 datetime
  updated_at      TEXT NOT NULL          -- ISO 8601 datetime
);

-- Index for active medication lookup (ended_at IS NULL = currently taking)
CREATE INDEX idx_user_medications_active ON user_medications(ended_at)
  WHERE ended_at IS NULL;
```

**Privacy enforcement:**
- This table is excluded from the `sync_to_supabase.py` table list explicitly (add assertion).
- The table is created in the app's private document directory, not in any shared or iCloud-backed location.
- When a user deletes the app, all medication data is destroyed with it (standard iOS/Android app data deletion).
- No analytics events reference medication names. Only the resolved drug class (e.g., "anticoagulants") may appear in anonymized aggregate analytics, and only if the user has opted into analytics.

### 6.2 Interaction Engine — Local SQLite Schema

The interaction database is exported to a separate SQLite table (not JSON) during `build_final_db.py` for fast query performance in Flutter.

```sql
CREATE TABLE interactions (
  id                     TEXT PRIMARY KEY,
  subject_canonical_id   TEXT,            -- FK to ingredients table
  subject_cui            TEXT,
  subject_rxcui          TEXT,
  object_rxcui           TEXT,
  object_drug_class      TEXT,
  severity               TEXT NOT NULL,
  evidence_level         TEXT NOT NULL,
  flag_name              TEXT NOT NULL,
  mechanism              TEXT NOT NULL,
  clinical_notes         TEXT NOT NULL,
  management_guidance    TEXT,
  bidirectional          INTEGER NOT NULL, -- 1 = true, 0 = false
  sources_json           TEXT NOT NULL,    -- Serialized JSON array of source objects
  subject_names_json     TEXT NOT NULL,    -- Serialized JSON array for fuzzy matching
  object_names_json      TEXT NOT NULL     -- Serialized JSON array for fuzzy matching
);

-- Indexes for the two hot query paths
CREATE INDEX idx_interactions_subject ON interactions(subject_canonical_id);
CREATE INDEX idx_interactions_object_rxcui ON interactions(object_rxcui);
CREATE INDEX idx_interactions_object_class ON interactions(object_drug_class);
```

### 6.3 New Flutter Widget: `InteractionBanner`

`InteractionBanner` is a stateless widget added to the `ProductDetailScreen`. It reads from the local SQLite interaction table and the `user_medications` table.

**Location in widget tree:** Immediately below the score card, before the ingredients breakdown section.

**Inputs to the widget:**
- `productIngredients`: list of `canonical_id` strings for all ingredients in the current product
- `localDb`: reference to the SQLite database instance

**Widget behavior:**
1. Query `user_medications` where `ended_at IS NULL` to get active medications.
2. If no active medications: render nothing (or render a gentle "Add your medications to see personalized interaction info" prompt — UX decision for M4).
3. For each active medication × each product ingredient, run the matching strategy from Section 4 against the local `interactions` table.
4. Collect all matching interactions. Group by severity (highest first).
5. Render the highest-severity banner as a full-width widget using the color rules from Section 5.3.
6. All additional interactions are collapsed into the "See all interactions (N)" expandable section below.

**Performance requirement:** The full query path must complete in < 200ms on a mid-range device (2021 Android, 3GB RAM). This is achievable with indexed SQLite queries against a database of ≤ 5,000 interaction records.

### 6.4 Stack-Level Interaction Check

When the user adds a product to their stack (via the stack-building feature), a background interaction check runs across all products currently in the stack:

1. Collect all `canonical_id` values for every ingredient in every product in the stack.
2. Query the `interactions` table for any entry where both `subject_canonical_id` AND `object_canonical_id` are in the collected set.
3. If any supplement ↔ supplement interactions are found: surface a `StackInteractionBanner` in the stack overview screen (not on individual product screens).
4. Also re-run the supplement ↔ drug check for all stack ingredients × all active medications.

**Stack interaction entry point in data:** Supplement ↔ supplement entries have both `subject_canonical_id` and `object_canonical_id` populated. This is the distinguishing field — if `object_canonical_id` is not null, it's a supplement-supplement pair.

### 6.5 Medication Entry UI

The medication entry flow is a new screen added at M4:

1. **Search field** with RxNorm API integration (debounced, 300ms). Calls `rxnav.nlm.nih.gov/REST/drugs.json?name=<query>` while online. Offline: direct entry only.
2. **Autocomplete list** from RxNorm results showing `displayName` and `synonym`.
3. On selection: resolve RXCUI, populate `user_medications`.
4. **Fallback:** if user can't find their drug via search, "I can't find it — let me pick the type" launches the drug class picker.
5. **Active/inactive toggle:** users can mark medications as stopped (sets `ended_at`). Stopped medications do not trigger interaction warnings.

**Privacy reminder in the UI:** A single line of copy under the search field: "Your medications are stored only on this device and never shared."

---

## 7. Build Plan with Milestones

### M0 — Schema + Golden Dataset (2–3 weeks, 1 engineer)

**Deliverables:**
- This spec document finalized and reviewed.
- `scripts/data/drug_nutrient_interactions.json` created with the schema from Section 3, containing exactly 10 hand-curated interaction records (the "golden set").
- `scripts/validate_interactions_schema.py` written and passing on the golden dataset.
- 10 golden interactions cover: fish oil + warfarin, St. John's Wort + SSRIs, St. John's Wort + HIV antiretrovirals, 5-HTP + MAOIs, 5-HTP + St. John's Wort, kava + alcohol, magnesium + antibiotics (tetracyclines), calcium + levothyroxine, vitamin K + warfarin, green tea (high dose) + anticoagulants.
- Schema validator integrated into `build_final_db.py` as a pre-flight check.
- Test file `scripts/tests/test_interaction_schema.py` written with golden dataset assertions.
- `drug_classes` lookup table populated with the 10 classes listed in Section 3.6.

**Acceptance criteria:** All 10 golden interactions render correct severity banners in a local Flutter test harness (screenshots reviewed manually).

### M1 — supp.ai Import + Normalization (3–4 weeks, 1 engineer)

**Deliverables:**
- `scripts/api_audit/normalize_suppai.py`: imports supp.ai TSV, normalizes supplement names to canonical_ids, resolves drug names to RXCUI via RxNorm API.
- Manual review queue output: JSON file listing all supp.ai entries that failed auto-normalization.
- Reviewed and approved entries promoted to `drug_nutrient_interactions.json`.
- `scripts/deduplicate_interactions.py`: merge-by-pair deduplication with conflict resolution rules from Section 4.3.
- Target: ~400–600 approved supplement-drug interaction entries after review.
- Test coverage for the normalization pipeline.
- supp.ai attribution added to the app's data sources disclosure screen.

**Acceptance criteria:** `python3 -m pytest scripts/tests/test_interaction_schema.py scripts/tests/test_suppai_import.py` passes. Deduplication reduces the raw supp.ai set by ≥ 10% (expected duplicate rate based on overlapping source coverage with golden set).

### M2 — UMLS RxNorm RXCUI Enrichment (2–3 weeks, 1 engineer)

**Deliverables:**
- `scripts/api_audit/enrich_rxnorm.py`: for all drug entries in the interaction DB lacking RXCUI, run RxNorm lookup. Apply safe-apply pattern (no auto-write without review).
- For all `ingredient_quality_map.json` entries with `cui` but no `rxcui`: run RxNorm enrichment. Same safe-apply pattern.
- Target: ≥ 90% of drug entries in the interaction DB have a confirmed RXCUI.
- Interaction DB entries with unresolved drug RXCUI: demoted to `evidence_level = "theoretical"` pending resolution.

**Acceptance criteria:** Running `python3 scripts/api_audit/enrich_rxnorm.py --dry-run` reports < 10% of interaction entries with null `object_rxcui`.

### M3 — DrugBank Drug-Drug Coverage (4–6 weeks, 1 engineer; license decision required)

**Deliverables:**
- License decision: academic XML (free, limited) vs. commercial API (paid).
- If academic: `scripts/api_audit/import_drugbank.py` for XML bulk import of drug-drug interactions for the 10 drug classes in the lookup table.
- Target: ~200–400 drug-drug interaction entries covering the most clinically significant pairs within the 10 priority drug classes.
- All DrugBank entries require the standard review queue flow before promotion.
- DrugBank attribution added to data sources disclosure.

**Acceptance criteria:** Drug-drug coverage for all 10 drug classes in Section 3.6. Test file `scripts/tests/test_drugbank_import.py` passing.

### M4 — Flutter Widget + Medication Entry UI (4–5 weeks, 1 engineer Flutter)

**Deliverables:**
- `user_medications` SQLite table and migration.
- `InteractionBanner` widget integrated into `ProductDetailScreen`.
- Medication entry screen with RxNorm search and drug class fallback picker.
- Stack-level interaction check in `StackScreen`.
- Disclaimer text permanently rendered in all interaction display contexts.
- Privacy policy updated to state medications are stored locally only.
- UI/UX review of severity banner colors and copy.

**Acceptance criteria:** Manual QA checklist covering: medication add flow, interaction banner render for each severity tier, stack interaction detection, offline behavior (interaction DB cached locally), medication data not appearing in Supabase.

### M5 — Stack-Level Interaction Engine (2–3 weeks, 1 engineer)

**Deliverables:**
- Extend the M4 stack check to handle multi-product stacks with > 10 ingredients efficiently.
- Performance optimization: ensure stack-check completes < 500ms for a 5-product stack on mid-range device.
- Interaction deduplication in the stack view (same interaction from two products shown once).
- "Your stack is interaction-safe" positive feedback state when no interactions detected.

**Acceptance criteria:** Performance regression test in `scripts/tests/test_stack_interaction_perf.py` (run on CI against a synthetic 5-product stack with 50 total ingredients).

### Estimated Total Effort

| Milestone | Calendar time | Engineering time |
|---|---|---|
| M0 | 2–3 weeks | ~40 hours |
| M1 | 3–4 weeks | ~60 hours |
| M2 | 2–3 weeks | ~30 hours |
| M3 | 4–6 weeks | ~80 hours (pending license) |
| M4 | 4–5 weeks | ~100 hours (Flutter) |
| M5 | 2–3 weeks | ~40 hours |
| **Total** | **~5 months sequential** | **~350 hours** |

M0–M2 and M4 can overlap with M3 if the DrugBank license decision is delayed.

---

## 8. Open Questions & Risks

### 8.1 Legal / Medical Disclaimer — Liability Exposure

**Risk:** Displaying drug interaction warnings in a consumer app creates liability exposure, especially if a warning is missed (false negative) or if a user takes action based on an incorrect warning (false positive).

**Assessment:** False negatives (missed serious interactions) are the more dangerous failure mode for users. False positives (unnecessary caution) cause friction but not harm. The design philosophy in this spec errs toward more caution: severity conflicts resolve to the higher tier, and pending-review entries are excluded from production rather than shown with lower confidence.

**Mitigations:**
- The disclaimer language in Section 5.5 is mandatory and non-dismissible.
- The "informational" tier is specifically designed for entries where we want to surface awareness without implying clinical urgency.
- Legal review required before M4 ship. Involve a healthcare attorney to review the disclaimer language and the severity copy in the banners.
- Consider whether the feature requires a "terms of use" acknowledgment gate on first use.

### 8.2 False Negatives Are the Real Risk

The interaction DB will have coverage gaps, especially at M0/M1. A user on a medication not covered by our database will see no interaction warning. This is not the same as "no interaction exists."

**Mitigation:** The app should communicate coverage status. If a user's medication has no RXCUI resolution and no drug class match, the app should display: "We couldn't identify this medication. Our interaction database covers [N] common medication classes. Check with your pharmacist for specific interactions." This is better than silently showing nothing.

### 8.3 Data Licensing

| Source | License risk | Mitigation |
|---|---|---|
| supp.ai | Low — academic open; attribution required | Attribution text in app must be verified before M4 |
| NIH ODS, LiverTox | None — US government public domain | No action required |
| ChEMBL | Low — CC BY-SA 3.0; attribution required | Already handled by existing ChEMBL audit tooling |
| DrugBank free XML | Medium — academic license; attribution required; no commercial redistribution | Review license terms at M3; if the app is monetized, the free academic license may not apply |
| DrugBank commercial | Low once licensed | Budget required; evaluate at M3 |

**Key risk:** If PharmaGuide moves to a paid app or subscription model before M3, the DrugBank academic XML license may not be valid. Clarify with DrugBank legal before using the academic XML in a commercial product.

### 8.4 Maintenance Burden

Drug approvals, recalls, and interaction updates happen continuously. The NIH ODS Fact Sheets are updated periodically. supp.ai may release updated dataset versions. DrugBank updates quarterly.

**Mitigation plan:**
- Interactions file follows the same `update_frequency: quarterly` policy as other data files.
- The `_metadata.last_updated` field triggers a stale-data warning in `build_final_db.py` if the file has not been updated in > 6 months.
- At M2+, run `enrich_rxnorm.py` quarterly to catch newly assigned RXCUIs for entries that were previously unresolved.
- The FDA weekly sync pattern (`scripts/run_fda_sync.sh`) is a model for automating data currency checks. A quarterly interactions refresh script can follow the same pattern.

### 8.5 Handling "My Blood Pressure Pill" — Missing RXCUI

When users enter vague medication descriptions, the RXCUI lookup fails. The drug class picker fallback (Section 6.2) covers this case, but it depends on the user knowing their medication class.

**Realistic worst case:** A user enters "heart pill" and selects "Blood Pressure Medications (ACE Inhibitors)" when they are actually on a calcium channel blocker. This produces false negative interaction results.

**Mitigation:** The drug class picker shows `example_drug_names` alongside the class description. The user can compare their pill name against examples. This is not foolproof but reduces misclassification.

**Future option (out of scope for v1):** Pill identification via image (NDC barcode scan or imprint search). This would dramatically improve RXCUI resolution accuracy but is a significant engineering investment.

### 8.6 Interaction Between Interaction Warnings and the Scoring System

The current scoring system produces a `BLOCKED` or `UNSAFE` verdict for products containing banned/recalled substances. Users may conflate a low quality score with an interaction warning, or expect the score to reflect their personal medication context.

**Decision:** The score is product-global and never modified by interactions. This must be communicated clearly in the UX. The product detail screen should visually separate the quality score section from the interaction section. Copy suggestion: "Quality score reflects the supplement itself. Interaction warnings reflect your specific health context."

---

## 9. Out of Scope — Do Not Confuse with v1

The following features are commonly requested in the interaction space and are intentionally deferred. They are documented here to prevent scope creep during M0–M5 planning.

### 9.1 Pharmacogenomic Gene-Variant Effects

CYP2D6, CYP2C9, CYP2C19, and SLCO1B1 variants materially alter drug metabolism for a meaningful percentage of the population. For example, CYP2D6 poor metabolizers on codeine face toxicity risk. Including gene variants in interaction logic would require genotype input from the user, a different data source (PharmGKB, CPIC), and a dramatically more complex matching engine.

**Why deferred:** No pathway to obtain reliable user genotype data in v1. Consumer DNA test results are not reliable enough for clinical decision support use.

### 9.2 Dose-Dependent Interaction Modeling

The fish oil + warfarin interaction has a different clinical significance at 1g/day EPA+DHA versus 4g/day. The current schema captures dose thresholds in `clinical_notes` prose, but the interaction logic does not vary severity by dose.

**Why deferred:** Product-level dose data is available in the pipeline, but user-entered dose (how much of a product they take) is not captured in v1. Without user dose input, dose-dependent modeling produces false precision.

### 9.3 Time-of-Day Separation Recommendations

Calcium and levothyroxine should be separated by 4 hours. Iron and tetracyclines should not be taken together. These timing recommendations are interaction-adjacent but require a different UX (schedule-based) and a separate data field (`separation_hours`).

**Why deferred:** Time-of-day scheduling is a distinct feature category from interaction warnings. It requires an active-schedule model for the user's supplement and medication intake. Scope it separately if there is demand.

### 9.4 Clinical Decision Support for Providers

PharmaGuide is a consumer app. The interaction data and UI are designed for patient-level awareness, not clinical workflow integration. The app does not produce clinical recommendations, does not generate printable reports for prescribers, and does not integrate with EHR systems.

**Why deferred:** Regulatory pathway (FDA Software as a Medical Device classification) and liability exposure of clinical decision support are out of scope for the current product definition.

### 9.5 Pregnancy and Lactation Safety Flags

Supplement safety in pregnancy and lactation is a distinct concern from drug interactions. It requires a separate data source (LactMed, Drugs and Lactation Database) and a separate user profile flag.

**Why deferred:** High-value feature but orthogonal to the interaction engine. Scope as a separate "pregnancy mode" feature.

### 9.6 Real-Time Drug Approval Change Monitoring

New drug approvals and label changes happen continuously. Automatically monitoring FDA approval RSS feeds for interaction-relevant label changes is technically feasible (following the existing `run_fda_sync.sh` pattern) but is out of scope for v1 given the quarterly maintenance cadence already defined.

---

*End of specification.*

*This document is a living spec. Update version and `last_updated` when any section changes. Major schema changes require a schema_version bump and a migration note in `_metadata.change_log`.*
