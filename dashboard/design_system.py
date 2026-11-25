"""
CrowdPatrol 2.0 — Reusable Design System & Token Controller
Defines the enterprise visual system: typography, nocturnal surfaces,
selective glassmorphism, electric illumination, and responsive UI components.
"""

from typing import Dict, Any, List, Optional
import streamlit as st


# ==============================================================================
# 1. DESIGN TOKENS
# ==============================================================================

COLOR_TOKENS = {
    # Canvas & Surfaces
    "bg_main": "#050816",           # Deep Midnight Navy
    "bg_secondary": "#080F20",      # Dark Obsidian Slate
    "surface_elevated": "#101B30",  # Elevated Container / Card Surface
    "surface_glass": "rgba(16, 27, 48, 0.75)",
    "surface_glass_subtle": "rgba(8, 15, 32, 0.65)",

    # Primary Brand Accents
    "blue_primary": "#2563EB",      # Command Cobalt Blue
    "blue_hover": "#1D4ED8",
    "blue_glow": "rgba(37, 99, 235, 0.35)",
    "cyan_electric": "#00D9FF",     # Telemetry Electric Cyan
    "cyan_glow": "rgba(0, 217, 255, 0.30)",
    "violet_accent": "#8B5CF6",     # Predictive AI Violet
    "violet_glow": "rgba(139, 92, 246, 0.25)",

    # Semantic Status Indicators
    "status_low": "#10B981",        # Emerald Normal / Safe
    "status_medium": "#F59E0B",     # Amber Caution
    "status_high": "#EF4444",       # Crimson Danger
    "status_critical": "#DC2626",   # Emergency Flashing Red

    # High-Contrast Typography
    "text_primary": "#EAF4FF",      # Crisp Off-White
    "text_secondary": "#94A3B8",    # Muted Slate
    "text_tertiary": "#64748B",     # Dim Meta Gray
    "text_accent": "#00D9FF",

    # Borders & Dividers
    "border_subtle": "rgba(59, 130, 246, 0.18)",
    "border_active": "rgba(0, 217, 255, 0.45)",
    "border_glow": "rgba(0, 217, 255, 0.65)",
    "border_critical": "rgba(239, 68, 68, 0.55)",
}

TYPOGRAPHY_TOKENS = {
    "font_sans": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "font_mono": "'JetBrains Mono', 'Fira Code', monospace",
}


# ==============================================================================
# 2. GLOBAL CSS FRAMEWORK GENERATOR
# ==============================================================================

