"""
CrowdPatrol 2.0 — Unified Dark Control-Room SaaS Landing Page
Matches the exact Ink/Slate color scheme of the live monitoring dashboard
(#0b0d14 canvas, #07080d chrome, #11141c cards, #38bdf8 sky-blue accent),
with real crowd-management photography, plain-English copy, and zero HTML leaks.
"""

import base64
from pathlib import Path
import streamlit as st

try:
    from dashboard.design_system import COLOR_TOKENS, TYPOGRAPHY_TOKENS
except ImportError:
    from design_system import COLOR_TOKENS, TYPOGRAPHY_TOKENS


def _clean_html(raw: str) -> str:
    """Strip leading indentation so Streamlit Markdown never parses HTML as code blocks."""
    return "\n".join(line.strip() for line in raw.splitlines() if line.strip())


@st.cache_data(show_spinner=False)
def _load_asset_b64(filename: str) -> str:
    asset_path = Path(__file__).resolve().parent / "assets" / filename
    if not asset_path.exists():
        return ""
    return base64.b64encode(asset_path.read_bytes()).decode("ascii")


def _brand_logo_html(size: int = 34) -> str:
    b64 = _load_asset_b64("crowdpatrol_logo.png")
    if b64:
        return f'<img src="data:image/png;base64,{b64}" alt="CrowdPatrol Logo" style="width:{size}px; height:{size}px; object-fit:contain; display:block;" />'
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="3" y="3" width="58" height="58" rx="14" fill="#07080d" stroke="#38bdf8" stroke-width="3"/>'
        '<circle cx="32" cy="32" r="5" fill="#38bdf8"/>'
        '</svg>'
    )


def get_landing_page_css() -> str:
    c = COLOR_TOKENS
    t = TYPOGRAPHY_TOKENS
    font_disp = "'Sora', 'Space Grotesk', sans-serif"
    font_body = "'DM Sans', 'IBM Plex Sans', sans-serif"
    return _clean_html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Sora:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.stApp {{
    background-color: {c['bg_main']} !important;
    color: {c['text_primary']} !important;
    font-family: {font_body} !important;
}}
.block-container {{
    padding-top: 112px !important;
    padding-bottom: 2.5rem !important;
    max-width: 1240px !important;
}}
section[data-testid="stSidebar"] {{ display: none !important; }}
header[data-testid="stHeader"] {{ display: none !important; }}

