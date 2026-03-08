#!/usr/bin/env python3
"""
Apply all audit-verified corrections to harmful_additives.json.
Generated from full 110-entry audit (March 2026).
All changes verified against FDA/EFSA/IARC/NTP/USDA primary sources.
"""
import json
import copy
from datetime import date

INPUT_PATH = "scripts/data/harmful_additives.json"
OUTPUT_PATH = "scripts/data/harmful_additives.json"

TODAY = str(date.today())


def get_entry(entries: list, entry_id: str) -> dict:
    for e in entries:
        if e["id"] == entry_id:
            return e
    raise KeyError(f"Entry not found: {entry_id}")


def apply_corrections(data: dict) -> dict:
    entries = data["harmful_additives"]

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCK 1: CRITICAL FACTUAL ERRORS
    # ─────────────────────────────────────────────────────────────────────────

    # ── Entry 22: ADD_CAROB_COLOR ──────────────────────────────────────────
    # E153 (vegetable carbon black) is NOT approved as a food color in the US.
    e = get_entry(entries, "ADD_CAROB_COLOR")
    e["regulatory_status"] = {
        "US": (
            "NOT approved as a food color. E153 (vegetable carbon / carbon black) "
            "is not listed in FDA's Certified Color Additives inventory for food use "
            "and is not permitted in US dietary supplements as a colorant. Products "
            "containing E153 imported into the US as food/supplement colorants may be "
            "refused entry."
        ),
        "EU": "E153 approved in limited food categories (e.g., certain cheeses, olive oil). Subject to purity criteria under Commission Regulation (EU) No 231/2012.",
        "WHO": "JECFA: acceptable for food use (Group 1) based on the absence of significant absorption and systemic toxicity at typical use levels.",
    }
    e["notes"] = (
        "A pigment derived from charred vegetable matter (carob, wood, coconut shell). "
        "IMPORTANT: E153 (carbon black) is NOT approved as a food color in the United States — "
        "it does not appear in FDA's Certified Color Additives inventory. US supplements must not "
        "list this as 'carmine' or 'carob color' implying FDA approval. "
        "Distinct from carob bean gum (E410 / locust bean gum), which IS FDA-GRAS as a thickener. "
        "In EU, E153 is approved for select food uses. EFSA 2012 re-evaluation found no safety concern "
        "at authorized EU use levels."
    )
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "REGULATORY_UPDATE", "Corrected critical error: entry stated 'US: FDA permitted' which is false. E153 is not listed in FDA's Certified Color Additives inventory. Regulatory status completely rewritten.")

    # ── Entry 23: ADD_CARRAGEENAN ─────────────────────────────────────────
    # USDA 2018 RETAINED carrageenan — it was NOT removed.
    e = get_entry(entries, "ADD_CARRAGEENAN")
    reg = e.get("regulatory_status", {})
    if isinstance(reg, dict):
        reg["US"] = (
            "FDA GRAS status for food use (21 CFR 172.620). "
            "NOSB voted in 2016 to recommend removal from the National List for organic foods, "
            "but USDA issued a final rule in April 2018 RETAINING carrageenan on the National List — "
            "overriding the NOSB recommendation (only the second override in ~30 years). "
            "Carrageenan remains permitted in USDA-certified organic processed products as of 2026."
        )
        e["regulatory_status"] = reg
    _fix_notes_carrageenan(e)
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "REGULATORY_UPDATE",
                    "Corrected critical error: entry stated carrageenan was 'removed from USDA organic certification 2018'. "
                    "The opposite occurred — USDA's April 2018 final rule RETAINED carrageenan on the National List, overriding NOSB.")

    # ── Entry 49: ADD_MINERAL_OIL ─────────────────────────────────────────
    # Untreated/mildly treated mineral oils = IARC Group 1 (NOT Group 2B).
    e = get_entry(entries, "ADD_MINERAL_OIL")
    notes = e.get("notes", "")
    notes = notes.replace("Group 2B", "Group 1").replace("group 2B", "Group 1")
    # Also ensure Group 1 is stated clearly
    if "Group 1" not in notes:
        notes = (
            "IARC CLASSIFICATION CORRECTION: Untreated and mildly treated mineral oils are "
            "IARC Group 1 (KNOWN human carcinogen — occupational evidence for scrotal and skin cancers). "
            "Highly refined / pharmaceutical-grade white mineral oil = IARC Group 3 (not classifiable). "
            + notes
        )
    e["notes"] = notes
    mech = e.get("mechanism_of_harm", "")
    mech = mech.replace("Group 2B", "Group 1")
    if "Group 1" not in mech:
        mech += (
            " NOTE: Untreated/mildly treated mineral oils are IARC Group 1 carcinogen; "
            "pharmaceutical-grade white mineral oil used in supplements is IARC Group 3."
        )
    e["mechanism_of_harm"] = mech
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "MECHANISM_UPDATE",
                    "Corrected IARC classification error: untreated/mildly treated mineral oils are Group 1 (known carcinogen), not Group 2B. "
                    "Pharmaceutical white mineral oil = Group 3. Source: IARC Supplement 7.")

    # ── Entry 52: ADD_NEOTAME ─────────────────────────────────────────────
    # Regulatory_status had "Status pending review" for both US and EU.
    # ADIs in original JSON were completely wrong (18 mg/kg/day has no basis).
    # EFSA 2025 updated ADI to 10 mg/kg/day (was 2 mg/kg/day).
    # FDA ADI ≈ 0.3 mg/kg/day based on 21 CFR 172.829 approval framework.
    e = get_entry(entries, "ADD_NEOTAME")
    e["regulatory_status"] = {
        "US": (
            "FDA approved as general-purpose sweetener and flavor enhancer (21 CFR 172.829, 2002). "
            "ADI approximately 0.3 mg/kg bw/day based on JECFA evaluation used at approval. "
            "No PKU warning label required (unlike aspartame) at typical use levels."
        ),
        "EU": (
            "E961; EFSA 2025 re-evaluation (EFSA Journal 2025:9480) established ADI of "
            "10 mg/kg bw/day — a significant increase from the previous EFSA ADI of 2 mg/kg bw/day. "
            "Approved for use in foodstuffs and table-top sweeteners."
        ),
        "WHO": "JECFA 2003 evaluation: ADI 2 mg/kg bw/day. EFSA 2025 revision is substantially higher.",
    }
    e["notes"] = (
        "An ultra-high-intensity artificial sweetener ~7,000–13,000× sweeter than sucrose. "
        "Chemically derived from aspartame but metabolized differently; phenylalanine release is negligible "
        "at typical use levels — no PKU warning required. "
        "REGULATORY NOTE: Previous JSON listed US ADI as 18 mg/kg/day — this is incorrect and has no basis "
        "in any regulatory publication. EFSA 2025 set ADI at 10 mg/kg/day (EFSA Journal 2025:9480), "
        "significantly higher than the earlier 2 mg/kg/day. "
        "2024 in vitro data (PMID 38721028, Frontiers in Nutrition 2024): neotame caused intestinal epithelial "
        "apoptosis via T1R3 receptor signaling and promoted pathogenic transformation of E. coli and E. faecalis "
        "at physiologically relevant concentrations; human significance not yet established."
    )
    e["mechanism_of_harm"] = (
        "Aspartame derivative that is rapidly metabolized; phenylalanine exposure negligible at typical "
        "ultra-low usage levels. Potential gut epithelial concern: 2024 in vitro study (PMID 38721028) "
        "demonstrated neotame-induced intestinal epithelial cell apoptosis via T1R3 taste receptor signaling, "
        "disruption of tight junctions, and phenotypic shift of E. coli and E. faecalis toward pathogenicity "
        "at physiologically relevant concentrations. Human significance and in vivo replication pending."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 38721028 — Neotame intestinal epithelial apoptosis and gut microbiome effects (Frontiers in Nutrition 2024)",
        "EFSA Journal 2025:9480 — Re-evaluation of neotame (E961), ADI revised to 10 mg/kg bw/day",
        "FDA 21 CFR 172.829 — Neotame approval as food additive (2002)",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "REGULATORY_UPDATE + MECHANISM_UPDATE",
                    "Critical correction: original JSON had US ADI 18 mg/kg/day and EU ADI 2 mg/kg/day — both incorrect. "
                    "US ADI ≈ 0.3 mg/kg/day; EFSA 2025 revised EU ADI to 10 mg/kg/day (from 2 mg/kg/day). "
                    "Added 2024 gut epithelial apoptosis finding (PMID 38721028). Populated previously empty regulatory and mechanism fields.")

    # ── Entry 64: ADD_POTASSIUM_SORBATE ──────────────────────────────────
    # Mechanism cited "1,2-propanediol" — wrong compound. Actual mutagenic
    # products are crotonaldehyde and malondialdehyde (reactive carbonyls).
    # Also: ADI was 25 mg/kg/day; EFSA 2019 revised to 11 mg/kg/day.
    e = get_entry(entries, "ADD_POTASSIUM_SORBATE")
    mech = e.get("mechanism_of_harm", "")
    mech = mech.replace("1,2-propanediol", "crotonaldehyde and malondialdehyde (reactive carbonyl compounds)")
    if "crotonaldehyde" not in mech:
        mech += (
            " CORRECTION: In the presence of ascorbic acid and iron in acidic conditions, "
            "sorbic acid can form mutagenic carbonyl degradation products — specifically "
            "crotonaldehyde and malondialdehyde — NOT 1,2-propanediol (which is not a sorbate metabolite). "
            "Formation occurs under specific in vitro conditions; not confirmed in supplement/food matrices."
        )
    e["mechanism_of_harm"] = mech
    reg = e.get("regulatory_status", {})
    if isinstance(reg, dict):
        reg["EU"] = "E202; group ADI 11 mg/kg bw/day as sorbic acid (EFSA 2019 revised — previously 25 mg/kg/day)."
        reg["WHO"] = "JECFA ADI 25 mg/kg bw/day (group ADI for sorbic acid and its salts); EFSA 2019 revised EU group ADI to 11 mg/kg bw/day."
        e["regulatory_status"] = reg
    notes = e.get("notes", "")
    notes = notes.replace("25 mg/kg", "11 mg/kg").replace("ADI: 25", "ADI: 11")
    if "11 mg/kg" not in notes:
        notes += (
            " EFSA 2019 revised the group ADI for sorbic acid/potassium sorbate downward "
            "from 25 to 11 mg/kg bw/day based on an extended one-generation reproductive toxicity study."
        )
    e["notes"] = notes
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 12176085 — Kang et al. 2002: mutagenic carbonyl products (crotonaldehyde, MDA) from sorbic acid + ascorbic acid reaction",
        "EFSA Journal 2019:5625 — Revised group ADI for sorbic acid E200/E202 (11 mg/kg bw/day)",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "MECHANISM_UPDATE + REGULATORY_UPDATE",
                    "Corrected mechanism: '1,2-propanediol' is not a mutagenic product of potassium sorbate; "
                    "actual reactive carbonyls are crotonaldehyde and malondialdehyde (PMID 12176085). "
                    "Updated EU/WHO ADI from 25 to 11 mg/kg bw/day (EFSA 2019 revision).")

    # ── Entry 67: ADD_RED40 ───────────────────────────────────────────────
    # Entry referenced a fabricated "EFSA 2023 re-evaluation that reduced ADI."
    # No such opinion exists. EFSA last evaluated Red 40 in 2009 (ADI 7 mg/kg/day).
    # Also: FDA/HHS announced voluntary phase-out by end of 2026 (April 2025).
    e = get_entry(entries, "ADD_RED40")
    reg = e.get("regulatory_status", {})
    if isinstance(reg, dict):
        reg["US"] = (
            "FDA approved color additive (21 CFR 74.340). "
            "HHS/FDA announced April 22, 2025: voluntary phase-out of FD&C Red No. 40 "
            "from the US food supply targeted by end of 2026, as part of initiative to phase out "
            "all remaining petroleum-based synthetic dyes. California school ban effective December 31, 2027 "
            "(California AB418, 2023)."
        )
        reg["EU"] = (
            "Authorized as E129. ADI: 7 mg/kg bw/day per EFSA 2009 re-evaluation (EFSA Journal 2009:1329) — "
            "EFSA maintained ADI unchanged, did NOT reduce it. "
            "EU requires hyperactivity warning label: 'may have an adverse effect on activity and attention in children' "
            "(Regulation (EC) No 1333/2008, Annex V). "
            "NOTE: There is NO 2023 EFSA re-evaluation of Red 40. Any reference to a 2023 EFSA ADI change is incorrect."
        )
        e["regulatory_status"] = reg
    notes = e.get("notes", "")
    # Remove any EFSA 2023 claims
    for bad_phrase in ["EFSA 2023", "EFSA's 2023", "2023 re-evaluation", "2023 reduced"]:
        if bad_phrase in notes:
            notes = notes.replace(bad_phrase, "[REMOVED — EFSA 2023 Red 40 re-evaluation does not exist]")
    if "phase-out" not in notes and "2025" not in notes:
        notes += (
            " UPDATE (2025): FDA/HHS announced April 22, 2025 voluntary phase-out of FD&C Red No. 40 "
            "by end of 2026. EFSA last evaluated in 2009; ADI maintained at 7 mg/kg bw/day — "
            "there is no 2023 EFSA re-evaluation or ADI reduction for this dye."
        )
    e["notes"] = notes
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2009:1329 — Re-evaluation of Allura Red AC (E129); ADI maintained at 7 mg/kg bw/day",
        "FDA/HHS Press Release April 22, 2025 — HHS and FDA to Phase Out Petroleum-Based Synthetic Dyes",
        "McCann et al. Lancet 2007 — Southampton study: hyperactivity association with mixed food colors",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "REGULATORY_UPDATE",
                    "Removed fabricated 'EFSA 2023 ADI reduction' claim — no such opinion exists. "
                    "EFSA last evaluated Red 40 in 2009; ADI maintained at 7 mg/kg bw/day. "
                    "Added FDA/HHS April 2025 voluntary phase-out announcement (target: end of 2026).")

    # ── Entry 69: ADD_SENNA ───────────────────────────────────────────────
    # Entry (in previous session notes) had attributed FDA 2002 ruling to senna.
    # The 2002 FDA final rule removed aloe and cascara sagrada, NOT senna.
    # Senna/sennosides are FDA-regulated OTC drug ingredients.
    # The EFSA 2018/2024 HAD genotoxicity findings in the entry are accurate.
    e = get_entry(entries, "ADD_SENNA")
    reg = e.get("regulatory_status", {})
    if isinstance(reg, dict):
        us_status = reg.get("US", "")
        if "2002" in us_status and ("cascara" not in us_status or "aloe" not in us_status):
            reg["US"] = (
                "Regulated as an OTC drug (stimulant laxative) in the US, not as a dietary supplement ingredient. "
                "FDA's 2002 final rule (Fed. Reg. 67:31125, May 9 2002) removed ALOE and CASCARA SAGRADA from "
                "the OTC stimulant laxative monograph as not GRASE — senna/sennosides were NOT part of that ruling. "
                "Senna sennosides are separately subject to ongoing FDA OTC monograph review. "
                "DSHEA allows sale as a supplement ingredient, but drug-level stimulant laxative effects mean "
                "it is inappropriate as a routine supplement additive. "
                "FDA has not established a GRAS status for senna sennosides as a food/supplement ingredient."
            )
        e["regulatory_status"] = reg
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "REGULATORY_UPDATE",
                    "Corrected regulatory attribution: FDA 2002 final rule removed aloe and cascara sagrada, NOT senna. "
                    "Senna sennosides were not part of the 2002 OTC stimulant laxative ruling. "
                    "EFSA 2018/2024 HAD genotoxicity findings retained as accurate.")

    # ── Entry 82: ADD_SORBIC_ACID ─────────────────────────────────────────
    # ADI listed as 25 mg/kg/day — EFSA 2019 revised group ADI to 11 mg/kg/day.
    e = get_entry(entries, "ADD_SORBIC_ACID")
    reg = e.get("regulatory_status", {})
    if isinstance(reg, dict):
        for key in ["EU", "WHO"]:
            if key in reg:
                reg[key] = reg[key].replace("25 mg/kg", "11 mg/kg").replace("ADI 25", "ADI 11")
        if "EU" in reg and "11" not in reg["EU"]:
            reg["EU"] = "E200; group ADI 11 mg/kg bw/day (EFSA 2019 revised from 25 mg/kg/day)."
        if "WHO" in reg and "11" not in reg["WHO"]:
            reg["WHO"] = "JECFA group ADI 25 mg/kg bw/day; EFSA 2019 revised EU group ADI to 11 mg/kg bw/day."
        e["regulatory_status"] = reg
    notes = e.get("notes", "")
    notes = notes.replace("25 mg/kg", "11 mg/kg").replace("ADI: 25", "ADI: 11")
    if "11 mg/kg" not in notes:
        notes += " EFSA 2019 revised the group ADI from 25 to 11 mg/kg bw/day."
    e["notes"] = notes
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2019:5625 — Follow-up re-evaluation of sorbic acid (E200) and potassium sorbate (E202): revised ADI 11 mg/kg bw/day",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "REGULATORY_UPDATE",
                    "Corrected ADI from 25 mg/kg/day to 11 mg/kg/day — EFSA 2019 follow-up re-evaluation revised the group ADI downward.")

    # ── Entry 102: ADD_YELLOW5 ────────────────────────────────────────────
    # Entry had caramel color (4-MEI/E150) content copied into mechanism and
    # regulatory_status — completely wrong for Yellow 5 (Tartrazine / E102 EU / FD&C Yellow No. 5 US).
    # Notes correctly identified it as azo dye; mechanism/regulatory need replacement.
    e = get_entry(entries, "ADD_YELLOW5")
    e["mechanism_of_harm"] = (
        "Azo dye metabolized to aromatic amines in the GI tract. "
        "Associated with hyperactivity in children (McCann et al. 2007 Southampton study, Lancet). "
        "Cross-reactivity with aspirin in aspirin-sensitive individuals (urticaria, bronchospasm). "
        "Trace benzidine (IARC Group 1 carcinogen) present as manufacturing impurity in azo dyes; "
        "modern manufacturing limits this substantially. "
        "Some in vitro genotoxicity signals reported; EFSA 2009 re-evaluation found no confirmed "
        "in vivo genotoxicity at authorized food use levels. "
        "EFSA requested further Comet assay studies for sulfonated mono-azo dyes as a class."
    )
    e["regulatory_status"] = {
        "US": (
            "FDA approved as FD&C Yellow No. 5 (Tartrazine) — 21 CFR 74.705. "
            "Requires specific labeling on all products containing it (FALCPA). "
            "NOTE: E102 is the EU code — in the US this dye is designated FD&C Yellow No. 5, not E102. "
            "HHS/FDA April 2025 announced voluntary phase-out of all petroleum-based synthetic dyes by 2026."
        ),
        "EU": (
            "Authorized as E102. ADI: 7.5 mg/kg bw/day (EFSA 2009 reduced from 10 mg/kg bw/day). "
            "EU Regulation 1333/2008 Annex V requires hyperactivity warning label on foods containing E102: "
            "'may have an adverse effect on activity and attention in children.'"
        ),
        "WHO": "JECFA ADI: 7.5 mg/kg bw/day.",
    }
    e["notes"] = (
        "Synthetic azo dye (FD&C Yellow No. 5 in the US; E102 in the EU). "
        "Most extensively studied synthetic food dye. "
        "EU requires hyperactivity warning label. Cross-reactivity with aspirin documented. "
        "EFSA 2009 re-evaluation reduced ADI from 10 to 7.5 mg/kg bw/day. "
        "FDA/HHS announced voluntary phase-out of petroleum-based synthetic dyes (April 2025, target end of 2026). "
        "CORRECTION: Previous entry had caramel color (4-MEI/E150) content erroneously copied into "
        "this entry's mechanism and regulatory_status fields — both have been replaced with correct Tartrazine data."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2009:1330 — Re-evaluation of Tartrazine (E102); ADI revised to 7.5 mg/kg bw/day",
        "McCann et al. Lancet 2007 (PMID 17825405) — Southampton study: hyperactivity association with food color mixtures including tartrazine",
        "FDA/HHS Press Release April 22, 2025 — HHS and FDA to Phase Out Petroleum-Based Synthetic Dyes",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "MECHANISM_UPDATE + REGULATORY_UPDATE",
                    "Major correction: entry had caramel color (4-MEI / E150) content erroneously in mechanism_of_harm and regulatory_status fields. "
                    "These have been replaced with correct FD&C Yellow No. 5 (Tartrazine / E102) data. "
                    "Also fixed: 'FDA approved E102' → 'FDA approved FD&C Yellow No. 5; E102 is the EU code'.")

    # ── Entry 105: BANNED_ADD_BHT ─────────────────────────────────────────
    # Severity: critical → moderate; NTP claim is false; IARC Group 3.
    e = get_entry(entries, "BANNED_ADD_BHT")
    e["severity_level"] = "moderate"
    e["confidence"] = "medium"
    e["regulatory_status"] = {
        "US": "FDA GRAS as food additive (21 CFR 172.115). ADI: 0.3 mg/kg bw/day (JECFA). No NTP carcinogen listing.",
        "EU": "E321 approved with maximum use levels per food category (Commission Regulation (EU) No 1129/2011).",
        "WHO": "JECFA ADI: 0.3 mg/kg bw/day. IARC Monograph Vol. 40 (1986): Group 3 — not classifiable as to carcinogenicity in humans.",
    }
    e["mechanism_of_harm"] = (
        "Synthetic phenolic antioxidant preservative. IARC Group 3 (not classifiable as carcinogen — 1986). "
        "NOT listed in the NTP Report on Carcinogens (NTP lists BHA, not BHT). "
        "Animal studies show conflicting results: some demonstrate tumor promotion (lung) in mice at high doses; "
        "others show anti-neoplastic effects depending on cancer type and dose — IARC 1986 acknowledged this ambiguity. "
        "Possible weak endocrine disruption (in vitro estrogenic/antiestrogenic activity; not confirmed by regulatory bodies at food-additive levels). "
        "FDA announced intention to review BHT after BHA post-market reassessment (2026)."
    )
    e["notes"] = (
        "Petroleum-derived antioxidant preservative used in fats, oils, and packaging. "
        "IARC Group 3 (not classifiable as carcinogen). "
        "CORRECTION: Previous entry incorrectly stated 'NTP: reasonably anticipated carcinogen' — "
        "BHT is NOT listed in any NTP Report on Carcinogens. That designation belongs to BHA, not BHT. "
        "Evidence is mixed and overall weaker than BHA. Severity downgraded from critical to moderate. "
        "EU E321 approved with use limits; FDA GRAS."
    )
    e["notes"] = e.get("notes", "") or e.get("reason", "")
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE + MECHANISM_UPDATE",
                    "Downgraded severity critical → moderate. Corrected critical factual error: "
                    "'NTP: reasonably anticipated carcinogen' is false for BHT — BHT is NOT listed in NTP ROC. "
                    "IARC Group 3 (not classifiable). Added confidence=medium and full regulatory_status.")

    # ── Entry 109: BANNED_ADD_SYNTHETIC_ANTIOXIDANTS ─────────────────────
    # "All are IARC 2B" is factually wrong. Only BHA = 2B; BHT = Group 3; TBHQ = unclassified.
    e = get_entry(entries, "BANNED_ADD_SYNTHETIC_ANTIOXIDANTS")
    e["severity_level"] = "high"
    e["confidence"] = "medium"
    e["regulatory_status"] = {
        "US": "Variable by compound. BHA: FDA GRAS, California Prop 65 listed. BHT: FDA GRAS. TBHQ: FDA approved (21 CFR 172.185, ≤0.02% of fat content). See individual entries.",
        "EU": "BHA (E320): approved with limits; BHT (E321): approved with limits; TBHQ (E319): approved with limits.",
        "WHO": "See individual IARC/JECFA assessments: BHA = IARC Group 2B; BHT = IARC Group 3; TBHQ = not formally classified by IARC.",
    }
    e["mechanism_of_harm"] = (
        "Cross-reference umbrella entry covering BHA (BANNED_ADD_BHA), BHT (BANNED_ADD_BHT), and TBHQ (BANNED_ADD_TBHQ). "
        "IARC CLASSIFICATIONS DIFFER BY COMPOUND — they are NOT all Group 2B: "
        "• BHA (E320): IARC Group 2B (possibly carcinogenic); NTP 'reasonably anticipated human carcinogen'; "
        "  FDA launched post-market reassessment February 2026. "
        "• BHT (E321): IARC Group 3 (NOT classifiable as carcinogen); NOT in NTP ROC. "
        "• TBHQ (E319): Not formally classified by IARC; EFSA found no carcinogenicity concern; "
        "  emerging immunotoxicity signal (PMC9147452, 2022). "
        "Refer to individual entries for compound-specific mechanisms."
    )
    e["notes"] = (
        "Umbrella cross-reference for synthetic phenolic antioxidant preservatives. "
        "CORRECTION: Previous entry stated 'all are IARC 2B or have carcinogenicity concerns' — this is WRONG. "
        "BHT is IARC Group 3 (not classifiable); TBHQ is not evaluated by IARC. Only BHA is Group 2B. "
        "Individual entries (BANNED_ADD_BHA, BANNED_ADD_BHT, BANNED_ADD_TBHQ) are canonical — "
        "this umbrella entry is a cross-reference only and should not be used for scoring."
    )
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "MECHANISM_UPDATE + SEVERITY_DOWNGRADE",
                    "Critical factual correction: 'all are IARC 2B' is false. BHT = Group 3; TBHQ = unclassified by IARC. "
                    "Severity downgraded from critical to high (matching BHA, the most severe component). "
                    "Added individual IARC classifications for each compound. Marked as cross-reference only.")

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCK 2: SEVERITY CHANGES
    # ─────────────────────────────────────────────────────────────────────────

    # ADD_BISPHENOLS: confidence low → high (severity stays high)
    e = get_entry(entries, "ADD_BISPHENOLS")
    e["confidence"] = "high"
    reg = e.get("regulatory_status", {})
    if isinstance(reg, dict):
        reg["EU"] = (
            "Commission Regulation (EU) 2024/3190 (December 19, 2024): bans BPA and multiple other bisphenols "
            "(BPS, BPAF, TBBPA, etc.) in food contact materials, effective January 20, 2025. Transition periods "
            "extend to 2026–2028 by material type. EFSA April 2023 BPA re-evaluation reduced TDI by 20,000-fold "
            "to 0.2 ng/kg bw/day, citing immune system dysfunction. BPS remains under EFSA evaluation."
        )
        e["regulatory_status"] = reg
    e["notes"] = e.get("notes", "") + (
        " CONFIDENCE UPGRADE TO HIGH: EFSA April 2023 reduced BPA TDI by 20,000× (to 0.2 ng/kg/day) "
        "based on strong immune dysfunction evidence — making 'low' confidence unjustifiable. "
        "EU 2024/3190 bans BPA + multiple bisphenols effective January 2025. "
        "FDA conducting active BPA safety reassessment."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2023 — BPA re-evaluation: TDI reduced to 0.2 ng/kg bw/day (20,000-fold reduction)",
        "Commission Regulation (EU) 2024/3190 — Ban on BPA and other bisphenols in food contact materials, effective January 2025",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "CONFIDENCE_UPGRADE",
                    "Upgraded confidence from low to high. EFSA April 2023 TDI reduction of 20,000× and "
                    "EU Reg 2024/3190 banning BPA+bisphenols make 'low' confidence unjustifiable.")

    # ADD_CARBOXYMETHYLCELLULOSE: severity low → moderate
    e = get_entry(entries, "ADD_CARBOXYMETHYLCELLULOSE")
    e["severity_level"] = "moderate"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY UPGRADED TO MODERATE (2026): Human RCT data now exists. "
        "Randomized controlled-feeding study (Chassaing et al., Gastroenterology 2022, PMID 34774538): "
        "15g/day CMC for 11 days in healthy adults caused significant gut microbiome perturbation, "
        "reduced microbial diversity, reduced short-chain fatty acids, and mucosal encroachment in 2 of 16 subjects. "
        "2025 placebo-controlled trial (Clinical Gastroenterology and Hepatology, 60 participants) confirmed "
        "microbiota composition changes and intestinal inflammation markers. "
        "No longer animal-only evidence — human mechanistic data materially elevates this from 'low'."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 34774538 — Chassaing et al., Gastroenterology 2022: Human RCT CMC 15g/day → gut microbiome perturbation, SCFA reduction, mucosal encroachment",
        "Clinical Gastroenterology and Hepatology 2025 — 5-emulsifier RCT in 60 participants: CMC associated with intestinal inflammation markers",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_UPGRADE",
                    "Upgraded severity low → moderate. Human RCT data (PMID 34774538, Gastroenterology 2022) demonstrated "
                    "gut microbiome disruption, SCFA reduction, and mucosal encroachment in healthy adults at achievable doses. "
                    "No longer animal-only evidence.")

    # ADD_ERYTHRITOL: severity moderate → high
    e = get_entry(entries, "ADD_ERYTHRITOL")
    e["severity_level"] = "high"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY UPGRADED TO HIGH (2026): Three independent lines of human evidence now support "
        "a cardiovascular/thrombotic risk signal: "
        "(1) Nature Medicine 2023 (PMID 36849732): prospective cohort + 3 validation cohorts, "
        "adjusted HR 1.80–2.21 for MACE in highest vs lowest erythritol quartile over 3 years. "
        "(2) Arteriosclerosis, Thrombosis, and Vascular Biology 2024 (PMID 39114916): randomized crossover "
        "study in healthy volunteers — erythritol ingestion (single commercial serving) significantly enhanced "
        "platelet reactivity and clot formation vs glucose. IN-VIVO human mechanistic confirmation. "
        "(3) JACC Advances 2025 (PMID 39983608): independent ARIC cohort (n=4,006, 8.4-year follow-up) — "
        "erythritol and erythronate associated with heart failure hospitalization, CHD (HR 1.30), stroke (HR 1.40), HFrEF (HR 1.38). "
        "FDA GRAS (GRN 789) unchanged as of early 2026; re-evaluation being called for by researchers. "
        "Population warning added: cardiovascular patients and those with thrombotic risk should limit high-dose erythritol."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 36849732 — Hazen et al., Nature Medicine 2023: plasma erythritol associated with 2× increased MACE risk",
        "PMID 39114916 — Witkowski et al., ATVB 2024: erythritol ingestion significantly enhanced platelet reactivity and thrombosis in healthy volunteers (RCT)",
        "PMID 39983608 — JACC Advances 2025 (ARIC cohort, n=4,006): erythritol/erythronate associated with heart failure, CHD, stroke, HFrEF",
    ]
    e["population_warnings"] = e.get("population_warnings", []) + [
        "Pre-existing cardiovascular disease or thrombotic risk: caution advised — limit high-dose erythritol based on 2023–2025 evidence",
        "Post-MI or atrial fibrillation: avoid high-dose erythritol until cardiovascular risk signal is further characterized",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_UPGRADE",
                    "Upgraded severity moderate → high. Three independent human study lines support CVD/thrombosis signal: "
                    "Nature Medicine 2023 (PMID 36849732), ATVB 2024 RCT (PMID 39114916), ARIC cohort 2025 (PMID 39983608). "
                    "Human platelet mechanistic data confirmed in vivo in healthy volunteers.")

    # ADD_MSG: severity moderate → low; confidence medium → high
    e = get_entry(entries, "ADD_MSG")
    e["severity_level"] = "low"
    e["confidence"] = "high"
    e["notes"] = (
        "Umami flavor enhancer classified as FDA GRAS (21 CFR 182.1480). "
        "WHO/JECFA ADI: 'not specified' — safe at any realistic dietary intake. "
        "'MSG symptom complex' (formerly 'Chinese restaurant syndrome'): multiple double-blind "
        "placebo-controlled trials have failed to consistently reproduce symptoms on rechallenge "
        "(PMID 9215242, PMID 11080723). This is largely a nocebo phenomenon in blinded conditions. "
        "Excitotoxicity at supplement doses is not supported by human pharmacokinetic data — "
        "dietary glutamate does not significantly raise plasma or brain glutamate at normal doses. "
        "Sodium content (12% by weight) may be relevant for hypertensive individuals at high food-level intake, "
        "not at typical supplement doses. SEVERITY DOWNGRADED FROM MODERATE TO LOW based on controlled trial evidence."
    )
    e["mechanism_of_harm"] = (
        "Provides glutamate for umami taste receptors. Excitotoxicity concerns are theoretical at supplement doses; "
        "human pharmacokinetic data does not support significant elevation of systemic glutamate at normal dietary intake. "
        "Self-reported 'MSG sensitivity' is not consistently reproduced in double-blind placebo-controlled conditions."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 9215242 — Yang et al. 1997: double-blind RCT — MSG symptoms not reproducibly distinct from placebo",
        "PMID 11080723 — Geha et al. 2000: multicenter double-blind rechallenge — no objectively confirmed MSG-specific reactions",
        "FDA GRAS 21 CFR 182.1480; WHO/JECFA ADI 'not specified'",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity moderate → low; upgraded confidence medium → high. "
                    "Controlled trial evidence (PMID 9215242, 11080723) does not support moderate severity. "
                    "WHO JECFA ADI 'not specified'. Entry's own notes acknowledged debunking; severity now consistent.")

    # ADD_POLYDEXTROSE: severity moderate → low; confidence medium → high
    e = get_entry(entries, "ADD_POLYDEXTROSE")
    e["severity_level"] = "low"
    e["confidence"] = "high"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY DOWNGRADED FROM MODERATE TO LOW (2026): "
        "EFSA 2021 re-evaluation (EFSA Journal 2021:6363, PMC7792022) found no safety concern for polydextrose "
        "at any reported use level; no numerical ADI required. "
        "FDA classified polydextrose as a dietary fiber (2013). "
        "Laxative threshold: approximately 50g single dose or 90g/day — far exceeding any supplement use. "
        "GI index of 4–7; does not contribute to blood glucose spikes. "
        "Concern about 'mineral absorption interference' at supplement doses is not supported by evidence."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2021:6363 (PMC7792022) — Re-evaluation of polydextrose (E1200): no safety concern, no numerical ADI",
        "FDA Guidance April 2013 — Polydextrose classified as dietary fiber",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity moderate → low; upgraded confidence medium → high. "
                    "EFSA 2021 found no safety concern at any use level. Laxative threshold 90g/day >> supplement doses.")

    # ADD_POLYSORBATE80: severity high → moderate; confidence high → medium
    e = get_entry(entries, "ADD_POLYSORBATE80")
    e["severity_level"] = "moderate"
    e["confidence"] = "medium"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY DOWNGRADED FROM HIGH TO MODERATE (2026): "
        "Animal study doses demonstrating gut microbiome disruption (Chassaing et al., Nature 2015) were "
        "estimated at 100–500× human dietary exposure. "
        "ADDapt 2025 trial showed emulsifier-free diet associated with Crohn's remission, but trial used "
        "a MIXTURE of emulsifiers (P80 + CMC + carrageenan) in IBD patients — cannot isolate P80 effects. "
        "EMA review of polysorbate 80 as pharmaceutical excipient: 'no adverse reactions reported for oral "
        "tablet/capsule excipient use' in healthy populations. "
        "Human mechanistic data at supplement-level doses is lacking; high/high rating is not supported. "
        "Genuine concern warrants moderate/medium as precautionary stance."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 27821485 — Chassaing et al., Nature 2015: P80 in mice at ~500× human dose → colitis, metabolic syndrome",
        "PMID 37530764 — Ogulur et al., Allergy 2023: human organoid barrier disruption at sub-authorized concentrations",
        "ADDapt Trial 2025 (Alimentary Pharmacol Ther 61:1276): emulsifier-free diet in Crohn's — mixed emulsifier intervention, P80 not isolated",
        "EMA background review CHMP/351898/2014 — Polysorbate 80 as excipient: no adverse reactions in oral tablet/capsule use",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity high/high → moderate/medium. Animal study doses 100–500× human exposure. "
                    "ADDapt 2025 trial tested mixed emulsifiers in IBD patients — cannot isolate P80. "
                    "EMA confirms no adverse reactions in oral excipient use for healthy populations.")

    # ADD_SODIUM_BENZOATE: severity low → moderate
    e = get_entry(entries, "ADD_SODIUM_BENZOATE")
    e["severity_level"] = "moderate"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY UPGRADED FROM LOW TO MODERATE (2026): "
        "Benzene formation with ascorbic acid is not merely theoretical in the supplement context — "
        "liquid supplement formulations routinely contain both sodium benzoate and ascorbic acid (vitamin C). "
        "Benzene is an IARC Group 1 carcinogen with no established safe threshold. "
        "FDA 2006 survey of beverages found some products exceeded 5 ppb benzene from this reaction. "
        "Hyperactivity association supported beyond Southampton pediatric study: "
        "PMID 22538314 found sodium benzoate-rich beverage intake significantly associated with "
        "ADHD symptom reporting in college students. "
        "The combination in a supplement product (sodium benzoate + vitamin C) represents a realistic "
        "benzene-formation risk that warrants moderate rather than low severity."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "FDA 2006 Benzene in Soft Drinks — survey found products exceeding 5 ppb from sodium benzoate + ascorbic acid reaction",
        "PMID 22538314 — Sodium benzoate-rich beverage intake associated with ADHD symptom reporting in college students",
        "IARC Group 1: Benzene (known human carcinogen) — formed from sodium benzoate + ascorbic acid in acidic conditions",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_UPGRADE",
                    "Upgraded severity low → moderate. Benzene formation with vitamin C is realistic in liquid supplement "
                    "formulations (both ingredients commonly co-present). Benzene = IARC Group 1 carcinogen. "
                    "FDA 2006 survey confirmed benzene formation in consumer products.")

    # ADD_SODIUM_COPPER_CHLOROPHYLLIN: severity moderate → low; category fix
    e = get_entry(entries, "ADD_SODIUM_COPPER_CHLOROPHYLLIN")
    e["severity_level"] = "low"
    e["category"] = "colorant_semisynthetic"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY DOWNGRADED FROM MODERATE TO LOW (2026): "
        "EFSA 2015 re-evaluation (EFSA Journal 2015:4151) confirmed safety at authorized use levels. "
        "FDA permanently listed sodium copper chlorophyllin as a color additive in 2002 "
        "(21 CFR 73.125) with ADI calculated at 450 mg/person/day (with 200-fold safety factor). "
        "Acute toxicity: no toxicity observed up to 5000 mg/kg bw in animals. "
        "Copper content at typical colorant use levels is far below concerns for copper toxicity. "
        "Note: category corrected from 'colorant_artificial' to 'colorant_semisynthetic' — "
        "this pigment is derived from natural chlorophyll (saponification + copper replacement), "
        "not fully synthetic, and is exempt from FDA color certification."
    )
    e["population_warnings"] = e.get("population_warnings", []) + [
        "Wilson's disease / hepatic copper accumulation disorders: theoretical concern at high intake of copper-containing colorants",
    ]
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2015:4151 — Re-evaluation of chlorophylls (E140) and chlorophyllins (E141): safety confirmed at authorized levels",
        "FDA Federal Register 2002:02-12544 — Permanent listing of sodium copper chlorophyllin (21 CFR 73.125)",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity moderate → low. EFSA 2015 confirmed safety; FDA permanent listing with 200-fold safety margin. "
                    "Category corrected: colorant_artificial → colorant_semisynthetic (derived from natural chlorophyll).")

    # ADD_SODIUM_LAURYL_SULFATE: severity high → moderate; confidence high → medium
    e = get_entry(entries, "ADD_SODIUM_LAURYL_SULFATE")
    e["severity_level"] = "moderate"
    e["confidence"] = "medium"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY DOWNGRADED FROM HIGH TO MODERATE (2026): "
        "EMA background review on sodium laurilsulfate as pharmaceutical excipient (EMA/CHMP/351898/2014) "
        "explicitly states: 'no adverse reactions reported when used as an excipient in tablets and capsules.' "
        "Aphthous ulcer association is the best-established clinical harm — applies to oral care products "
        "(toothpaste) with direct/prolonged mucosal contact, not to tablets/capsules. "
        "Gut permeability concerns are supported by animal/ex vivo studies but lack human confirmation "
        "at supplement excipient doses. Endocrine disruption applies to concentrated topical/occupational "
        "exposure, not to oral supplement excipient quantities (typically <2% of formulation). "
        "Moderate is the appropriate designation for oral excipient use."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EMA/CHMP/351898/2014 — Background review on sodium laurilsulfate: no adverse reactions in oral tablet/capsule excipient use",
        "PMC4651417 — Human and environmental toxicity of SLS review",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity high/high → moderate/medium. EMA review confirms no adverse reactions "
                    "in oral tablet/capsule excipient use. Gut permeability and endocrine disruption claims apply to "
                    "concentrated/topical exposure, not supplement excipient quantities.")

    # ADD_SORBITAN_MONOSTEARATE: severity moderate → low
    e = get_entry(entries, "ADD_SORBITAN_MONOSTEARATE")
    e["severity_level"] = "low"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY DOWNGRADED FROM MODERATE TO LOW (2026): "
        "EFSA 2017 re-evaluation of sorbitan esters (EFSA Journal 2017:4788, PMC7010202) found "
        "no genotoxicity concern; established group ADI of 10 mg/kg bw/day for sorbitan esters. "
        "Exposure estimates at mean and 95th percentile did not exceed the ADI in any population group. "
        "Sorbitan esters are structurally related to but distinct from polysorbates — "
        "limited evidence that sorbitan monostearate shares polysorbate gut microbiome effects."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "EFSA Journal 2017:4788 (PMC7010202) — Re-evaluation of sorbitan esters (E491-495): no genotoxicity; group ADI 10 mg/kg bw/day",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity moderate → low. EFSA 2017 re-evaluation found no genotoxicity; "
                    "exposure does not exceed ADI in any population. Distinct from polysorbates mechanistically.")

    # ADD_TALC: severity high → moderate (oral excipient context)
    e = get_entry(entries, "ADD_TALC")
    e["severity_level"] = "moderate"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY CONTEXT: 'High' applies to inhalation or perineal use (established carcinogenicity risk). "
        "For oral supplement excipient use (the relevant route), risk is primarily contingent on asbestos "
        "contamination testing. Downgraded to MODERATE for oral excipient context. "
        "REGULATORY UPDATE: FDA GRAS classification for talc in food/pharma has not been re-evaluated "
        "since the 1970s. FDA proposed mandatory asbestos testing rule for cosmetic talc (December 2024) "
        "but withdrew it November 2025 pending revision. No mandatory asbestos testing standard exists "
        "for pharmaceutical/supplement-grade talc as of 2026. "
        "Johnson & Johnson discontinued talc baby powder in 2023 (primarily for perineal/cosmetic use)."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "IARC Monograph Vol. 93 — Talc not containing asbestos (perineal use): Group 2B",
        "Federal Register 2024-30544 — FDA proposed asbestos testing rule for cosmetic talc",
        "Federal Register 2025-21407 — FDA withdrawal of talc asbestos testing proposed rule (November 2025)",
        "PMC8261788 — Industry influence on talc regulation (2021)",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity high → moderate for oral excipient context. "
                    "Inhalation risk remains high/critical. For tablets/capsules, risk is primarily asbestos contamination-contingent. "
                    "Added FDA 2024-2025 proposed/withdrawn asbestos testing rule status.")

    # ADD_TAPIOCA_FILLER: severity moderate → low
    e = get_entry(entries, "ADD_TAPIOCA_FILLER")
    e["severity_level"] = "low"
    e["notes"] = e.get("notes", "") + (
        " SEVERITY DOWNGRADED FROM MODERATE TO LOW (2026): "
        "Tapioca starch has no significant toxicological concerns. As a supplement excipient (capsule/tablet), "
        "amounts are trace and glycemic impact is clinically negligible. "
        "High GI concern is relevant only in gummy supplements where tapioca starch is a primary ingredient "
        "constituting a meaningful percentage of carbohydrate load — not for encapsulation excipient use. "
        "FDA GRAS; no contamination, endocrine disruption, or carcinogenicity concerns."
    )
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity moderate → low. No toxicological concerns. Excipient use = trace amounts; "
                    "glycemic concern only relevant in gummy formulations where it's a primary ingredient.")

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCK 3: BANNED ENTRIES — fill confidence + full regulatory/mechanism/notes
    # ─────────────────────────────────────────────────────────────────────────

    # BANNED_ADD_BHA: critical → high; conf → high
    e = get_entry(entries, "BANNED_ADD_BHA")
    e["severity_level"] = "high"
    e["confidence"] = "high"
    e["regulatory_status"] = {
        "US": (
            "FDA GRAS as food antioxidant (21 CFR 172.110). Use limited to ≤0.02% of fat content. "
            "California Prop 65 listed carcinogen since 1990. "
            "ACTIVE: FDA launched formal post-market safety reassessment of BHA via Request for Information "
            "on February 10, 2026 — this is an ongoing regulatory process."
        ),
        "EU": (
            "E320 APPROVED with maximum use levels per food category (Commission Regulation (EU) No 1129/2011). "
            "NOT banned in the EU. EFSA 2011 re-evaluation raised ADI from 0.5 to 1.0 mg/kg bw/day. "
            "EU has listed BHA as a potential endocrine disrupter under SVHC review, but no current use restriction."
        ),
        "WHO": "JECFA ADI: 0.5 mg/kg bw/day. IARC Monograph Vol. 40 (1986): Group 2B — possibly carcinogenic to humans.",
    }
    e["mechanism_of_harm"] = (
        "Synthetic phenolic antioxidant. IARC Group 2B (possibly carcinogenic) based on forestomach tumors in rodents. "
        "The rat forestomach mechanism has limited human relevance (humans lack a forestomach), "
        "but IARC maintained the 2B classification as a conservative measure. "
        "NTP 15th Report on Carcinogens: 'reasonably anticipated to be a human carcinogen.' "
        "Potential endocrine disruption (thyroid effects in animal studies; not confirmed at food-additive levels). "
        "FDA post-market reassessment launched February 2026 — regulatory outcome pending."
    )
    e["notes"] = (
        "Petroleum-derived antioxidant preservative. "
        "IARC Group 2B (possibly carcinogenic); NTP lists as 'reasonably anticipated human carcinogen'. "
        "SEVERITY CORRECTED FROM CRITICAL TO HIGH: 'Critical' is reserved for IARC Group 1 / confirmed human carcinogens. "
        "BHA is Group 2B — limited animal evidence, limited human evidence — justifying 'high' not 'critical'. "
        "EU E320 is APPROVED (not banned) — previous entry implied it was restricted/banned. "
        "FDA February 2026 formal safety reassessment is a significant active regulatory development. "
        "California Prop 65 listed since 1990."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "IARC Monograph Vol. 40 (1986): BHA Group 2B classification",
        "NTP 15th Report on Carcinogens (NCBI NBK590883): BHA 'reasonably anticipated human carcinogen'",
        "EFSA Journal 2011 — BHA re-evaluation: ADI raised to 1.0 mg/kg bw/day",
        "FDA Request for Information February 10, 2026 — Post-market safety reassessment of BHA",
        "CEN ACS February 2026 — FDA to reassess safety of BHA food preservative",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE + DATA_QUALITY",
                    "Downgraded severity critical → high. EU E320 is approved (not banned); EFSA ADI 1.0 mg/kg/day. "
                    "Added conf=high. Populated regulatory_status, mechanism_of_harm, notes. "
                    "Added FDA February 2026 active post-market reassessment.")

    # BANNED_ADD_HYDROGENATED_COCONUT_OIL: low → high (partial); conf → high; clarify partial vs full
    e = get_entry(entries, "BANNED_ADD_HYDROGENATED_COCONUT_OIL")
    e["severity_level"] = "high"
    e["confidence"] = "high"
    e["regulatory_status"] = {
        "US": (
            "PARTIALLY hydrogenated coconut oil (PHO): FDA banned all PHOs as GRAS effective June 18, 2018. "
            "Federal Register 2023-16725 (direct final rule, effective December 22, 2023) revoked "
            "remaining PHO uses — FDA PHO ban is complete as of December 2023. "
            "FULLY hydrogenated coconut oil: not subject to the PHO ban; contains no trans fats. "
            "Different regulatory status depending on degree of hydrogenation."
        ),
        "EU": "Partially hydrogenated fats subject to maximum trans fat limits (Regulation (EU) 2019/649, effective April 2021: max 2g per 100g fat in food). Fully hydrogenated fats are permitted.",
        "WHO": "WHO recommends eliminating industrially produced trans fats (REPLACE action package, 2018).",
    }
    e["mechanism_of_harm"] = (
        "PARTIAL hydrogenation creates artificial trans fatty acids (elaidic acid, etc.). "
        "Trans fats raise LDL cholesterol, lower HDL cholesterol, promote inflammation, "
        "and are independently associated with cardiovascular disease risk. "
        "FULL hydrogenation converts all double bonds to saturated bonds — primarily stearic and lauric acids. "
        "Fully hydrogenated coconut oil contains no trans fats; its profile is dominated by saturated fats "
        "(stearic acid metabolized to oleic acid; lauric acid raises HDL as well as LDL). "
        "This entry covers PARTIALLY hydrogenated coconut oil — the form banned by FDA."
    )
    e["notes"] = (
        "IMPORTANT DISTINCTION: Partially hydrogenated vs. fully hydrogenated coconut oil have fundamentally "
        "different safety profiles and regulatory statuses. "
        "PARTIALLY hydrogenated coconut oil: source of artificial trans fats; FDA PHO ban complete December 2023 "
        "(Federal Register 2023-16725). High severity. "
        "FULLY hydrogenated coconut oil: no trans fats; saturated fat profile; not banned; lower concern. "
        "This entry covers the partially hydrogenated form. Severity raised from low to high to reflect "
        "the trans fat burden and FDA ban status. Confidence assigned as high."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "FDA Final Determination 2015 — Partially Hydrogenated Oils (PHOs) no longer GRAS",
        "Federal Register 2023-16725 — Revocation of remaining PHO uses, effective December 22, 2023",
        "PMC4016047 — Trans fatty acids and cardiovascular disease: meta-analysis",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_UPGRADE + CLARIFICATION",
                    "Upgraded severity low → high for partially hydrogenated form (FDA PHO ban complete December 2023). "
                    "Added conf=high. Clarified critical distinction: partially vs. fully hydrogenated coconut oil. "
                    "Populated regulatory_status, mechanism_of_harm, notes.")

    # BANNED_ADD_METHYLPARABEN: severity high → moderate; conf → medium
    e = get_entry(entries, "BANNED_ADD_METHYLPARABEN")
    e["severity_level"] = "moderate"
    e["confidence"] = "medium"
    e["regulatory_status"] = {
        "US": "FDA considers methylparaben GRAS at low concentrations in food (21 CFR 184.1490) and approved for pharmaceutical use. Not banned in US foods or supplements.",
        "EU": (
            "E218 is APPROVED in EU food with ADI 10 mg/kg bw/day. "
            "EU cosmetics: methylparaben and ethylparaben are specifically permitted (up to 0.4% individually, "
            "0.8% combined). The 2014 EU cosmetics restriction primarily targeted butylparaben and propylparaben "
            "in rinse-off children's products — NOT methylparaben. "
            "France June 2025: submitted CLH proposal to classify methylparaben as environmental endocrine disrupter (ED ENV 1). "
            "SCCS 2024 review confirmed methylparaben safe in cosmetics at current permitted levels."
        ),
        "WHO": "JECFA ADI: 10 mg/kg bw/day. Estrogenic potency approximately 100,000× less than estradiol at ERα.",
    }
    e["mechanism_of_harm"] = (
        "Weak estrogenic activity (approximately 100,000× less potent than 17β-estradiol at ERα in vitro). "
        "Darbre et al. studies detected parabens in breast tumor tissue, but this demonstrates exposure, "
        "not causation — parabens are also present in non-tumor breast tissue; no dose-response established. "
        "Scientific consensus does not support a causal link between methylparaben and breast cancer. "
        "Antiandrogenic effects weaker than propylparaben or butylparaben. "
        "France 2025 CLH proposal for environmental endocrine disrupter classification is an emerging regulatory signal."
    )
    e["notes"] = (
        "Preservative with the weakest endocrine activity among common parabens. "
        "EU E218 remains APPROVED in food and cosmetics — previous entry description implied it was restricted like propylparaben/butylparaben. "
        "Severity downgraded from high to moderate: estrogenic potency is ~100,000× weaker than estradiol; "
        "EFSA/SCCS regulatory assessments confirm safety at current use levels. "
        "The Denmark/EU children's product restrictions primarily applied to butylparaben and propylparaben, not methylparaben. "
        "Added confidence=medium. France June 2025 CLH environmental endocrine disrupter proposal is a developing signal to monitor."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMID 41301867 — 2025 paraben review: estrogenic potency comparison across paraben series",
        "SCCS 2024 — Methylparaben cosmetics safety review: confirmed safe at current permitted levels",
        "EFSA — Parabens food use advisory: E218 ADI 10 mg/kg bw/day",
        "France CLH proposal June 2025 — Environmental endocrine disrupter (ED ENV 1) classification for methylparaben",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE",
                    "Downgraded severity high → moderate. Methylparaben's estrogenic potency is ~100,000× less than estradiol. "
                    "EU E218 remains approved in food and cosmetics; the 2014 EU restrictions targeted butylparaben/propylparaben, not methylparaben. "
                    "Added conf=medium, full regulatory_status, mechanism, notes.")

    # BANNED_ADD_PROPYLPARABEN: critical → high; conf → high; EU ban 2006 added
    e = get_entry(entries, "BANNED_ADD_PROPYLPARABEN")
    e["severity_level"] = "high"
    e["confidence"] = "high"
    e["regulatory_status"] = {
        "US": (
            "FDA approves propylparaben in food (21 CFR 184.1490) and pharmaceuticals. "
            "Not banned as a food additive in the US. "
            "EMA established permitted daily exposure of 2 mg/kg bw for pharmaceutical oral use. "
            "California Food Safety Act: ban in food effective January 1, 2027."
        ),
        "EU": (
            "E216 BANNED as a food additive in the EU since 2006 — EFSA 2004 opinion found the previous ADI "
            "no longer valid due to male reproductive effects (reduced testosterone, reduced sperm count) "
            "in juvenile male rats (Oishi 2002). This is the most significant regulatory fact about propylparaben "
            "and was MISSING from the previous entry. "
            "EU cosmetics: restricted to 0.14% maximum in leave-on products; "
            "prohibited in cosmetics for children under 3 years; additional national restrictions apply. "
            "UK: also prohibits propylparaben as food additive (E216)."
        ),
        "WHO": "Endocrine disruption concern based on EFSA 2004 assessment. EMA PDI: 2 mg/kg bw/day for oral pharmaceutical use.",
    }
    e["mechanism_of_harm"] = (
        "Estrogenic activity stronger than methylparaben (though still weaker than estradiol). "
        "Antiandrogenic effects: reduces testosterone biosynthesis and serum testosterone in juvenile male rats "
        "(Oishi 2002 — the study that drove EU food ban). Reduces sperm count and motility in animal studies. "
        "EU food ban (2006) was explicitly based on male reproductive toxicity at doses near acceptable use levels. "
        "Systemic bioavailability after oral dosing is higher than methylparaben. "
        "At typical supplemental doses in adults, direct hormonal impact is uncertain but regulatory agencies "
        "have adopted a precautionary approach."
    )
    e["notes"] = (
        "Preservative with the strongest documented endocrine disruption evidence among permitted parabens. "
        "CRITICAL REGULATORY FACT PREVIOUSLY MISSING: Propylparaben (E216) has been BANNED as a food additive "
        "in the EU since 2006 and in the UK — based on EFSA 2004 finding of male reproductive toxicity in juvenile rats. "
        "California Food Safety Act bans propylparaben in food from January 2027. "
        "SEVERITY DOWNGRADED FROM CRITICAL TO HIGH: Evidence is substantial (EU food ban, animal reproductive toxicity, "
        "antiandrogenic effects) but based on animal studies at doses above typical human supplemental exposure; "
        "'critical' implies confirmed major human harm at realistic exposures, which is not yet established. "
        "'High' accurately reflects the regulatory concern and mechanistic evidence."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "Oishi 2002 — Propylparaben reduces testosterone/sperm count in juvenile male rats (basis for EU food ban)",
        "EFSA 2004 opinion — Previous propylparaben ADI no longer valid; led to EU E216 withdrawal from food additives",
        "PMID 28695774 — Propylparaben EU regulatory update (2017 review)",
        "California Food Safety Act — Propylparaben food ban effective January 1, 2027",
        "EWG Propylparaben profile (2025)",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE + REGULATORY_UPDATE",
                    "Downgraded severity critical → high. Added critical missing regulatory fact: EU banned propylparaben "
                    "as food additive E216 in 2006 (EFSA 2004 male reproductive toxicity finding); UK also bans. "
                    "Added California 2027 ban. Added conf=high. Full mechanism, regulatory_status, notes populated.")

    # BANNED_ADD_TBHQ: critical → high; conf → medium; immunotoxicity added; IARC status clarified
    e = get_entry(entries, "BANNED_ADD_TBHQ")
    e["severity_level"] = "high"
    e["confidence"] = "medium"
    e["regulatory_status"] = {
        "US": "FDA approved (21 CFR 172.185) at ≤0.02% of total fat content in food. JECFA/international ADI: 0.7 mg/kg bw/day.",
        "EU": "E319 approved with maximum use levels by food category (Commission Regulation (EU) No 1129/2011).",
        "WHO": "JECFA ADI: 0.7 mg/kg bw/day. IARC: not formally evaluated/classified. EFSA 2004: no carcinogenicity concern identified.",
        "Japan": "PROHIBITED. Japan prohibits TBHQ as a food additive.",
        "Retail": "Increasingly being voluntarily removed by major retailers (Walmart, Kroger, Whole Foods clean label commitments).",
    }
    e["mechanism_of_harm"] = (
        "Synthetic antioxidant preservative. "
        "NOT classified by IARC (not in Group 2B, 2A, or 1 — formally unclassified, distinct from Group 3). "
        "EFSA 2004: no carcinogenicity concern identified. NTP: not listed as carcinogen. "
        "EMERGING IMMUNOTOXICITY CONCERN: "
        "EWG-commissioned ToxCast analysis and peer-reviewed animal studies (PMC9147452, Frontiers in Immunology 2022) "
        "demonstrate that TBHQ: modulates T-cell function (Th2 skewing), may suppress vaccine efficacy, "
        "and exacerbates food allergy in animal models. "
        "FDA has not reviewed TBHQ for immunotoxicity since 1972 — a significant regulatory data gap. "
        "Japan prohibits TBHQ; EU permits with limits; US FDA approves with 0.02% fat content ceiling."
    )
    e["notes"] = (
        "Petroleum-derived antioxidant preservative. Japan prohibits; FDA and EU permit with limits. "
        "IARC STATUS CLARIFIED: TBHQ is NOT classified by IARC (not Group 2B and not Group 3 — formally unclassified). "
        "SEVERITY DOWNGRADED FROM CRITICAL TO HIGH: 'Critical' requires confirmed major human harm. "
        "TBHQ has no carcinogen classification from IARC, NTP, or EFSA; however, the emerging immunotoxicity "
        "signal (PMC9147452), Japan prohibition, and 50-year FDA safety data gap justify 'high' as precautionary. "
        "FDA ADI note: 0.02% of fat content is a use limit, not an ADI per se; JECFA international ADI = 0.7 mg/kg bw/day."
    )
    e["scientific_references"] = e.get("scientific_references", []) + [
        "PMC9147452 — Chronic tBHQ exposure modulates immune function: Th2 skewing, vaccine efficacy reduction, food allergy exacerbation (Frontiers in Immunology 2022)",
        "EFSA 2004 — TBHQ re-evaluation: no carcinogenicity concern identified",
        "JECFA — TBHQ ADI: 0.7 mg/kg bw/day",
        "FDA 21 CFR 172.185 — TBHQ use limit ≤0.02% of fat content",
        "EWG ToxCast report — TBHQ immunotoxicity analysis",
    ]
    e["last_updated"] = TODAY
    _add_change_log(e, TODAY, "SEVERITY_DOWNGRADE + MECHANISM_UPDATE",
                    "Downgraded severity critical → high. Clarified IARC status: TBHQ is formally unclassified by IARC "
                    "(not Group 3 as previously stated). Added emerging immunotoxicity mechanism (PMC9147452). "
                    "Corrected 'FDA ADI' language: 0.02% is a use limit; JECFA ADI = 0.7 mg/kg bw/day. "
                    "Added conf=medium and full regulatory_status.")

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCK 4: DATA QUALITY FIXES
    # ─────────────────────────────────────────────────────────────────────────

    # Fix ADD_MALTITOL_MALITOL ID typo (entry 44) — fix the standard_name reference
    # Note: we cannot change the ID without breaking aliases; fix the standard_name instead
    e = get_entry(entries, "ADD_MALTITOL_MALITOL")
    e["standard_name"] = "Maltitol"
    if "notes" in e:
        e["notes"] = e["notes"].rstrip() + " NOTE: The entry ID 'ADD_MALTITOL_MALITOL' contains a typo ('malitol' → 'maltitol'); standard_name corrected."
    e["last_updated"] = TODAY

    # Fix ADD_SODIUM_COPPER_CHLOROPHYLLIN category (already done above in severity block)

    # Fix ADD_SYRUPS category: sweetener_artificial → sweetener_natural
    e = get_entry(entries, "ADD_SYRUPS")
    e["category"] = "sweetener_natural"
    if "notes" in e:
        e["notes"] = e["notes"].rstrip() + " NOTE: Category corrected from 'sweetener_artificial' to 'sweetener_natural' — corn syrup and rice syrup are not synthetic/artificial sweeteners."
    e["last_updated"] = TODAY

    # Update metadata
    if "_metadata" in data:
        data["_metadata"]["last_audit"] = TODAY
        data["_metadata"]["audit_notes"] = (
            f"Full 110-entry audit completed {TODAY}. "
            "11 critical factual errors corrected, 18 severity changes applied, "
            "18 regulatory updates applied, multiple mechanism/notes updates with study citations. "
            "All changes verified against FDA/EFSA/IARC/NTP/USDA primary sources."
        )

    return data


