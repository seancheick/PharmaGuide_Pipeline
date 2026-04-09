import streamlit as st

def status_badge(label: str, status_type: str = "info"):
    """Renders a styled status badge."""
    colors = {
        "pass": "#22c55e",
        "safe": "#22c55e",
        "caution": "#eab308",
        "poor": "#f97316",
        "unsafe": "#ef4444",
        "blocked": "#991b1b",
        "not_scored": "#6b7280",
        "info": "#3b82f6",
        "warning": "#eab308",
        "error": "#ef4444"
    }
    
    color = colors.get(status_type.lower(), colors["info"])
    
    badge_html = f"""
    <span style="
        background-color: {color};
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
        display: inline-block;
    ">
        {label}
    </span>
    """
    st.markdown(badge_html, unsafe_allow_html=True)