/* Sticky Fixed Navbar (Taller for clear shield logo visibility) */
.cp-nav {{
    position: fixed;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    width: min(1208px, calc(100% - 32px));
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 76px;
    padding: 13px 24px;
    background-color: rgba(17, 20, 28, 0.94);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid {c['hairline_strong']};
    border-radius: 14px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.48);
}}
.cp-nav-brand {{
    display: flex;
    align-items: center;
    gap: 14px;
    text-decoration: none !important;
}}
.cp-brand-text {{ display: flex; flex-direction: column; line-height: 1.15; }}
.cp-brand-name {{ font-family: {font_disp}; color: {c['text_primary']}; font-size: 1.22rem; font-weight: 700; letter-spacing: -0.02em; }}
.cp-brand-sub {{ color: {c['accent']}; font-family: {t['font_mono']}; font-size: 0.68rem; letter-spacing: 0.08em; }}
.cp-nav-links {{ display: flex; align-items: center; gap: 28px; }}
.cp-nav-link {{
    color: {c['text_secondary']} !important;
    text-decoration: none !important;
    font-size: 0.9rem;
    font-weight: 500;
}}
.cp-nav-link:hover {{ color: {c['text_primary']} !important; }}
.cp-nav-actions {{ display: flex; align-items: center; gap: 10px; }}
.cp-nav-signin {{
    display: inline-flex; align-items: center; height: 38px; padding: 0 16px;
    background: {c['surface_raised']}; border: 1px solid {c['hairline_strong']};
    border-radius: 8px; color: {c['text_primary']} !important;
    font-size: 0.86rem; font-weight: 500; text-decoration: none !important;
}}
.cp-nav-signin:hover {{ background: #222734; }}
.cp-nav-cta {{
    display: inline-flex; align-items: center; height: 38px; padding: 0 18px;
    background: {c['accent']}; border-radius: 8px; color: {c['bg_deepest']} !important;
    font-size: 0.86rem; font-weight: 600; text-decoration: none !important;
}}
.cp-nav-cta:hover {{ background: {c['accent_hover']}; }}
@media (max-width: 860px) {{ .cp-nav-links {{ display: none; }} }}

/* Asymmetric Hero */
.cp-hero-grid {{
    display: grid;
    grid-template-columns: 1fr 1.12fr;
    gap: 36px;
    align-items: center;
    margin-bottom: 64px;
}}
@media (max-width: 920px) {{ .cp-hero-grid {{ grid-template-columns: 1fr; }} }}
.cp-hero-badge {{
    display: inline-flex; align-items: center; gap: 8px;
    padding: 5px 12px; border-radius: 999px;
    background: {c['accent_subtle']}; border: 1px solid {c['accent_border']};
    font-family: {t['font_mono']}; font-size: 0.75rem; color: {c['accent']};
    margin-bottom: 18px;
}}
.cp-hero-h1 {{
    font-family: {font_disp};
    font-size: clamp(2.05rem, 3.6vw, 3rem);
    line-height: 1.08;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: {c['text_primary']};
    margin: 0 0 16px 0;
}}
.cp-hero-p {{
    font-size: 1rem;
    line-height: 1.6;
    color: {c['text_secondary']};
    margin: 0 0 26px 0;
    max-width: 540px;
}}
.cp-hero-btns {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.cp-btn-pri {{
    display: inline-flex; align-items: center; height: 42px; padding: 0 20px;
    background: {c['accent']}; color: {c['bg_deepest']} !important;
    border-radius: 8px; font-size: 0.9rem; font-weight: 600; text-decoration: none !important;
}}
.cp-btn-pri:hover {{ background: {c['accent_hover']}; }}
.cp-btn-sec {{
    display: inline-flex; align-items: center; height: 42px; padding: 0 18px;
    background: {c['surface_raised']}; color: {c['text_primary']} !important;
    border: 1px solid {c['hairline_strong']}; border-radius: 8px;
    font-size: 0.9rem; font-weight: 500; text-decoration: none !important;
}}
.cp-btn-sec:hover {{ background: #222734; }}

/* Surveillance Hero Card with Real Image */
.cp-hero-card {{
    background: {c['surface_card']};
    border: 1px solid {c['hairline_strong']};
    border-radius: 14px;
    overflow: hidden;
}}
.cp-card-top {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px;
    background: {c['bg_deepest']};
    border-bottom: 1px solid {c['hairline']};
    font-family: {t['font_mono']}; font-size: 0.75rem; color: {c['text_secondary']};
}}
.cp-img-wrap {{
    position: relative;
    width: 100%;
    height: 270px;
    overflow: hidden;
    background: #07080d;
}}
.cp-img-wrap img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
    filter: brightness(0.88) contrast(1.06);
}}
.cp-img-fade {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(11,13,20,0.08) 45%, rgba(11,13,20,0.88) 100%);
}}
.cp-img-overlay-stats {{
    position: absolute; bottom: 12px; left: 12px; right: 12px;
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
}}
.cp-mini-kpi {{
    background: rgba(7, 8, 13, 0.85);
    border: 1px solid {c['hairline_strong']};
    border-radius: 8px;
    padding: 8px 10px;
}}
.cp-mini-k {{ font-size: 0.7rem; color: {c['text_muted']}; }}
.cp-mini-v {{ font-family: {t['font_mono']}; font-size: 0.92rem; font-weight: 600; color: {c['text_primary']}; }}

