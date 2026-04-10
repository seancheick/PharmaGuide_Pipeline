import streamlit as st
import pandas as pd
import sqlite3
import json
from pathlib import Path
from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.product_header import product_header
from scripts.dashboard.components.score_breakdown import score_breakdown
from scripts.dashboard.components.score_trace import score_trace


def _safe_columns(spec):
    try:
        columns = st.columns(spec)
        expected = spec if isinstance(spec, int) else len(spec)
        if isinstance(columns, (list, tuple)) and len(columns) >= expected:
            return list(columns[:expected])
    except Exception:
        pass
    fallback_count = spec if isinstance(spec, int) else len(spec)
    return [st for _ in range(fallback_count)]


def _safe_tabs(labels):
    try:
        tabs = st.tabs(labels)
        if isinstance(tabs, (list, tuple)) and len(tabs) >= len(labels):
            return list(tabs[: len(labels)])
    except Exception:
        pass
    return [st for _ in labels]


def render_inspector(data):
    """
    Renders the Product Inspector view with search and results table.
    """
    st.subheader("Product Search")
    
    # 1. Search Input
    # Pre-fill from session state if it was set via deep link
    initial_query = st.session_state.get("selected_dsld_id", "")
    
    search_query = st.text_input(
        "Search by DSLD ID, Name, Brand, or UPC", 
        value=initial_query,
        placeholder="Enter search term...",
        key="inspector_search_input"
    )
    search_query = search_query.strip() if isinstance(search_query, str) else ""
    
    if not search_query:
        st.info("Enter a search term above to begin.")
        return

    # 2. Search Logic
    results = perform_search(data.db_conn, search_query)
    
    if results.empty:
        st.warning(f"No results found for '{search_query}'")
        return

    # 3. Results Table
    st.write(f"Found {len(results)} matches:")
    
    # Color coding for verdicts
    verdict_colors = {
        "SAFE": "#22c55e",
        "CAUTION": "#eab308",
        "POOR": "#f97316",
        "UNSAFE": "#ef4444",
        "BLOCKED": "#991b1b",
        "NOT_SCORED": "#6b7280"
    }
    
    data_table(results, color_columns={"verdict": verdict_colors}, max_rows=100)
    
    # Selection logic: 
    # If we have an exact DSLD ID match, we should probably auto-select it.
    default_index = 0
    if st.session_state.get("selected_dsld_id") in results["dsld_id"].values:
        default_index = results[results["dsld_id"] == st.session_state["selected_dsld_id"]].index[0]
        # In streamlit selectbox, index is 0-based relative to options list
        options = results["dsld_id"].tolist()
        try:
            default_index = options.index(st.session_state["selected_dsld_id"])
        except ValueError:
            default_index = 0

    selected_id = st.selectbox(
        "Select a product to view details:",
        options=results["dsld_id"].tolist(),
        index=default_index,
        format_func=lambda x: f"{x} - {results[results['dsld_id']==x]['product_name'].values[0]}"
    )
    
    if selected_id:
        st.session_state.selected_dsld_id = selected_id
        st.query_params["dsld_id"] = selected_id
        
        # --- DRILL-DOWN PANEL ---
        st.divider()
        render_drill_down(selected_id, data)

