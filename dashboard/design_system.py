"""
CrowdPatrol 2.0 — Control-Room Design System (Unsloped)
Ink neutral ramp, tabular telemetry typography, 4px spacing scale,
quiet 8% hairlines, and one cool sky-blue accent (#38bdf8).
"""

COLOR_TOKENS = {
    # Ink Neutral Ramp (Dark)
    "bg_deepest": "#07080d",        # Sidebar & deepest chrome
    "bg_main": "#0b0d14",           # Page canvas
    "surface_card": "#11141c",      # Elevated card / panel
    "surface_raised": "#1a1e28",    # Active row, input, secondary button
    "hairline": "rgba(238, 240, 245, 0.08)",
    "hairline_strong": "rgba(238, 240, 245, 0.14)",

    # Text Roles (3 roles)
    "text_primary": "#eef0f5",
    "text_secondary": "#a3a9b8",
    "text_muted": "#7a8296",

    # Single Accent (Sky Blue — >4.5:1 contrast with #07080d dark text)
    "accent": "#38bdf8",
    "accent_hover": "#7dd3fc",
    "accent_subtle": "rgba(56, 189, 248, 0.12)",
    "accent_border": "rgba(56, 189, 248, 0.35)",

    # Toned Semantic Status Colors
    "status_low": "#4cc38a",
    "status_medium": "#f59e0b",
    "status_high": "#e5484d",
    "status_critical": "#dc2626",
}

TYPOGRAPHY_TOKENS = {
    "font_display": "'Space Grotesk', 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    "font_sans": "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "font_mono": "'JetBrains Mono', 'Fira Code', ui-monospace, monospace",
}