/* How It Works Split */
.cp-sec-head {{ text-align: center; max-width: 680px; margin: 0 auto 32px auto; }}
.cp-sec-title {{ font-family: {font_disp}; font-size: 1.75rem; font-weight: 700; color: {c['text_primary']}; letter-spacing: -0.025em; margin: 0 0 8px 0; }}
.cp-sec-sub {{ font-size: 0.96rem; line-height: 1.6; color: {c['text_secondary']}; margin: 0; }}

/* Floating Story Behind the Logo Cloud */
@keyframes cp-cloud-drift {{
    0%, 100% {{ transform: translate(0px, 0px); }}
    25% {{ transform: translate(-8px, -6px); }}
    50% {{ transform: translate(4px, -11px); }}
    75% {{ transform: translate(8px, -4px); }}
}}
@keyframes cp-cloud-expand {{
    0% {{ opacity: 0.7; transform: scale(0.88) translateY(8px); }}
    100% {{ opacity: 1; transform: scale(1) translateY(0); }}
}}
details.cp-story-cloud {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 9998;
}}
details.cp-story-cloud:not([open]) {{
    animation: cp-cloud-drift 7s ease-in-out infinite;
}}
details.cp-story-cloud summary.cp-cloud-trigger {{
    list-style: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: rgba(17, 20, 28, 0.95);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid {c['accent_border']};
    border-radius: 999px;
    color: {c['text_primary']};
    font-size: 0.84rem;
    font-weight: 500;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
    user-select: none;
}}
details.cp-story-cloud summary.cp-cloud-trigger::-webkit-details-marker {{
    display: none;
}}
details.cp-story-cloud summary.cp-cloud-trigger:hover {{
    border-color: {c['accent']};
    background: {c['surface_raised']};
}}
details.cp-story-cloud[open] {{
    width: min(500px, calc(100vw - 32px));
    background: {c['surface_card']};
    border: 1px solid {c['hairline_strong']};
    border-radius: 18px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.72);
    overflow: hidden;
    animation: cp-cloud-expand 220ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
}}
details.cp-story-cloud[open] summary.cp-cloud-trigger {{
    width: 100%;
    justify-content: space-between;
    border-radius: 0;
    border: none;
    border-bottom: 1px solid {c['hairline']};
    background: {c['bg_deepest']};
    padding: 12px 18px;
}}
.cp-cloud-body {{
    padding: 20px;
    display: flex;
    gap: 18px;
    align-items: center;
}}
@media (max-width: 560px) {{
    .cp-cloud-body {{ flex-direction: column; text-align: center; }}
}}
.cp-cloud-logo {{
    flex-shrink: 0;
    width: 148px;
    height: 148px;
    background: {c['bg_deepest']};
    border: 1px solid {c['hairline_strong']};
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px;
}}
.cp-cloud-h {{
    font-family: {font_disp};
    font-size: 1.08rem;
    font-weight: 600;
    color: {c['text_primary']};
    margin: 0 0 8px 0;
}}
.cp-cloud-p {{
    font-size: 0.84rem;
    line-height: 1.58;
    color: {c['text_secondary']};
    margin: 0 0 8px 0;
}}
.cp-cloud-p:last-child {{ margin-bottom: 0; }}