def get_design_system_css() -> str:
    """
    Returns the comprehensive CROWDPatrol 2.0 CSS stylesheet.
    Injects custom properties, reset, typography, selective glassmorphism,
    neon illumination, card styles, and accessibility rules.
    """
    c = COLOR_TOKENS
    t = TYPOGRAPHY_TOKENS

    return f"""
<style>
    /* -------------------------------------------------------------------------
       FONTS & GLOBAL PROPERTIES
       ------------------------------------------------------------------------- */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {{
        --cp-bg-main: {c['bg_main']};
        --cp-bg-sec: {c['bg_secondary']};
        --cp-surface-elevated: {c['surface_elevated']};
        --cp-surface-glass: {c['surface_glass']};
        --cp-blue: {c['blue_primary']};
        --cp-cyan: {c['cyan_electric']};
        --cp-violet: {c['violet_accent']};
        --cp-text-pri: {c['text_primary']};
        --cp-text-sec: {c['text_secondary']};
        --cp-border-subtle: {c['border_subtle']};
        --cp-border-active: {c['border_active']};
        --cp-font-sans: {t['font_sans']};
        --cp-font-mono: {t['font_mono']};
    }}

    html {{
        scroll-behavior: smooth;
    }}

    /* Target the main Streamlit application canvas */
    .stApp {{
        background-color: {c['bg_main']};
        background-image: 
            radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.15) 0%, transparent 65%),
            radial-gradient(circle at 10% 35%, rgba(0, 217, 255, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 90% 70%, rgba(139, 92, 246, 0.10) 0%, transparent 55%);
        background-attachment: fixed;
        color: {c['text_primary']};
        font-family: var(--cp-font-sans);
    }}

    /* Ensure container width is spacious and centered */
    .block-container {{
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1260px !important;
    }}

    /* -------------------------------------------------------------------------
       SELECTIVE GLASSMORPHISM & SURFACE ELEVATION
       ------------------------------------------------------------------------- */
    .cp-glass-surface {{
        background: {c['surface_glass']};
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid {c['border_subtle']};
        border-radius: 14px;
        box-shadow: 0 8px 32px -4px rgba(0, 0, 0, 0.55);
    }}

    .cp-surface-solid {{
        background: {c['surface_elevated']};
        border: 1px solid {c['border_subtle']};
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.40);
    }}

    /* -------------------------------------------------------------------------
       TOP NAVIGATION BAR
       ------------------------------------------------------------------------- */
    .cp-navbar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 28px;
        background: rgba(8, 15, 32, 0.85);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 217, 255, 0.22);
        border-radius: 16px;
        margin-bottom: 32px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.60);
    }}

    .cp-brand {{
        display: flex;
        align-items: center;
        gap: 14px;
        text-decoration: none;
    }}

    .cp-brand-icon {{
        width: 42px;
        height: 42px;
        background: linear-gradient(135deg, {c['blue_primary']} 0%, {c['cyan_electric']} 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        box-shadow: 0 0 18px {c['cyan_glow']};
    }}

    .cp-brand-title {{
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #FFFFFF;
        line-height: 1.1;
    }}

    .cp-brand-title span {{
        color: {c['cyan_electric']};
    }}

    .cp-brand-tagline {{
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        color: {c['text_secondary']};
        text-transform: uppercase;
    }}

    .cp-nav-links {{
        display: flex;
        align-items: center;
        gap: 24px;
    }}

    .cp-nav-link {{
        color: {c['text_secondary']};
        text-decoration: none;
        font-size: 0.92rem;
        font-weight: 600;
        transition: color 0.2s ease;
    }}

    .cp-nav-link:hover {{
        color: {c['cyan_electric']};
    }}

    /* -------------------------------------------------------------------------
       HERO & CINEMATIC DISPLAY TYPOGRAPHY
       ------------------------------------------------------------------------- */
    .cp-hero-container {{
        text-align: center;
        padding: 40px 10px 30px 10px;
    }}

    .cp-hero-eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 16px;
        background: rgba(37, 99, 235, 0.15);
        border: 1px solid rgba(0, 217, 255, 0.35);
        border-radius: 9999px;
        font-size: 0.80rem;
        font-weight: 700;
        color: {c['cyan_electric']};
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 22px;
        box-shadow: 0 0 20px rgba(0, 217, 255, 0.18);
    }}

    .cp-hero-headline {{
        font-size: 3.6rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.08;
        color: #FFFFFF;
        margin: 0 auto 20px auto;
        max-width: 900px;
        text-shadow: 0 2px 24px rgba(0, 0, 0, 0.8);
    }}

    .cp-hero-headline .gradient-text {{
        background: linear-gradient(135deg, #FFFFFF 20%, {c['cyan_electric']} 70%, {c['violet_accent']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}

    .cp-hero-desc {{
        font-size: 1.25rem;
        color: {c['text_secondary']};
        max-width: 680px;
        margin: 0 auto 34px auto;
        line-height: 1.6;
    }}

    /* -------------------------------------------------------------------------
       SURVEILLANCE VISUALIZATION CENTERPIECE
       ------------------------------------------------------------------------- */
    .cp-surveillance-stage {{
        position: relative;
        background: {c['surface_elevated']};
        border: 1px solid {c['border_active']};
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 12px 48px -8px rgba(0, 0, 0, 0.7), 0 0 32px rgba(0, 217, 255, 0.15);
        overflow: hidden;
        margin-bottom: 48px;
    }}

    .cp-viz-grid {{
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 20px;
        align-items: center;
    }}

    .cp-mock-viewport {{
        position: relative;
        background: #060B18;
        border-radius: 12px;
        border: 1px solid rgba(59, 130, 246, 0.3);
        height: 380px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 16px;
    }}

    /* Visual AI Overlay Elements */
    .cp-bbox {{
        position: absolute;
        border: 2px solid {c['cyan_electric']};
        background: rgba(0, 217, 255, 0.08);
        border-radius: 4px;
        box-shadow: 0 0 12px rgba(0, 217, 255, 0.4);
    }}

    .cp-bbox-label {{
        position: absolute;
        top: -20px;
        left: -2px;
        background: {c['cyan_electric']};
        color: #050816;
        font-family: var(--cp-font-mono);
        font-size: 0.68rem;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 3px 3px 0 0;
        letter-spacing: 0.04em;
        white-space: nowrap;
    }}

    .cp-bbox-vector {{
        position: absolute;
        height: 2px;
        background: linear-gradient(90deg, {c['cyan_electric']}, transparent);
        transform-origin: left center;
    }}

    .cp-heatmap-scanline {{
        position: absolute;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, {c['cyan_electric']}, transparent);
        opacity: 0.7;
        animation: cpScanline 4s linear infinite;
    }}

    @keyframes cpScanline {{
        0% {{ top: 0%; }}
        100% {{ top: 100%; }}
    }}

    /* Side HUD Telemetry Cards */
    .cp-hud-panel {{
        display: flex;
        flex-direction: column;
        gap: 14px;
    }}

    .cp-hud-card {{
        background: rgba(8, 15, 32, 0.7);
        border: 1px solid rgba(59, 130, 246, 0.22);
        border-radius: 10px;
        padding: 16px;
    }}

    .cp-hud-card-label {{
        font-size: 0.75rem;
        font-weight: 700;
        color: {c['cyan_electric']};
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .cp-hud-card-val {{
        font-size: 1.45rem;
        font-weight: 800;
        font-family: var(--cp-font-mono);
        color: #FFFFFF;
    }}

    .cp-hud-card-sub {{
        font-size: 0.80rem;
        color: {c['text_secondary']};
        margin-top: 4px;
    }}

    /* -------------------------------------------------------------------------
       STORYTELLING CHAPTERS (THE 5-CHAPTER EXPERIENCE)
       ------------------------------------------------------------------------- */
    .cp-chapter-card {{
        background: {c['surface_elevated']};
        border: 1px solid {c['border_subtle']};
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    }}

    .cp-chapter-card:hover {{
        border-color: {c['border_active']};
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 217, 255, 0.12);
    }}

    .cp-chapter-num {{
        font-family: var(--cp-font-mono);
        font-size: 0.78rem;
        font-weight: 700;
        color: {c['cyan_electric']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 8px;
    }}

    .cp-chapter-title {{
        font-size: 1.65rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 12px;
    }}

    .cp-chapter-body {{
        font-size: 1.0rem;
        color: {c['text_secondary']};
        line-height: 1.65;
    }}

    /* -------------------------------------------------------------------------
       FEATURE & TECHNOLOGY CARDS
       ------------------------------------------------------------------------- */
    .cp-feature-card {{
        background: rgba(16, 27, 48, 0.6);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 14px;
        padding: 22px;
        height: 100%;
        transition: all 0.2s ease;
    }}

    .cp-feature-card:hover {{
        border-color: {c['cyan_electric']};
        background: rgba(16, 27, 48, 0.85);
        box-shadow: 0 6px 24px rgba(0, 217, 255, 0.15);
    }}

    .cp-feature-icon {{
        width: 44px;
        height: 44px;
        border-radius: 10px;
        background: rgba(37, 99, 235, 0.2);
        border: 1px solid rgba(0, 217, 255, 0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        margin-bottom: 14px;
    }}

    .cp-pipeline-step {{
        background: rgba(16, 27, 48, 0.7);
        border: 1px solid {c['border_subtle']};
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        font-family: var(--cp-font-mono);
        font-size: 0.85rem;
        color: {c['text_primary']};
    }}

    /* -------------------------------------------------------------------------
       ACCESSIBILITY & REDUCED-MOTION SUPPORT
       ------------------------------------------------------------------------- */
    @media (prefers-reduced-motion: reduce) {{
        *, ::before, ::after {{
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
            scroll-behavior: auto !important;
        }}
        .cp-heatmap-scanline {{
            display: none !important;
        }}
    }}

    /* -------------------------------------------------------------------------
       RESPONSIVE BREAKPOINTS
       ------------------------------------------------------------------------- */
    @media (max-width: 900px) {{
        .cp-viz-grid {{
            grid-template-columns: 1fr;
        }}
        .cp-hero-headline {{
            font-size: 2.5rem;
        }}
        .cp-navbar {{
            flex-direction: column;
            gap: 16px;
            padding: 16px;
        }}
    }}
</style>
"""