def get_design_system_css() -> str:
    """Returns the unslopped Ink control-room CSS for Streamlit."""
    c = COLOR_TOKENS
    t = TYPOGRAPHY_TOKENS

    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {{
        --cp-bg-deepest: {c['bg_deepest']};
        --cp-bg-main: {c['bg_main']};
        --cp-surface-card: {c['surface_card']};
        --cp-surface-raised: {c['surface_raised']};
        --cp-hairline: {c['hairline']};
        --cp-hairline-strong: {c['hairline_strong']};
        --cp-text-primary: {c['text_primary']};
        --cp-text-secondary: {c['text_secondary']};
        --cp-text-muted: {c['text_muted']};
        --cp-accent: {c['accent']};
        --cp-accent-hover: {c['accent_hover']};
        --cp-accent-subtle: {c['accent_subtle']};
        --cp-status-low: {c['status_low']};
        --cp-status-medium: {c['status_medium']};
        --cp-status-high: {c['status_high']};
        --cp-status-critical: {c['status_critical']};
        --cp-ease: cubic-bezier(0.22, 1, 0.36, 1);
    }}

    html {{
        scroll-behavior: smooth;
    }}

    .stApp {{
        background-color: {c['bg_main']};
        color: {c['text_primary']};
        font-family: {t['font_sans']};
    }}

    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1440px !important;
    }}

    /* Typography Hierarchy: corporate display + clean IBM Plex Sans body */
    h1, h2, h3, h4, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
        font-family: {t['font_display']} !important;
        color: {c['text_primary']} !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }}

    h1 {{ font-size: 1.75rem !important; line-height: 1.15 !important; }}
    h2 {{ font-size: 1.25rem !important; line-height: 1.25 !important; }}
    h3 {{ font-size: 1.05rem !important; line-height: 1.3 !important; }}

    p, span, label, div {{
        font-family: {t['font_sans']};
    }}

    /* Sidebar Chrome */
    section[data-testid="stSidebar"] {{
        background-color: {c['bg_deepest']} !important;
        border-right: 1px solid {c['hairline']} !important;
    }}

    section[data-testid="stSidebar"] .block-container {{
        padding-top: 1.25rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}

    /* Buttons: 8px radius, crisp surface step, single easing curve */
    .stButton > button,
    .stFormSubmitButton > button {{
        border-radius: 8px !important;
        font-family: {t['font_sans']} !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        min-height: 36px !important;
        transition: background-color 150ms var(--cp-ease), border-color 150ms var(--cp-ease), transform 120ms var(--cp-ease) !important;
        border: 1px solid {c['hairline_strong']} !important;
        background-color: {c['surface_raised']} !important;
        color: {c['text_primary']} !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
    }}

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {{
        background-color: #222734 !important;
        border-color: rgba(238, 240, 245, 0.24) !important;
    }}

    .stButton > button:active,
    .stFormSubmitButton > button:active {{
        transform: scale(0.98) !important;
    }}

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-primaryFormSubmit"] {{
        background-color: {c['accent']} !important;
        color: {c['bg_deepest']} !important;
        border: 1px solid {c['accent']} !important;
        font-weight: 600 !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28) !important;
    }}

    .stButton > button[kind="primary"] p,
    .stFormSubmitButton > button[kind="primary"] p,
    button[data-testid="stBaseButton-primary"] p,
    button[data-testid="stBaseButton-primaryFormSubmit"] p {{
        color: {c['bg_deepest']} !important;
        font-weight: 600 !important;
    }}

    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
        background-color: {c['accent_hover']} !important;
        border-color: {c['accent_hover']} !important;
    }}

    /* Inputs & Selectboxes */
    .stTextInput input,
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stTextArea textarea {{
        background-color: {c['surface_raised']} !important;
        border: 1px solid {c['hairline']} !important;
        border-radius: 8px !important;
        color: {c['text_primary']} !important;
        font-size: 0.875rem !important;
    }}

    .stTextInput input:focus,
    .stNumberInput input:focus,
    .stTextArea textarea:focus {{
        border-color: {c['accent']} !important;
        box-shadow: 0 0 0 1px {c['accent']} !important;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        border-bottom: 1px solid {c['hairline']};
        background: transparent;
    }}

    .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        border: none !important;
        color: {c['text_secondary']} !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        padding: 8px 14px !important;
    }}

    .stTabs [aria-selected="true"] {{
        color: {c['text_primary']} !important;
        border-bottom: 2px solid {c['accent']} !important;
    }}

    .stTabs div[data-baseweb="tab-highlight"] {{
        background-color: {c['accent']} !important;
    }}

    /* Metric Cards */
    div[data-testid="stMetric"] {{
        background-color: {c['surface_card']};
        border: 1px solid {c['hairline']};
        border-radius: 12px;
        padding: 14px 16px;
    }}

    div[data-testid="stMetric"] label {{
        color: {c['text_muted']} !important;
        font-size: 0.75rem !important;
        font-weight: 500 !important;
    }}

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {c['text_primary']} !important;
        font-family: {t['font_mono']} !important;
        font-variant-numeric: tabular-nums !important;
        font-size: 1.5rem !important;
        font-weight: 500 !important;
    }}

    /* Expanders */
    details[data-testid="stExpander"] {{
        background-color: {c['surface_card']} !important;
        border: 1px solid {c['hairline']} !important;
        border-radius: 12px !important;
    }}

    /* Signature Status Dot */
    .cp-status-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 999px;
        vertical-align: middle;
        margin-right: 6px;
    }}
    .cp-status-dot--live {{
        background-color: {c['status_low']};
    }}
    .cp-status-dot--standby {{
        background-color: {c['text_muted']};
    }}
    .cp-status-dot--alert {{
        background-color: {c['status_high']};
    }}

    /* Monospace tabular readout utility */
    .cp-mono {{
        font-family: {t['font_mono']};
        font-variant-numeric: tabular-nums;
    }}

    /* Quiet surface card */
    .cp-card {{
        background-color: {c['surface_card']};
        border: 1px solid {c['hairline']};
        border-radius: 12px;
        padding: 20px;
    }}

    /* Clean Risk Banner (no neon glow, semantic left accent bar) */
    .cp-emergency-banner {{
        background-color: #1c1215;
        border: 1px solid rgba(229, 72, 77, 0.35);
        border-left: 4px solid {c['status_high']};
        color: {c['text_primary']};
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 16px;
    }}
</style>
"""