.cp-how-grid {{
    display: grid;
    grid-template-columns: 1.05fr 1fr;
    gap: 28px;
    align-items: center;
    margin-bottom: 64px;
    background: {c['surface_card']};
    border: 1px solid {c['hairline']};
    border-radius: 14px;
    padding: 20px;
}}
@media (max-width: 900px) {{ .cp-how-grid {{ grid-template-columns: 1fr; }} }}
.cp-how-img {{
    width: 100%; height: 290px; object-fit: cover; border-radius: 10px;
    border: 1px solid {c['hairline']}; display: block;
}}
.cp-step {{
    padding: 12px 14px;
    background: {c['bg_deepest']};
    border: 1px solid {c['hairline']};
    border-radius: 10px;
    margin-bottom: 10px;
}}
.cp-step:last-child {{ margin-bottom: 0; }}
.cp-step-num {{ font-family: {t['font_mono']}; font-size: 0.74rem; color: {c['accent']}; margin-bottom: 4px; }}
.cp-step-h {{ font-family: {font_disp}; font-size: 0.98rem; font-weight: 600; color: {c['text_primary']}; margin-bottom: 4px; }}
.cp-step-p {{ font-family: {font_body}; font-size: 0.86rem; line-height: 1.55; color: {c['text_secondary']}; margin: 0; }}