# ==============================================================================
# 3. STREAMLIT UI COMPONENT RENDERERS
# ==============================================================================

def inject_design_system():
    """Injects the global CROWDPatrol 2.0 design tokens and styles into the active Streamlit app."""
    st.markdown(get_design_system_css(), unsafe_allow_html=True)


def render_navbar(on_launch_dashboard=None, active_page: str = "landing"):
    """Renders the top navigation bar."""
    st.markdown(f"""
    <div class="cp-navbar">
        <a href="#hero" class="cp-brand">
            <div class="cp-brand-icon">🛡️</div>
            <div>
                <div class="cp-brand-title">CROWD<span>PATROL</span></div>
                <div class="cp-brand-tagline">AI Crowd Safety & Risk Intelligence</div>
            </div>
        </a>
        <div class="cp-nav-links">
            <a href="#hero" class="cp-nav-link">Home</a>
            <a href="#storytelling" class="cp-nav-link">Story</a>
            <a href="#features" class="cp-nav-link">Features</a>
            <a href="#pipeline" class="cp-nav-link">Pipeline</a>
            <a href="#technology" class="cp-nav-link">Technology</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_surveillance_centerpiece():
    """
    Renders the sophisticated AI surveillance visualization centerpiece:
    public crowd viewport, dynamic bounding boxes, tracking vectors, and side HUD telemetry.
    Explicitly labeled as an illustrative simulation / demo.
    """
    c = COLOR_TOKENS
    st.markdown(f"""
    <div class="cp-surveillance-stage">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#10B981; box-shadow:0 0 10px #10B981;"></span>
                <span style="font-family:var(--cp-font-mono); font-size:0.85rem; font-weight:700; color:#EAF4FF;">SIMULATED DEMO SCENARIO &bull; SECTOR ALPHA-01</span>
            </div>
            <div style="font-family:var(--cp-font-mono); font-size:0.80rem; color:{c['cyan_electric']};">
                YOLOv8 + DeepSORT &bull; 640&times;640 &bull; ILLUSTRATIVE AI TELEMETRY
            </div>
        </div>

        <div class="cp-viz-grid">
            <!-- Left: Simulated Real-Time Computer Vision Viewport -->
            <div class="cp-mock-viewport" style="position:relative;">
                <div class="cp-heatmap-scanline"></div>
                
                <!-- Watermark Badge: Not connected to physical hardware -->
                <div style="position:absolute; top:8px; left:50%; transform:translateX(-50%); background:rgba(8,15,32,0.85); border:1px solid rgba(0,217,255,0.4); padding:3px 12px; border-radius:4px; font-family:var(--cp-font-mono); font-size:0.68rem; color:#00D9FF; letter-spacing:0.06em; z-index:5; white-space:nowrap;">
                    [SIMULATED CAMERA FEED &bull; NOT CONNECTED TO PHYSICAL HARDWARE]
                </div>

                <!-- Camera HUD Overlay -->
                <div style="display:flex; justify-content:space-between; z-index:2; margin-top:24px;">
                    <div style="background:rgba(5,8,22,0.85); padding:4px 10px; border-radius:4px; font-family:var(--cp-font-mono); font-size:0.75rem; border:1px solid rgba(0,217,255,0.3);">
                        CAM-01 [SIMULATED FEED] &bull; TARGET: 30+ FPS &bull; RES: 1280&times;720
                    </div>
                    <div style="background:rgba(239,68,68,0.25); color:#EF4444; border:1px solid #EF4444; padding:4px 10px; border-radius:4px; font-family:var(--cp-font-mono); font-size:0.75rem; font-weight:700;">
                        ● SIMULATED SURGE SCENARIO
                    </div>
                </div>

                <!-- Bounding Box 1: Dense Concourse Center -->
                <div class="cp-bbox" style="top:75px; left:60px; width:140px; height:190px;">
                    <div class="cp-bbox-label">ID: 042 &bull; PERSON 96% (SIM)</div>
                    <div class="cp-bbox-vector" style="bottom:10px; left:50%; width:45px; transform:rotate(-25deg);"></div>
                </div>

                <!-- Bounding Box 2: Bottleneck Cluster -->
                <div class="cp-bbox" style="top:110px; left:230px; width:130px; height:170px; border-color:#F59E0B; box-shadow:0 0 12px rgba(245,158,11,0.4);">
                    <div class="cp-bbox-label" style="background:#F59E0B;">ID: 088 &bull; PERSON 92% (CLUSTER)</div>
                </div>

                <!-- Bounding Box 3: Fast Velocity Anomaly -->
                <div class="cp-bbox" style="top:90px; left:390px; width:110px; height:160px; border-color:#EF4444; box-shadow:0 0 14px rgba(239,68,68,0.5);">
                    <div class="cp-bbox-label" style="background:#EF4444; color:#FFF;">ID: 104 &bull; ANOMALY (SIMULATED)</div>
                    <div class="cp-bbox-vector" style="bottom:10px; left:50%; width:60px; transform:rotate(15deg); background:linear-gradient(90deg, #EF4444, transparent);"></div>
                </div>

                <!-- Bottom Viewport Footer -->
                <div style="display:flex; justify-content:space-between; align-items:flex-end; z-index:2;">
                    <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:#94A3B8; background:rgba(5,8,22,0.85); padding:4px 8px; border-radius:4px;">
                        FARNEBACK OPTICAL FLOW: VECTOR MAGNITUDE 1.4 m/s (SIMULATED DYNAMICS)
                    </div>
                    <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:{c['cyan_electric']}; background:rgba(5,8,22,0.85); padding:4px 8px; border-radius:4px;">
                        TRACKS: 34 ACTIVE (ILLUSTRATIVE MODEL)
                    </div>
                </div>
            </div>

            <!-- Right: Real-Time HUD Telemetry Cards (Illustrative) -->
            <div class="cp-hud-panel">
                <div style="font-family:var(--cp-font-mono); font-size:0.70rem; color:#F59E0B; text-transform:uppercase; letter-spacing:0.06em; font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                    <span>✦</span> ILLUSTRATIVE TELEMETRY (DEMO)
                </div>

                <div class="cp-hud-card">
                    <div class="cp-hud-card-label">👥 Person Count</div>
                    <div class="cp-hud-card-val">34 <span style="font-size:0.9rem; color:#10B981;">&uarr; +6 influx</span></div>
                    <div class="cp-hud-card-sub">Illustrative active tracks in demo sector</div>
                </div>

                <div class="cp-hud-card">
                    <div class="cp-hud-card-label">🔥 Peak Cell Density</div>
                    <div class="cp-hud-card-val" style="color:#F59E0B;">7 <span style="font-size:0.9rem; font-weight:600; color:#94A3B8;">persons/cell</span></div>
                    <div class="cp-hud-card-sub">Cell B2 &bull; 4&times;4 spatial grid (Demo)</div>
                </div>

                <div class="cp-hud-card">
                    <div class="cp-hud-card-label">⚠️ Risk Assessment</div>
                    <div class="cp-hud-card-val" style="color:#EF4444;">HIGH (78.4)</div>
                    <div class="cp-hud-card-sub">Illustrative: Density (65%) + Flow (35%)</div>
                </div>

                <div class="cp-hud-card">
                    <div class="cp-hud-card-label">⚡ Target AI Throughput</div>
                    <div class="cp-hud-card-val" style="color:{c['cyan_electric']};">30+ FPS</div>
                    <div class="cp-hud-card-sub">Benchmark target on tested GPU hardware</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