def render_drill_down(dsld_id, data):
    """
    Renders the detailed product drill-down panel.
    """
    # 1. Load Data
    # Fetch from products_core
    cursor = data.db_conn.execute("SELECT * FROM products_core WHERE dsld_id = ?", (dsld_id,))
    product_row = cursor.fetchone()
    
    if not product_row:
        st.error(f"Product {dsld_id} not found in database.")
        return

    # Load detail blob
    blob_path = data.detail_blobs_dir / f"{dsld_id}.json" if data.detail_blobs_dir else None
    blob = None
    if blob_path and blob_path.exists():
        try:
            blob = json.loads(blob_path.read_text())
        except Exception as e:
            st.warning(f"Failed to load detail blob: {e}")
    else:
        st.info("Detail blob not found - bonuses/penalties and full ingredient list may be limited.")

    # 2. Header Block
    product_header(
        name=product_row["product_name"],
        brand=product_row["brand_name"],
        verdict=product_row["verdict"],
        grade=product_row["grade"],
        score=product_row["score_100_equivalent"],
        percentile=product_row["percentile_label"] if "percentile_label" in product_row.keys() else None
    )

    # 3. Score Pillar Bars
    st.write("### 📊 Performance Pillars")
    score_breakdown(
        ingredient=product_row["score_ingredient_quality"],
        safety=product_row["score_safety_purity"],
        evidence=product_row["score_evidence_research"],
        brand=product_row["score_brand_trust"],
        height=250
    )

    # 4. Pros & Cons (Bonuses & Penalties)
    st.write("### ✅ Pros & ❌ Cons")
    col_pros, col_cons = _safe_columns(2)
    
    if blob:
        bonuses = blob.get("score_bonuses", [])
        penalties = blob.get("score_penalties", [])
        
        with col_pros:
            st.write("**What Helped**")
            if not bonuses:
                st.caption("No bonuses applied")
            for b in bonuses:
                st.success(f"🟢 {b.get('label', 'Bonus')}: +{b.get('score', 0)} pts")
                
        with col_cons:
            st.write("**What Hurt**")
            if not penalties:
                st.caption("No penalties applied")
            for p in penalties:
                # Severity-based coloring or simple error block
                st.error(f"🔴 {p.get('label', 'Penalty')}: {p.get('score', 0)} pts")
    else:
        st.caption("Pros/Cons unavailable without detail blob.")

    # 5. Ingredients
    st.write("### 🧪 Ingredients")
    tab_active, tab_inactive = _safe_tabs(["Active Ingredients", "Inactive Ingredients"])
    
    if blob:
        with tab_active:
            active_df = pd.DataFrame(blob.get("ingredients", []))
            if not active_df.empty:
                # Column selection and styling
                cols = ["name", "bio_score", "form", "dosage", "flags"]
                available_cols = [c for c in cols if c in active_df.columns]
                st.dataframe(active_df[available_cols], use_container_width=True)
            else:
                st.caption("No active ingredients listed.")
                
        with tab_inactive:
            inactive_df = pd.DataFrame(blob.get("inactive_ingredients", []))
            if not inactive_df.empty:
                st.dataframe(inactive_df, use_container_width=True)
            else:
                st.caption("No inactive ingredients listed.")
    else:
        st.caption("Ingredient details unavailable without detail blob.")

    # 6. Warnings
    st.write("### ⚠️ Warnings")
    if blob and blob.get("warnings"):
        for w in blob["warnings"]:
            severity = w.get("severity", "info").lower()
            title = w.get("title", w.get("type", "Warning"))
            detail = w.get("detail", "")
            if severity in ("high", "critical", "avoid", "contraindicated"):
                st.error(f"**{title}**: {detail}")
            elif severity in ("medium", "moderate", "caution"):
                st.warning(f"**{title}**: {detail}")
            else:
                st.info(f"**{title}**: {detail}")
    else:
        st.caption("No warnings for this product.")

    # 7. Score Trace
    with st.expander("🧭 Audit Evidence"):
        if blob:
            audit = blob.get("audit", {})
            col_left, col_right = _safe_columns(2)
            with col_left:
                st.write("**Supplement Type Audit**")
                if audit.get("supplement_type"):
                    st.dataframe(pd.DataFrame([audit["supplement_type"]]), use_container_width=True, hide_index=True)
                st.write("**Non-GMO Audit**")
                if blob.get("non_gmo_audit"):
                    st.dataframe(pd.DataFrame([blob["non_gmo_audit"]]), use_container_width=True, hide_index=True)
            with col_right:
                st.write("**Omega-3 Audit**")
                if blob.get("omega3_audit"):
                    st.dataframe(pd.DataFrame([blob["omega3_audit"]]), use_container_width=True, hide_index=True)
                st.write("**Proprietary Blend Audit**")
                if blob.get("proprietary_blend_audit"):
                    st.dataframe(pd.DataFrame([blob["proprietary_blend_audit"]]), use_container_width=True, hide_index=True)
        else:
            st.caption("Audit evidence unavailable without detail blob.")

    with st.expander("🔍 Detailed Score Trace"):
        if blob:
            score_trace(
                section_breakdown=blob.get("section_breakdown", {}),
                bonuses=blob.get("score_bonuses", []),
                penalties=blob.get("score_penalties", [])
            )
        else:
            st.caption("Trace unavailable without detail blob.")

    # 8. Source Paths & Raw JSON
    with st.expander("🛠️ Debug Information"):
        st.write("**Source Paths**")
        st.code(f"Database: {data.db_path}")
        if blob_path:
            st.code(f"Detail Blob: {blob_path}")
            
        st.write("**Raw JSON (Blob)**")
        st.json(blob if blob else {"error": "No blob found"})
        
        st.write("**Raw Row (SQLite)**")
        st.json(dict(product_row))

def perform_search(db_conn, query):
    """
    Performs progressive search in SQLite:
    1. Numeric check (ID or UPC)
    2. Full-Text Search (FTS5)
    3. LIKE fallback
    """
    if db_conn is None:
        return pd.DataFrame()

    query = query.strip()
    
    # 1. Numeric check for DSLD ID or UPC
    if query.isdigit():
        if len(query) < 10:
            sql = "SELECT dsld_id, product_name, brand_name, score_100_equivalent as score, grade, verdict FROM products_core WHERE dsld_id = ?"
            params = [query]
        else:
            sql = "SELECT dsld_id, product_name, brand_name, score_100_equivalent as score, grade, verdict FROM products_core WHERE upc_sku = ?"
            params = [query]
        
        df = pd.read_sql_query(sql, db_conn, params=params)
        if not df.empty:
            return df

    # 2. Full-Text Search (FTS5)
    try:
        fts_sql = """
            SELECT dsld_id, product_name, brand_name, score_100_equivalent as score, grade, verdict 
            FROM products_core 
            WHERE dsld_id IN (SELECT dsld_id FROM products_fts WHERE products_fts MATCH ?)
            LIMIT 50
        """
        # Escaping query for FTS
        clean_query = query.replace('"', '""')
        df = pd.read_sql_query(fts_sql, db_conn, params=[clean_query])
        if not df.empty:
            return df
    except sqlite3.Error:
        pass # Fallback to LIKE if FTS fails

    # 3. Text search (LIKE)
    sql = """
        SELECT dsld_id, product_name, brand_name, score_100_equivalent as score, grade, verdict 
        FROM products_core 
        WHERE product_name LIKE ? OR brand_name LIKE ? 
        LIMIT 100
    """
    params = [f"%{query}%", f"%{query}%"]

    try:
        df = pd.read_sql_query(sql, db_conn, params=params)
        return df
    except Exception as e:
        st.error(f"Search error: {e}")
        return pd.DataFrame()