/* 6-Card Feature Grid */
.cp-grid-6 {{
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 64px;
}}
@media (max-width: 940px) {{ .cp-grid-6 {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 620px) {{ .cp-grid-6 {{ grid-template-columns: 1fr; }} }}
.cp-feat-card {{
    background: {c['surface_card']}; border: 1px solid {c['hairline']};
    border-radius: 12px; padding: 20px;
}}
.cp-icon-tile {{
    width: 34px; height: 34px; border-radius: 8px;
    display: inline-flex; align-items: center; justify-content: center;
    margin-bottom: 12px; border: 1px solid {c['hairline']};
}}
.cp-feat-h {{ font-family: {font_disp}; font-size: 0.98rem; font-weight: 600; color: {c['text_primary']}; margin: 0 0 6px 0; }}
.cp-feat-p {{ font-family: {font_body}; font-size: 0.86rem; line-height: 1.55; color: {c['text_secondary']}; margin: 0; }}

/* Benchmarks */
.cp-bench-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 56px;
}}
@media (max-width: 900px) {{ .cp-bench-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.cp-bench-card {{
    background: {c['surface_card']}; border: 1px solid {c['hairline']};
    border-radius: 12px; padding: 18px 20px;
}}
.cp-bench-num {{ font-family: {t['font_mono']}; font-size: 1.65rem; font-weight: 600; color: {c['text_primary']}; margin-bottom: 4px; }}
.cp-bench-lbl {{ font-size: 0.85rem; color: {c['text_secondary']}; margin-bottom: 2px; }}
.cp-bench-meta {{ font-family: {t['font_mono']}; font-size: 0.72rem; color: {c['text_muted']}; }}

/* Footer */
.cp-footer {{
    background: {c['bg_deepest']};
    border-top: 1px solid {c['hairline']};
    border-radius: 12px;
    padding: 36px 28px 22px 28px;
    margin-top: 48px;
}}
.cp-footer-grid {{
    display: grid; grid-template-columns: 1.8fr 1fr 1fr 1fr; gap: 28px; margin-bottom: 24px;
}}
@media (max-width: 820px) {{ .cp-footer-grid {{ grid-template-columns: 1fr 1fr; }} }}
.cp-footer-h {{ font-size: 0.85rem; font-weight: 600; color: {c['text_primary']}; margin-bottom: 10px; }}
.cp-footer-a {{ display: block; font-size: 0.82rem; color: {c['text_muted']} !important; text-decoration: none !important; margin-bottom: 6px; }}
.cp-footer-a:hover {{ color: {c['text_primary']} !important; }}
.cp-footer-bot {{
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;
    padding-top: 16px; border-top: 1px solid {c['hairline']}; font-size: 0.78rem; color: {c['text_muted']};
}}
</style>
""")


def render_saas_landing_page():
    """Renders the unified dark control-room SaaS landing page."""
    st.markdown(get_landing_page_css(), unsafe_allow_html=True)

    hero_b64 = _load_asset_b64("crowd_hero.jpg")
    ops_b64 = _load_asset_b64("crowd_ops.jpg")
    hero_src = f"data:image/jpeg;base64,{hero_b64}" if hero_b64 else ""
    ops_src = f"data:image/jpeg;base64,{ops_b64}" if ops_b64 else ""

    st.markdown(_clean_html(f"""
<nav class="cp-nav">
<a class="cp-nav-brand" href="#">
{_brand_logo_html(50)}
<div class="cp-brand-text">
<span class="cp-brand-name">CrowdPatrol</span>
<span class="cp-brand-sub">CROWD SAFETY</span>
</div>
</a>
<div class="cp-nav-links">
<a class="cp-nav-link" href="#how-it-works">How It Works</a>
<a class="cp-nav-link" href="#features">Features</a>
<a class="cp-nav-link" href="#benchmarks">Benchmarks</a>
</div>
<div class="cp-nav-actions">
<a class="cp-nav-signin" href="#console-access">Sign In</a>
<a class="cp-nav-cta" href="#console-access">Launch Console →</a>
</div>
</nav>
"""), unsafe_allow_html=True)

    hero_img_tag = f'<img src="{hero_src}" alt="Elevated crowd surveillance view" />' if hero_src else ""
    st.markdown(_clean_html(f"""
<section class="cp-hero-grid">
<div>
<div class="cp-hero-badge">
<span class="cp-status-dot cp-status-dot--live"></span>
<span>Live Crowd Safety Monitoring</span>
</div>
<h1 class="cp-hero-h1">Monitor Crowd Density and Spot Safety Risks in Real Time</h1>
<p class="cp-hero-p">
CrowdPatrol watches your cameras or recorded video, counts people automatically, detects sudden crowd surges, and alerts your team before congestion turns dangerous.
</p>
<div class="cp-hero-btns">
<a class="cp-btn-pri" href="#console-access">Sign In / Launch Console</a>
<a class="cp-btn-sec" href="#how-it-works">See How It Works</a>
</div>
</div>
<div class="cp-hero-card">
<div class="cp-card-top">
<span><span class="cp-status-dot cp-status-dot--live"></span>DIRECT-01 · Main Concourse</span>
<span>1280×720 · 43.4 FPS</span>
</div>
<div class="cp-img-wrap">
{hero_img_tag}
<div class="cp-img-fade"></div>
<div class="cp-img-overlay-stats">
<div class="cp-mini-kpi"><div class="cp-mini-k">People</div><div class="cp-mini-v">27</div></div>
<div class="cp-mini-kpi"><div class="cp-mini-k">Max Density</div><div class="cp-mini-v">6 / cell</div></div>
<div class="cp-mini-kpi"><div class="cp-mini-k">Anomaly</div><div class="cp-mini-v">0.42</div></div>
<div class="cp-mini-kpi"><div class="cp-mini-k">Risk</div><div class="cp-mini-v" style="color:#4cc38a;">38.4 · Low</div></div>
</div>
</div>
</div>
</section>
"""), unsafe_allow_html=True)

    ops_img_tag = f'<img class="cp-how-img" src="{ops_src}" alt="Crowd monitoring operations desk" />' if ops_src else ""
    st.markdown(_clean_html(f"""
<div id="how-it-works" class="cp-sec-head">
<h2 class="cp-sec-title">How CrowdPatrol Works</h2>
<p class="cp-sec-sub">Three simple steps from camera feed to early warning, designed for venue and security operators.</p>
</div>
<div class="cp-how-grid">
<div>{ops_img_tag}</div>
<div>
<div class="cp-step">
<div class="cp-step-num">Step 01 · Connect Video</div>
<div class="cp-step-h">Use any webcam, IP camera, or recorded clip</div>
<p class="cp-step-p">Monitor a single stream in detail or watch up to four feeds together in the 2×2 CCTV Command Center.</p>
</div>
<div class="cp-step">
<div class="cp-step-num">Step 02 · Analyze Crowd</div>
<div class="cp-step-h">Count people, map density, and track movement</div>
<p class="cp-step-p">YOLOv8n + DeepSORT track individuals while 4×4 grid heatmaps and optical flow measure crowding and sudden speed surges.</p>
</div>
<div class="cp-step">
<div class="cp-step-num">Step 03 · Act Early</div>
<div class="cp-step-h">Acknowledge live alerts and notify your team</div>
<p class="cp-step-p">High and Critical risks trigger browser audio alarms, sidebar Ack/Resolve controls, and verified email notifications.</p>
</div>
</div>
</div>
"""), unsafe_allow_html=True)

    st.markdown(_clean_html("""
<div id="features" class="cp-sec-head">
<h2 class="cp-sec-title">Key Capabilities</h2>
<p class="cp-sec-sub">Everything needed to run crowd safety monitoring on standard hardware.</p>
</div>
<div class="cp-grid-6">
<div class="cp-feat-card">
<div class="cp-icon-tile" style="background:rgba(56,189,248,0.12);">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
</div>
<div class="cp-feat-h">People & Head Counting</div>
<p class="cp-feat-p">Fine-tuned on CrowdHuman (0.5421 mAP@50), with an optional Head Mode for dense overhead crowds.</p>
</div>
<div class="cp-feat-card">
<div class="cp-icon-tile" style="background:rgba(76,195,138,0.12);">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4cc38a" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
</div>
<div class="cp-feat-h">Smooth High-FPS Playback</div>
<p class="cp-feat-p">Frame-skipping with Kalman prediction reaches 43.43 FPS on CPU without stuttering video playback.</p>
</div>
<div class="cp-feat-card">
<div class="cp-icon-tile" style="background:rgba(245,158,11,0.12);">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
</div>
<div class="cp-feat-h">Crowd Surge Detection</div>
<p class="cp-feat-p">Optical flow detects sudden acceleration and directional turbulence while filtering out camera pan.</p>
</div>
<div class="cp-feat-card">
<div class="cp-icon-tile" style="background:rgba(56,189,248,0.12);">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/></svg>
</div>
<div class="cp-feat-h">4×4 Spatial Density Map</div>
<p class="cp-feat-p">Highlights overcrowded zones on a thermal overlay and tracks peak density per grid cell.</p>
</div>
<div class="cp-feat-card">
<div class="cp-icon-tile" style="background:rgba(229,72,77,0.12);">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e5484d" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
</div>
<div class="cp-feat-h">Anti-Flicker Risk Scoring</div>
<p class="cp-feat-p">EMA smoothing (α=0.25) and a 5-point hysteresis deadband prevent false alarm flickering.</p>
</div>
<div class="cp-feat-card">
<div class="cp-icon-tile" style="background:rgba(76,195,138,0.12);">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4cc38a" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
</div>
<div class="cp-feat-h">Audio Alarms & Email Alerts</div>
<p class="cp-feat-p">Plays distinct High beep and Critical siren alarms and emails verified operator accounts automatically.</p>
</div>
</div>
"""), unsafe_allow_html=True)

    st.markdown(_clean_html("""
<div id="benchmarks" class="cp-sec-head">
<h2 class="cp-sec-title">Measured Benchmark Results</h2>
<p class="cp-sec-sub">Tested on Intel Core i7-13700H (CPU mode, 300 steady-state frames from youtube_crowd_test.mp4).</p>
</div>
<div class="cp-bench-grid">
<div class="cp-bench-card"><div class="cp-bench-num">43.43 FPS</div><div class="cp-bench-lbl">Pipeline throughput</div><div class="cp-bench-meta">detect_interval=3 · CPU</div></div>
<div class="cp-bench-card"><div class="cp-bench-num">7.32x</div><div class="cp-bench-lbl">Frame-skipping speedup</div><div class="cp-bench-meta">43.43 FPS vs 5.93 FPS</div></div>
<div class="cp-bench-card"><div class="cp-bench-num">17.20x</div><div class="cp-bench-lbl">Optical flow speedup</div><div class="cp-bench-meta">320×180 vs 1280×720</div></div>
<div class="cp-bench-card"><div class="cp-bench-num">0.5421</div><div class="cp-bench-lbl">CrowdHuman mAP@50</div><div class="cp-bench-meta">+13.06% over baseline</div></div>
</div>
<div id="console-access"></div>
"""), unsafe_allow_html=True)

    story_b64 = _load_asset_b64("story_logo.png") or _load_asset_b64("crowdpatrol_logo.png")
    story_img = (
        f'<img src="data:image/png;base64,{story_b64}" alt="CrowdPatrol Story Crest" style="width:128px; height:128px; object-fit:contain; display:block;" />'
        if story_b64 else _brand_logo_html(128)
    )
    story_thumb = (
        f'<img src="data:image/png;base64,{story_b64}" alt="" style="width:22px; height:22px; object-fit:contain; display:block;" />'
        if story_b64 else ""
    )
    st.markdown(_clean_html(f"""
<details class="cp-story-cloud">
<summary class="cp-cloud-trigger">
<span style="display:inline-flex; align-items:center; gap:8px;">
{story_thumb}
<span>Story behind the logo</span>
</span>
<span style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#38bdf8;">Click to toggle</span>
</summary>
<div class="cp-cloud-body">
<div class="cp-cloud-logo">{story_img}</div>
<div>
<h4 class="cp-cloud-h">Inspired by Prevention After the RCB Stampede</h4>
<p class="cp-cloud-p">
We were deeply moved by the tragic RCB victory parade stampede in Bengaluru, where preventable overcrowding and delayed situational awareness led to devastating loss of life. That incident inspired us to build CrowdPatrol as an early-warning tool to help prevent future crowd disasters.
</p>
<p class="cp-cloud-p">
In our crest, the <strong>Guardian Lion</strong> stands for vigilant protection, the <strong>Radar Sweep</strong> represents continuous real-time scanning, and the <strong>Crowd</strong> represents the people we aim to safeguard.
</p>
</div>
</div>
</details>
"""), unsafe_allow_html=True)


def render_landing_footer():
    st.markdown(_clean_html(f"""
<footer class="cp-footer">
<div class="cp-footer-grid">
<div>
<div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
{_brand_logo_html(28)}
<span style="font-size:0.98rem; font-weight:600; color:#eef0f5;">CrowdPatrol</span>
</div>
<p style="font-size:0.82rem; line-height:1.55; color:#7a8296; margin:0 0 10px 0; max-width:300px;">
Autonomous crowd density, optical flow anomaly detection, and multi-camera safety monitoring platform.
</p>
<div style="font-family:'JetBrains Mono',monospace; font-size:0.74rem; color:#38bdf8;">YOLOv8n · DeepSORT · Farneback · SQLite</div>
</div>
<div>
<div class="cp-footer-h">Product</div>
<a class="cp-footer-a" href="#how-it-works">How It Works</a>
<a class="cp-footer-a" href="#features">Features</a>
<a class="cp-footer-a" href="#benchmarks">Benchmarks</a>
</div>
<div>
<div class="cp-footer-h">Application</div>
<a class="cp-footer-a" href="#console-access">Direct Stream</a>
<a class="cp-footer-a" href="#console-access">2×2 CCTV Grid</a>
<a class="cp-footer-a" href="#console-access">Remote Telemetry</a>
</div>
<div>
<div class="cp-footer-h">Account</div>
<a class="cp-footer-a" href="#console-access">Sign In</a>
<a class="cp-footer-a" href="#console-access">Create Account</a>
<a class="cp-footer-a" href="#console-access">Email Verification</a>
</div>
</div>
<div class="cp-footer-bot">
<span>© 2026 CrowdPatrol. Real-time crowd safety and operational intelligence.</span>
<span>YOLOv8n + DeepSORT + Farneback Optical Flow</span>
</div>
</footer>
"""), unsafe_allow_html=True)
