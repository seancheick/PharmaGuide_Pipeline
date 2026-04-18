"""Safety Copy Coverage — Path C authored-field surface.

Shows clinical-review authoring coverage across all six data files
Dr. Pham authored, so you can spot staleness or missing fields before
they leak into production.

Files covered:
- medication_depletions.json (alert_headline, alert_body,
  acknowledgement_note, monitoring_tip_short, food_sources_short,
  adequacy_threshold_*)
- banned_recalled_ingredients.json (ban_context, safety_warning,
  safety_warning_one_liner)
- ingredient_interaction_rules.json (alert_headline, alert_body,
  informational_note on each severe sub-rule + pregnancy_lactation
  block)
- harmful_additives.json (safety_summary, safety_summary_one_liner)
- synergy_cluster.json (synergy_benefit_short)
- manufacturer_violations.json (brand_trust_summary)
"""
from __future__ import annotations

import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FLUTTER_ASSETS = Path("/Users/seancheick/PharmaGuide ai/assets/reference_data")


def _safe_read(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _banned_recalled_summary(d):
    entries = d.get("recalled_ingredients") or d.get("ingredients") or []
    total = len(entries)
    fields = ("ban_context", "safety_warning", "safety_warning_one_liner")
    counts = {f: sum(1 for e in entries if e.get(f)) for f in fields}
    by_ban_context = Counter(e.get("ban_context") for e in entries)
    return {
        "total": total,
        "field_counts": counts,
        "ban_context_distribution": dict(by_ban_context),
        "entries": entries,
    }


def _depletions_summary(d):
    entries = d.get("medication_depletions") or []
    total = len(entries)
    fields = ("alert_headline", "alert_body", "acknowledgement_note",
              "monitoring_tip_short", "food_sources_short")
    counts = {f: sum(1 for e in entries if e.get(f)) for f in fields}
    with_threshold = sum(
        1 for e in entries
        if e.get("adequacy_threshold_mcg") is not None
        or e.get("adequacy_threshold_mg") is not None
    )
    return {
        "total": total,
        "field_counts": counts,
        "with_adequacy_threshold": with_threshold,
        "entries": entries,
    }


def _interaction_rules_summary(d):
    rules = d.get("interaction_rules") or []
    severe_total = severe_authored = 0
    nonsevere_total = nonsevere_authored = 0
    pl_total = pl_authored = 0
    for r in rules:
        for key in ("condition_rules", "drug_class_rules"):
            for sub in r.get(key) or []:
                sev = (sub.get("severity") or "").lower()
                has = bool(sub.get("alert_headline"))
                if sev in ("avoid", "contraindicated"):
                    severe_total += 1
                    if has:
                        severe_authored += 1
                elif sev in ("caution", "monitor", "info"):
                    nonsevere_total += 1
                    if has:
                        nonsevere_authored += 1
        pl = r.get("pregnancy_lactation")
        if pl:
            pl_total += 1
            if pl.get("alert_headline"):
                pl_authored += 1
    return {
        "rules_total": len(rules),
        "severe_authored": severe_authored,
        "severe_total": severe_total,
        "nonsevere_authored": nonsevere_authored,
        "nonsevere_total": nonsevere_total,
        "pl_authored": pl_authored,
        "pl_total": pl_total,
        "rules": rules,
    }


def _harmful_additives_summary(d):
    entries = d.get("harmful_additives") or []
    total = len(entries)
    fields = ("safety_summary", "safety_summary_one_liner")
    counts = {f: sum(1 for e in entries if e.get(f)) for f in fields}
    by_severity = Counter(e.get("severity_level") for e in entries)
    return {
        "total": total,
        "field_counts": counts,
        "severity_distribution": dict(by_severity),
        "entries": entries,
    }


def _synergy_summary(d):
    entries = d.get("synergy_clusters") or []
    total = len(entries)
    authored = sum(1 for e in entries if e.get("synergy_benefit_short"))
    return {
        "total": total,
        "authored": authored,
        "entries": entries,
    }


def _violations_summary(d):
    entries = d.get("manufacturer_violations") or []
    total = len(entries)
    authored = sum(1 for e in entries if e.get("brand_trust_summary"))
    by_severity = Counter(e.get("severity_level") for e in entries)
    return {
        "total": total,
        "authored": authored,
        "severity_distribution": dict(by_severity),
        "entries": entries,
    }


def _coverage_badge(authored: int, total: int) -> str:
    if total == 0:
        return "—"
    pct = 100.0 * authored / total
    if authored == total:
        return f"✅ {authored}/{total} (100%)"
    if pct >= 95:
        return f"🟡 {authored}/{total} ({pct:.1f}%)"
    return f"🔴 {authored}/{total} ({pct:.1f}%)"


def _file_mtime(p: Path) -> str:
    if not p.exists():
        return "missing"
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _flutter_sync_row(name: str, pipeline_schema, flutter_schema):
    if flutter_schema is None:
        return {"file": name, "pipeline": pipeline_schema, "flutter": "not an asset", "status": "—"}
    status = "✅ synced" if pipeline_schema == flutter_schema else "⚠️ stale"
    return {"file": name, "pipeline": pipeline_schema, "flutter": flutter_schema, "status": status}


def render_safety_copy(data):
    st.subheader("Clinical Copy Coverage (Path C)")
    st.caption(
        "Dr. Pham-authored safety / bonus copy across six data files. "
        "Every field here should be populated before shipping — this page exists "
        "to spot staleness the moment it happens."
    )

    # Load all six files
    br_path = DATA_DIR / "banned_recalled_ingredients.json"
    dep_path = DATA_DIR / "medication_depletions.json"
    ir_path = DATA_DIR / "ingredient_interaction_rules.json"
    ha_path = DATA_DIR / "harmful_additives.json"
    syn_path = DATA_DIR / "synergy_cluster.json"
    vio_path = DATA_DIR / "manufacturer_violations.json"

    br = _safe_read(br_path) or {}
    dep = _safe_read(dep_path) or {}
    ir = _safe_read(ir_path) or {}
    ha = _safe_read(ha_path) or {}
    syn = _safe_read(syn_path) or {}
    vio = _safe_read(vio_path) or {}

    br_s = _banned_recalled_summary(br)
    dep_s = _depletions_summary(dep)
    ir_s = _interaction_rules_summary(ir)
    ha_s = _harmful_additives_summary(ha)
    syn_s = _synergy_summary(syn)
    vio_s = _violations_summary(vio)

    # Top-level coverage table
    st.write("### Per-file coverage")
    rows = [
        {
            "file": "medication_depletions.json",
            "entries": dep_s["total"],
            "alert_headline": _coverage_badge(dep_s["field_counts"]["alert_headline"], dep_s["total"]),
            "alert_body": _coverage_badge(dep_s["field_counts"]["alert_body"], dep_s["total"]),
            "acknowledgement_note": _coverage_badge(dep_s["field_counts"]["acknowledgement_note"], dep_s["total"]),
            "monitoring_tip_short": _coverage_badge(dep_s["field_counts"]["monitoring_tip_short"], dep_s["total"]),
            "food_sources_short (optional)": f"{dep_s['field_counts']['food_sources_short']}/{dep_s['total']}",
            "adequacy_threshold_* (optional)": f"{dep_s['with_adequacy_threshold']}/{dep_s['total']}",
            "schema": (dep.get("_metadata") or {}).get("schema_version", "—"),
            "last_modified": _file_mtime(dep_path),
        },
        {
            "file": "banned_recalled_ingredients.json",
            "entries": br_s["total"],
            "ban_context": _coverage_badge(br_s["field_counts"]["ban_context"], br_s["total"]),
            "safety_warning": _coverage_badge(br_s["field_counts"]["safety_warning"], br_s["total"]),
            "safety_warning_one_liner": _coverage_badge(br_s["field_counts"]["safety_warning_one_liner"], br_s["total"]),
            "schema": (br.get("_metadata") or {}).get("schema_version", "—"),
            "last_modified": _file_mtime(br_path),
        },
        {
            "file": "ingredient_interaction_rules.json",
            "entries": ir_s["rules_total"],
            "severe_subrules": _coverage_badge(ir_s["severe_authored"], ir_s["severe_total"]),
            "nonsevere_subrules": _coverage_badge(ir_s["nonsevere_authored"], ir_s["nonsevere_total"]),
            "pregnancy_lactation_blocks": _coverage_badge(ir_s["pl_authored"], ir_s["pl_total"]),
            "schema": (ir.get("_metadata") or {}).get("schema_version", "—"),
            "last_modified": _file_mtime(ir_path),
        },
        {
            "file": "harmful_additives.json",
            "entries": ha_s["total"],
            "safety_summary": _coverage_badge(ha_s["field_counts"]["safety_summary"], ha_s["total"]),
            "safety_summary_one_liner": _coverage_badge(ha_s["field_counts"]["safety_summary_one_liner"], ha_s["total"]),
            "schema": (ha.get("_metadata") or {}).get("schema_version", "—"),
            "last_modified": _file_mtime(ha_path),
        },
        {
            "file": "synergy_cluster.json",
            "entries": syn_s["total"],
            "synergy_benefit_short": _coverage_badge(syn_s["authored"], syn_s["total"]),
            "schema": (syn.get("_metadata") or {}).get("schema_version", "—"),
            "last_modified": _file_mtime(syn_path),
        },
        {
            "file": "manufacturer_violations.json",
            "entries": vio_s["total"],
            "brand_trust_summary": _coverage_badge(vio_s["authored"], vio_s["total"]),
            "severity_distribution": ", ".join(f"{k}:{v}" for k, v in sorted(vio_s["severity_distribution"].items())),
            "schema": (vio.get("_metadata") or {}).get("schema_version", "—"),
            "last_modified": _file_mtime(vio_path),
        },
    ]
    # Table rendering with mixed-keys — use separate sections.
    for r in rows:
        cols = st.columns([3, 7])
        with cols[0]:
            st.markdown(f"**{r['file']}**")
            st.caption(f"schema {r['schema']} · modified {r['last_modified']}")
        with cols[1]:
            fields_md = " &nbsp; · &nbsp; ".join(
                f"{k}: {v}" for k, v in r.items()
                if k not in ("file", "entries", "schema", "last_modified")
            )
            st.markdown(f"{r['entries']} entries &nbsp; · &nbsp; {fields_md}")
        st.divider()

    # Classification summaries
    st.write("### Classification breakdowns")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**banned_recalled — `ban_context` distribution**")
        if br_s["ban_context_distribution"]:
            df = pd.DataFrame(
                [(k or "None", v) for k, v in sorted(br_s["ban_context_distribution"].items(), key=lambda x: -x[1])],
                columns=["ban_context", "count"],
            )
            st.dataframe(df, width="stretch", hide_index=True)
        st.write("**harmful_additives — `severity_level` distribution**")
        if ha_s["severity_distribution"]:
            df = pd.DataFrame(
                [(k or "None", v) for k, v in sorted(ha_s["severity_distribution"].items(), key=lambda x: -x[1])],
                columns=["severity_level", "count"],
            )
            st.dataframe(df, width="stretch", hide_index=True)
    with col2:
        st.write("**manufacturer_violations — `severity_level` distribution**")
        if vio_s["severity_distribution"]:
            df = pd.DataFrame(
                [(k or "None", v) for k, v in sorted(vio_s["severity_distribution"].items(), key=lambda x: -x[1])],
                columns=["severity_level", "count"],
            )
            st.dataframe(df, width="stretch", hide_index=True)

    # Flutter asset sync
    st.write("### Flutter asset sync status")
    st.caption(
        "Files shipped as Flutter reference_data assets must stay "
        "schema-synced with the pipeline source. Flutter falls back "
        "to asset data when offline."
    )

    def _flutter_schema(fname):
        p = FLUTTER_ASSETS / fname
        if not p.exists():
            return None
        d = _safe_read(p) or {}
        return (d.get("_metadata") or {}).get("schema_version")

    sync_rows = [
        _flutter_sync_row("banned_recalled_ingredients.json",
                          (br.get("_metadata") or {}).get("schema_version"),
                          _flutter_schema("banned_recalled_ingredients.json")),
        _flutter_sync_row("medication_depletions.json",
                          (dep.get("_metadata") or {}).get("schema_version"),
                          _flutter_schema("medication_depletions.json")),
        _flutter_sync_row("synergy_cluster.json",
                          (syn.get("_metadata") or {}).get("schema_version"),
                          _flutter_schema("synergy_cluster.json")),
        _flutter_sync_row("ingredient_interaction_rules.json",
                          (ir.get("_metadata") or {}).get("schema_version"),
                          _flutter_schema("ingredient_interaction_rules.json")),
        _flutter_sync_row("harmful_additives.json",
                          (ha.get("_metadata") or {}).get("schema_version"),
                          _flutter_schema("harmful_additives.json")),
        _flutter_sync_row("manufacturer_violations.json",
                          (vio.get("_metadata") or {}).get("schema_version"),
                          _flutter_schema("manufacturer_violations.json")),
    ]
    st.dataframe(pd.DataFrame(sync_rows), width="stretch", hide_index=True)

    # Sample spot-check
    st.write("### Spot-check a random entry")
    source_options = [
        "medication_depletions",
        "banned_recalled",
        "interaction_rules (severe)",
        "interaction_rules (pregnancy_lactation)",
        "harmful_additives",
        "synergy_cluster",
        "manufacturer_violations",
    ]
    picked = st.selectbox("Pick a source", source_options, key="safety_copy_picker")
    if st.button("🎲 Random entry", key="safety_copy_randomize"):
        st.session_state["safety_copy_seed"] = random.randint(0, 10**9)
    seed = st.session_state.get("safety_copy_seed", 0)
    rnd = random.Random(seed)

    if picked == "medication_depletions":
        es = [e for e in dep_s["entries"] if e.get("alert_headline")]
        if es:
            e = rnd.choice(es)
            st.markdown(f"**{e.get('medication_name') or e.get('id')}** → depletes {e.get('nutrient_name') or e.get('nutrient_canonical_id')}")
            st.markdown(f"- **alert_headline**: {e.get('alert_headline')}")
            st.markdown(f"- **alert_body**: {e.get('alert_body')}")
            st.markdown(f"- **acknowledgement_note**: {e.get('acknowledgement_note')}")
            st.markdown(f"- **monitoring_tip_short**: {e.get('monitoring_tip_short')}")
            if e.get("food_sources_short"):
                st.markdown(f"- **food_sources_short**: {e.get('food_sources_short')}")
            thresh_mcg = e.get("adequacy_threshold_mcg")
            thresh_mg = e.get("adequacy_threshold_mg")
            if thresh_mcg is not None:
                st.markdown(f"- **adequacy_threshold_mcg**: {thresh_mcg}")
            if thresh_mg is not None:
                st.markdown(f"- **adequacy_threshold_mg**: {thresh_mg}")
    elif picked == "banned_recalled":
        es = [e for e in br_s["entries"] if e.get("safety_warning")]
        if es:
            e = rnd.choice(es)
            st.markdown(f"**{e.get('standard_name') or e.get('id')}**  `ban_context={e.get('ban_context')}`")
            st.markdown(f"- **safety_warning**: {e.get('safety_warning')}")
            st.markdown(f"- **safety_warning_one_liner**: {e.get('safety_warning_one_liner')}")
    elif picked == "interaction_rules (severe)":
        flat = []
        for r in ir_s["rules"]:
            for key in ("condition_rules", "drug_class_rules"):
                for sub in r.get(key) or []:
                    if (sub.get("severity") or "").lower() in ("avoid", "contraindicated") and sub.get("alert_headline"):
                        flat.append((r.get("id"), key, sub))
        if flat:
            rid, kind, sub = rnd.choice(flat)
            target = sub.get("condition_id") or sub.get("drug_class_id")
            st.markdown(f"**{rid}** / {kind} / `{target}` / sev=`{sub.get('severity')}`")
            st.markdown(f"- **alert_headline**: {sub.get('alert_headline')}")
            st.markdown(f"- **alert_body**: {sub.get('alert_body')}")
            st.markdown(f"- **informational_note**: {sub.get('informational_note')}")
    elif picked == "interaction_rules (pregnancy_lactation)":
        flat = [(r.get("id"), r.get("pregnancy_lactation")) for r in ir_s["rules"]
                if r.get("pregnancy_lactation") and (r.get("pregnancy_lactation") or {}).get("alert_headline")]
        if flat:
            rid, pl = rnd.choice(flat)
            st.markdown(f"**{rid}** / pregnancy_lactation / pregnancy=`{pl.get('pregnancy_category')}` / lactation=`{pl.get('lactation_category')}`")
            st.markdown(f"- **alert_headline**: {pl.get('alert_headline')}")
            st.markdown(f"- **alert_body**: {pl.get('alert_body')}")
            st.markdown(f"- **informational_note**: {pl.get('informational_note')}")
    elif picked == "harmful_additives":
        es = [e for e in ha_s["entries"] if e.get("safety_summary")]
        if es:
            e = rnd.choice(es)
            st.markdown(f"**{e.get('standard_name') or e.get('id')}**  `severity_level={e.get('severity_level')}`  `category={e.get('category')}`")
            st.markdown(f"- **safety_summary**: {e.get('safety_summary')}")
            st.markdown(f"- **safety_summary_one_liner**: {e.get('safety_summary_one_liner')}")
    elif picked == "synergy_cluster":
        es = [e for e in syn_s["entries"] if e.get("synergy_benefit_short")]
        if es:
            e = rnd.choice(es)
            st.markdown(f"**{e.get('standard_name') or e.get('id')}**  tier=`{e.get('evidence_tier')}`")
            st.markdown(f"- **synergy_benefit_short**: {e.get('synergy_benefit_short')}")
            st.caption(f"*mechanism (for reference):* {(e.get('synergy_mechanism') or '')[:300]}")
    elif picked == "manufacturer_violations":
        es = [e for e in vio_s["entries"] if e.get("brand_trust_summary")]
        if es:
            e = rnd.choice(es)
            st.markdown(f"**{e.get('id')}**  `{e.get('manufacturer')}` / `{e.get('product') or '—'}`  `severity={e.get('severity_level')}`")
            st.markdown(f"- **brand_trust_summary**: {e.get('brand_trust_summary')}")
            st.caption(f"*reason (source):* {e.get('reason')}")

    # Staleness alerts
    st.write("### Staleness alerts")
    alerts = []
    if dep_s["field_counts"]["alert_headline"] < dep_s["total"]:
        alerts.append(f"medication_depletions: {dep_s['total'] - dep_s['field_counts']['alert_headline']} entries missing alert_headline")
    if br_s["field_counts"]["safety_warning"] < br_s["total"]:
        alerts.append(f"banned_recalled: {br_s['total'] - br_s['field_counts']['safety_warning']} entries missing safety_warning")
    if ir_s["severe_authored"] < ir_s["severe_total"]:
        alerts.append(f"interaction_rules: {ir_s['severe_total'] - ir_s['severe_authored']} severe sub-rules missing alert_headline")
    if ir_s["pl_authored"] < ir_s["pl_total"]:
        alerts.append(f"interaction_rules: {ir_s['pl_total'] - ir_s['pl_authored']} pregnancy_lactation blocks missing alert_headline")
    if ir_s["nonsevere_authored"] < ir_s["nonsevere_total"]:
        alerts.append(f"interaction_rules: {ir_s['nonsevere_total'] - ir_s['nonsevere_authored']} non-severe sub-rules missing alert_headline")
    if ha_s["field_counts"]["safety_summary"] < ha_s["total"]:
        alerts.append(f"harmful_additives: {ha_s['total'] - ha_s['field_counts']['safety_summary']} entries missing safety_summary")
    if syn_s["authored"] < syn_s["total"]:
        alerts.append(f"synergy_cluster: {syn_s['total'] - syn_s['authored']} entries missing synergy_benefit_short")
    if vio_s["authored"] < vio_s["total"]:
        alerts.append(f"manufacturer_violations: {vio_s['total'] - vio_s['authored']} entries missing brand_trust_summary")

    stale_sync = [r for r in sync_rows if r["status"] == "⚠️ stale"]
    for r in stale_sync:
        alerts.append(f"Flutter sync stale: {r['file']} (pipeline={r['pipeline']} vs flutter={r['flutter']})")

    if alerts:
        for a in alerts:
            st.warning(a)
    else:
        st.success("All six files fully authored. Flutter assets in sync.")

    # Validator command hint
    st.write("### Validator commands")
    st.code(
        "python3 scripts/validate_safety_copy.py --strict           # all files\n"
        "python3 scripts/validate_safety_copy.py --banned-recalled-only --strict\n"
        "python3 scripts/validate_safety_copy.py --interaction-rules-only --strict\n"
        "python3 scripts/validate_safety_copy.py --depletions-only --strict\n"
        "python3 scripts/validate_safety_copy.py --harmful-additives-only --strict\n"
        "python3 scripts/validate_safety_copy.py --synergy-only --strict\n"
        "python3 scripts/validate_safety_copy.py --violations-only --strict",
        language="bash",
    )
