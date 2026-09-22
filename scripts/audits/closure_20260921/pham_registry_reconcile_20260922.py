"""Reconcile the clinical strain registry DATA against Dr Pham's 2026-09-22 packet.

    python3 scripts/audits/closure_20260921/pham_registry_reconcile_20260922.py [--out rows.json]

Prints the per-strain table and every finding; exits 1 on any FAIL. Uses the production owners
(probiotic_measurements, studied_formulas, enrich_supplements_v3) so the
table reports what the pipeline will do, not a re-derivation.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import logging
logging.disable(logging.CRITICAL)

from probiotic_measurements import (derived_context_evidence, effective_strain_evidence,
                                    identity_review_accepted, strain_literature_review_concluded,
                                    clinical_strain_research_scope, context_accepted_for_scoring)
from studied_formulas import valid_native_study_context

from enrich_supplements_v3 import (_PROBIOTIC_RESULT_STATED, _derive_clinical_support_level,
                                    _probiotic_research_presentation)

DATA = json.loads((ROOT / "scripts/data/clinically_relevant_strains.json").read_text())
REG = {e["id"]: e for e in DATA["clinically_relevant_strains"]}
CFG = json.loads((ROOT / "scripts/scoring_v4/config/quality_score.json").read_text())["evidence_magnitudes"]["probiotic"]
POINTS, MULT = CFG["native_strain_evidence_points"], CFG["effect_direction_multipliers"]
POSITIVE = {"positive_strong", "positive_weak"}


# Dr Pham packet: decision, expected sign-off, allowed effective directions,
# PMIDs that must be present, citations she withdrew/replaced for THIS strain.
PACKET = {
    "STRAIN_LACTIS_BI07": dict(dec="1a A: sign off; single-strain = acute lactose-challenge surrogate 36149331; 21436726 combination only",
                               signoff=True, dirs={"unresolved"}, need={"36149331"}, combo={"21436726"}, max_pts=0),
    "STRAIN_LACTIS_BB12": dict(dec="1b A: sign off; human evidence reviewed, mixed/limited",
                               signoff=True, dirs={"mixed", "null", "unresolved"}, need={"26382580", "39271904"}),
    "STRAIN_ACIDOPHILUS_LA5": dict(dec="withdraw single-strain; 1c A: 30439760 + 39102225 literal combinations",
                                   signoff=False, terminal=True, withdrawn={"34405373"}, combo={"30439760", "39102225"}, max_pts=0),
    "STRAIN_LGG": dict(dec="confirm; medium (moderate QoE)", signoff=True, strength="medium", dirs=POSITIVE),
    "STRAIN_SACCHAROMYCES": dict(dec="confirm; medium (moderate QoE)", signoff=True, strength="medium", dirs=POSITIVE),
    "STRAIN_CASEI_SHIROTA": dict(dec="confirm; null, no efficacy credit", signoff=True, dirs={"null"}, max_pts=0),
    "STRAIN_COAGULANS_MTCC5856": dict(dec="confirm", signoff=True),
    "STRAIN_REUTERI_DSM17938": dict(dec="confirm", signoff=True),
    "STRAIN_K12": dict(dec="confirm", signoff=True),
    "STRAIN_LACTIS_HN019": dict(dec="confirm; null, no efficacy credit", signoff=True, dirs={"null"}, max_pts=0),
    "STRAIN_PLANTARUM_299V": dict(dec="confirm; medium (n = 40)", signoff=True, strength="medium"),
    "STRAIN_INFANTIS_35624": dict(dec="confirm; null, no efficacy credit", signoff=True, dirs={"null"}, max_pts=0),
    "STRAIN_LONGUM_BB536": dict(dec="confirm", signoff=True),
    "STRAIN_RHAMNOSUS_HN001": dict(dec="confirm; medium (mood outcome secondary)", signoff=True, strength="medium"),
    "STRAIN_RHAMNOSUS_SP1": dict(dec="confirm", signoff=True),
    "STRAIN_COAGULANS_SNZ1969": dict(dec="replace 36372047 -> 34119240", signoff=True, need={"34119240"}, withdrawn={"36372047"}),
    "STRAIN_M18": dict(dec="replace 32250565 (in vitro) -> 23449874 (+37764667)", signoff=True, need={"23449874"}, withdrawn={"32250565"}),
    "STRAIN_COAGULANS_GBI30": dict(dec="replace 29196920 (narrative review) -> 33110439", signoff=True, need={"33110439"}, withdrawn={"29196920"}),
    "STRAIN_REUTERI_ATCC6475": dict(dec="replace 36261538 (responder secondary) -> 29926979", signoff=True, need={"29926979"}, withdrawn={"36261538"}),
    "STRAIN_CRISPATUS_CTV05": dict(dec="replace 35659905 -> 32402161 (35659905 supportive only)", signoff=True, need={"32402161"}, withdrawn_primary={"35659905"}),
    "STRAIN_PLANTARUM_HEAL9": dict(dec="withdraw 31734734 as single-strain (HEAL9 + 8700:2)", signoff=False, withdrawn={"31734734"}, combo={"31734734"}),
    "STRAIN_RHAMNOSUS_GR1": dict(dec="withdraw 12628548 as single-strain (GR-1 + RC-14)", signoff=False, terminal=True, withdrawn={"12628548"}, combo={"12628548"}, max_pts=0),
    "STRAIN_FERMENTUM_RC14": dict(dec="withdraw 12628548 as single-strain (GR-1 + RC-14)", signoff=False, terminal=True, withdrawn={"12628548"}, max_pts=0),
    "STRAIN_HELVETICUS_R0052": dict(dec="withdraw 20974015 as single-strain (R0052 + R0175)", signoff=False, terminal=True, withdrawn={"20974015"}, combo={"20974015"}, max_pts=0),
    "STRAIN_LONGUM_R0175": dict(dec="withdraw 20974015 as single-strain (R0052 + R0175)", signoff=False, terminal=True, withdrawn={"20974015"}, max_pts=0),
    "STRAIN_SUBTILIS_CU1": dict(dec="section 3: proceed; primary null, respiratory finding post hoc n = 44; 27825987 safety data"),
    "STRAIN_NISSLE_1917": dict(dec="15479682 active-comparator equivalence, medium, no superiority credit", signoff=True, need={"15479682"}, dirs={"unresolved"}, max_pts=0),
}

FAILS, INFOS = [], []
def fail(sid, check, detail): FAILS.append((sid, check, detail))
def info(sid, check, detail): INFOS.append((sid, check, detail))


def summary(e):
    return (e.get("cfu_thresholds") or {}).get("evidence") or {}


def scoring_pmids(e):
    """PMIDs that can produce points for this identity: the effective summary's
    citations, or the accepted exact-strain contexts when those own the evidence."""
    ev = effective_strain_evidence(e) or {}
    out = {p for p in [ev.get("pmid"), *(ev.get("additional_pmids") or [])] if p}
    for c in e.get("study_contexts") or []:
        if c["context_id"] in (ev.get("derived_from_contexts") or []):
            out |= set(c["source_pmids"])
    return out


def points_possible(e):
    ev = effective_strain_evidence(e) or {}
    scope = clinical_strain_research_scope(e)
    if not scope.get("human_evidence") or not (identity_review_accepted(e)):
        return 0.0
    support = ev.get("clinical_support_level") or ev.get("evidence_strength") or "weak"
    support = {"strong": "high", "medium": "moderate"}.get(support, support)
    return round(POINTS.get(support, 0.0) * MULT.get(str(ev.get("effect_direction") or "").replace(" ", "_"), 0.0), 2)


def disposition(e):
    pres = _probiotic_research_presentation(e)
    ev = effective_strain_evidence(e) or {}
    return pres["review_status"], pres["research_match_status"], ev.get("effect_direction")


# ---------------------------------------------------------------- per-strain table
rows = []
for sid, exp in PACKET.items():
    e = REG[sid]
    t = e["cfu_thresholds"]
    ev = summary(e)
    eff = effective_strain_evidence(e) or {}
    ctxs = e.get("study_contexts") or []
    single = [c for c in ctxs if c["identity_scope"] == "exact_strain"]
    combos = [c for c in ctxs if c["identity_scope"] == "combination"]
    rs, ms, direction = disposition(e)
    pts = points_possible(e)
    spm = scoring_pmids(e)
    old = [x for x in [(ev.get("previous_citation") or {}).get("pmid"),
                       ((e.get("literature_review") or {}).get("withdrawn_citation") or {}).get("pmid")] if x]
    primaries = collections.Counter()
    for c in single:
        for o in c["outcomes"]:
            primaries[(o.get("hierarchy"), o.get("kind"))] += 1
    rows.append(dict(
        id=sid, name=e["standard_name"], ctx_review=sorted({c["review_status"] for c in ctxs}) or ["-"],
        decision=exp["dec"], old=old, final=sorted(spm), single=len(single), combination=len(combos),
        primary_kinds={f"{h}:{k}": n for (h, k), n in primaries.items()}, direction=direction, strength=eff.get("evidence_strength"),
        eligible=sum(1 for c in ctxs if context_accepted_for_scoring(c)), points=pts,
        signoff=t.get("dr_pham_signoff"), disposition=f"{rs}/{ms}", support=_derive_clinical_support_level(e),
        indication=t.get("indication_primary")))

    if "signoff" in exp and t.get("dr_pham_signoff") is not exp["signoff"]:
        fail(sid, "signoff", f"expected {exp['signoff']}, got {t.get('dr_pham_signoff')}")
    if t.get("dr_pham_signoff") is True and "Pham" not in str(t.get("dr_pham_signoff_verified_by") or ""):
        fail(sid, "clinician_review_overwritten", t.get("dr_pham_signoff_verified_by"))
    if "dirs" in exp and direction not in exp["dirs"]:
        fail(sid, "direction", f"expected one of {sorted(exp['dirs'])}, got {direction}")
    if "strength" in exp and eff.get("evidence_strength") != exp["strength"]:
        fail(sid, "strength", f"expected {exp['strength']}, got {eff.get('evidence_strength')}")
    if "max_pts" in exp and pts > exp["max_pts"]:
        fail(sid, "points", f"expected <= {exp['max_pts']}, got {pts}")
    all_pmids = {p for c in ctxs for p in c["source_pmids"]} | spm
    for p in exp.get("need", ()):
        if p not in all_pmids:
            fail(sid, "replacement_missing", p)
    for p in exp.get("withdrawn", ()):
        if p in spm:
            fail(sid, "withdrawn_citation_scores", p)
    for p in exp.get("withdrawn_primary", ()):
        if eff.get("pmid") == p:
            fail(sid, "withdrawn_citation_is_primary", p)
    for p in exp.get("combo", ()):
        owners = [c for c in ctxs if p in c["source_pmids"]]
        if not owners:
            fail(sid, "combination_record_missing", p)
        for c in owners:
            if c["identity_scope"] != "combination" or len(c["components"]) < 2:
                fail(sid, "combination_attached_as_single", c["context_id"])
    if exp.get("terminal"):
        if not strain_literature_review_concluded(e) or rs != "literature_reviewed_no_qualifying_evidence":
            fail(sid, "not_terminal_no_qualifying", rs)
        if e.get("key_benefits"):
            fail(sid, "benefits_on_no_evidence", e["key_benefits"])
        if e.get("evidence_level") != "none":
            fail(sid, "stale_evidence_level", e.get("evidence_level"))
    if rs == "pending_review":
        fail(sid, "unreviewed", "review_status pending_review")

# Section 3 CU1 copy
cu1 = REG["STRAIN_SUBTILIS_CU1"]["study_contexts"][0]
lim = " ".join(cu1["limitations"]).lower()
if not ("post hoc" in lim and "44" in lim and "safety" in lim):
    fail("STRAIN_SUBTILIS_CU1", "cu1_copy", cu1["limitations"])
if "fewer respiratory infections" in json.dumps(REG["STRAIN_SUBTILIS_CU1"]).lower():
    fail("STRAIN_SUBTILIS_CU1", "cu1_copy", "old 'fewer respiratory infections' wording present")

# LA-5 combination records: literal components, unregistered status
for cid, token in (("la5_bb12_lc01_yogurt_aad_30439760", "LC-01"),
                   ("la5_bb12_primal_preterm_mdro_39102225", "infantis")):
    c = next(c for c in REG["STRAIN_ACIDOPHILUS_LA5"]["study_contexts"] if c["context_id"] == cid)
    if c["component_registration_status"] != "unregistered_components_present" or not any(
            token in x and x.startswith("UNREGISTERED:") for x in c["components"]):
        fail("STRAIN_ACIDOPHILUS_LA5", "combination_literal_components", cid)
    if c["review_status"] != "clinician_approved":
        fail("STRAIN_ACIDOPHILUS_LA5", "combination_not_approved", cid)

# ---------------------------------------------------------------- global checks (all 132)
def norm_name(s):
    s = s.lower().replace("lactobacillus", "l").replace("lacticaseibacillus", "l").replace("bifidobacterium", "b")
    return re.sub(r"[^a-z0-9]", "", s)

alias_owner = collections.defaultdict(set)
name_owner = collections.defaultdict(set)
ctx_ids = collections.Counter()
for sid, e in REG.items():
    name_owner[norm_name(e["standard_name"])].add(sid)
    seen = collections.Counter(a.strip().lower() for a in e.get("aliases") or [])
    for a, n in seen.items():
        if n > 1:
            fail(sid, "alias_case_duplicate", a)
        alias_owner[re.sub(r"\s+", " ", a)].add(sid)
    for c in e.get("study_contexts") or []:
        ctx_ids[c["context_id"]] += 1
for k, v in name_owner.items():
    if len(v) > 1:
        fail(",".join(sorted(v)), "two_ids_one_strain", k)
for k, v in alias_owner.items():
    if len(v) > 1:
        fail(",".join(sorted(v)), "alias_across_parents", k)
for k, n in ctx_ids.items():
    if n > 1:
        fail(k, "duplicate_context_id", n)
for k, n in collections.Counter(e["id"] for e in DATA["clinically_relevant_strains"]).items():
    if n > 1:
        fail(k, "duplicate_registry_id", n)

# A PMID in both a combination record and a single-strain record is only valid
# when the trial had a separate single-strain arm (verified against the source).
SEPARATE_ARM_TRIALS = {
    # Three arms (PubMed abstract, 2026-09-22): placebo, S. boulardii CNCM I-745
    # alone, and Bactiol duo (unnamed S. boulardii + NCFM, Lpc-37, Bl-04, Bi-07).
    "33763399": {"STRAIN_BOULARDII_CNCM_I745"},
}
combo_owner, single_owner = collections.defaultdict(set), collections.defaultdict(set)
for e in REG.values():
    for c in e.get("study_contexts") or []:
        target = combo_owner if c["identity_scope"] == "combination" else single_owner
        for p in c["source_pmids"]:
            target[p].update(c["components"])
for p in set(combo_owner) & set(single_owner):
    if single_owner[p] - SEPARATE_ARM_TRIALS.get(p, set()):
        fail(p, "pmid_in_combination_and_single_strain_record", sorted(single_owner[p]))

for sid, e in REG.items():
    t = e["cfu_thresholds"]
    ev = summary(e)
    eff = effective_strain_evidence(e) or {}
    ctxs = e.get("study_contexts") or []
    rs, ms, direction = disposition(e)
    # duplicate context within a strain: same PMIDs + condition + outcome set
    keys = collections.Counter(
        (tuple(sorted(c["source_pmids"])), c["condition"], tuple(sorted(o.get("name", o.get("measure", "")) for o in c["outcomes"])))
        for c in ctxs)
    for k, n in keys.items():
        if n > 1:
            fail(sid, "duplicate_context_same_pmid_outcome", k[:2])
    fam = collections.defaultdict(set)
    for c in ctxs:
        for p in c["source_pmids"]:
            fam[p].add(c["trial_family"])
    for p, fams in fam.items():
        if len(fams) > 1:
            info(sid, "one_pmid_several_trial_families", f"{p}: {sorted(fams)}")
    # review status
    for c in ctxs:
        if c["review_status"] not in ("clinician_approved", "rejected_source"):
            fail(sid, "stale_context_review_status", f"{c['context_id']}={c['review_status']}")
        if not valid_native_study_context(c, sid) and context_accepted_for_scoring(c):
            info(sid, "approved_context_invalid_for_owner", c["context_id"])
    if rs == "pending_review":
        fail(sid, "unreviewed_identity", ms)
    # combination credited to a component
    d = derived_context_evidence(e) or {}
    for cid in d.get("derived_from_contexts") or []:
        c = next(x for x in ctxs if x["context_id"] == cid)
        if c["identity_scope"] != "exact_strain" or c["components"] != [sid]:
            fail(sid, "combination_credited_to_component", cid)
    # summary citing a PMID that is only ever a combination record
    combo_pmids = {p for x in REG.values() for c in x.get("study_contexts") or []
                   if c["identity_scope"] == "combination" for p in c["source_pmids"]}
    single_pmids = {p for c in ctxs if c["identity_scope"] == "exact_strain" for p in c["source_pmids"]}
    if ev.get("pmid") in combo_pmids and ev.get("pmid") not in single_pmids:
        fail(sid, "summary_cites_combination_record", ev.get("pmid"))
    # stale fields
    q3 = str((ev.get("clinical_validation") or {}).get("q3_human_clinical") or "").upper()
    typ = str(ev.get("type") or "").lower()
    if ev and q3 == "YES" and any(x in typ for x in ("in_vitro", "animal", "narrative")):
        fail(sid, "stale_q3_human_clinical", f"q3 YES on type {typ}")
    if ev and q3 in ("NO", "UNCLEAR") and any(x in typ for x in ("rct", "meta_analysis", "guideline")):
        fail(sid, "stale_q3_human_clinical", f"q3 {q3} on type {typ}")
    human = clinical_strain_research_scope(e).get("human_evidence")
    if strain_literature_review_concluded(e) and human:
        fail(sid, "stale_human_evidence", "concluded no-qualifying review but human_evidence True")
    lvl = e.get("evidence_level")
    want = ("none" if strain_literature_review_concluded(e) else
            {"strong": "high", "medium": "moderate", "weak": "low"}.get(eff.get("evidence_strength")) if eff else None)
    if want and lvl != want:
        fail(sid, "stale_evidence_level", f"{lvl} (effective strength {eff.get('evidence_strength')} -> {want})")
    csl, strength = ev.get("clinical_support_level"), ev.get("evidence_strength")
    if csl and strength and {"strong": "high", "medium": "moderate", "weak": "weak"}.get(strength) != csl:
        fail(sid, "support_level_disagrees_with_strength", f"{csl} vs {strength}")
    if t.get("dr_pham_signoff") is True and strain_literature_review_concluded(e):
        fail(sid, "conflicting_signoff", "signed off and concluded no-qualifying")
    if t.get("dr_pham_signoff") is not True and summary(e):
        fail(sid, "suspended_summary_hold", "legacy summary without sign-off (clinician hold)")
    if ev and not ev.get("effect_direction"):
        fail(sid, "missing_direction", ev.get("pmid"))
    # copy vs direction: the card shows "<support> support · <indication>"
    support = _derive_clinical_support_level(e)
    if support and direction not in POSITIVE and not (direction == "mixed" and support == "weak"):
        fail(sid, "support_copy_disagrees_with_direction", f"'{support} support' on {direction}")
    shown = _probiotic_research_presentation(e)["indication_primary"]
    if rs in ("pending_review", "literature_reviewed_no_qualifying_evidence") and shown:
        fail(sid, "indication_without_qualifying_evidence", shown)
    elif shown and direction not in POSITIVE and not _PROBIOTIC_RESULT_STATED.search(shown):
        fail(sid, "indication_copy_disagrees_with_direction", f"{direction}: {shown}")
    withdrawn = [(ev.get("previous_citation") or {}).get("pmid"),
                 ((e.get("literature_review") or {}).get("withdrawn_citation") or {}).get("pmid")]
    for p in filter(None, withdrawn):
        if p in str(e.get("notable_studies") or "") and "withdraw" not in str(e.get("notable_studies")).lower():
            fail(sid, "withdrawn_citation_in_notable_studies", p)

print(f"{'strain':28} {'dir':15} {'str':7} {'pts':>5} {'sign':5} {'1x/cmb':6} disposition / support / indication")
for r in rows:
    print(f"{r['id'][7:35]:28} {str(r['direction']):15} {str(r['strength']):7} {r['points']:>5} {str(r['signoff']):5} "
          f"{r['single']}/{r['combination']:<4} {r['disposition']} / {r['support']} / {r['indication']}")
    print(f"{'':28} old={r['old']} final={r['final']} eligible={r['eligible']} ctx_review={r['ctx_review']} kinds={r['primary_kinds']}")
if "--out" in sys.argv:
    Path(sys.argv[sys.argv.index("--out") + 1]).write_text(json.dumps(rows, indent=1, default=str) + "\n")
print(f"\nFAIL {len(FAILS)}")
for f in FAILS:
    print("  FAIL", *f)
print(f"INFO {len(INFOS)}")
for i in INFOS:
    print("  info", *i)
sys.exit(1 if FAILS else 0)