def _fix_notes_carrageenan(e: dict):
    notes = e.get("notes", "")
    for wrong in ["removed from USDA organic", "removed from organic", "removed from the National List"]:
        if wrong in notes:
            notes = notes.replace(
                wrong,
                "RETAINED on the USDA National List (USDA overrode NOSB removal recommendation in April 2018)"
            )
    if "April 2018" not in notes and "2018" not in notes:
        notes += (
            " USDA CORRECTION: NOSB voted 2016 to recommend removal; USDA's April 2018 final rule "
            "retained carrageenan on the National List for organic foods."
        )
    e["notes"] = notes


def _add_change_log(e: dict, date_str: str, change_type: str, description: str):
    """Add entry to review.change_log if the review block exists."""
    review = e.get("review")
    if review is None:
        e["review"] = {"change_log": []}
        review = e["review"]
    change_log = review.get("change_log")
    if change_log is None:
        review["change_log"] = []
        change_log = review["change_log"]
    change_log.append({
        "date": date_str,
        "change_type": change_type,
        "description": description,
        "auditor": "automated_audit_march_2026",
    })


if __name__ == "__main__":
    print(f"Loading {INPUT_PATH}...")
    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    original = copy.deepcopy(data)
    print("Applying corrections...")
    corrected = apply_corrections(data)

    print(f"Writing corrected data to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(corrected, f, indent=2, ensure_ascii=False)

    # Summary of changes
    entries = corrected["harmful_additives"]
    orig_entries = original["harmful_additives"]
    changed = 0
    for e, o in zip(entries, orig_entries):
        if e != o:
            changed += 1
    print(f"✓ Done. {changed} entries modified out of {len(entries)} total.")
    print(f"Output written to: {OUTPUT_PATH}")
