"""
CrowdPatrol 2.0 — Cinematic Landing Page & Narrative Storytelling Module
Establishes the enterprise-grade visual identity for CROWDPatrol:
- Nocturnal canvas with electric cyan/cobalt illumination and selective glassmorphism.
- 5-Chapter Storytelling: The Problem, The Intelligence, The Awareness, The Response, The Platform.
- Visual AI Surveillance Centerpiece with simulated bounding boxes, vectors, and live HUD telemetry.
- 8 Core Feature Capabilities and 6-Stage Technology Pipeline.
- Seamless navigation and deep-linking into the primary Streamlit Monitoring Dashboard.
"""

from typing import Optional, Callable
import streamlit as st

try:
    from dashboard.design_system import (
        COLOR_TOKENS,
        TYPOGRAPHY_TOKENS,
        get_design_system_css,
        render_surveillance_centerpiece,
    )
except ImportError:
    from design_system import (
        COLOR_TOKENS,
        TYPOGRAPHY_TOKENS,
        get_design_system_css,
        render_surveillance_centerpiece,
    )


def get_landing_page_css() -> str:
    """
    Returns the comprehensive CSS stylesheet for the CROWDPatrol 2.0 landing page.
    Includes both the modern design system and backward-compatible style tokens.
    """
    c = COLOR_TOKENS
    t = TYPOGRAPHY_TOKENS

    base_css = get_design_system_css()

    extra_css = f"""
<style>
    /* -------------------------------------------------------------------------
       ADDITIONAL LANDING PAGE EXTENSIONS & STORYTELLING LAYOUT
       ------------------------------------------------------------------------- */
    /* Target container constraints */
    .block-container {{
        padding-top: 1.25rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1280px !important;
    }}

    /* Backward compatibility color tokens and anchor offsets */
    :root {{
        --cp-navy-dark: #070B14;
        --cp-navy-surface: #0A0F1D;
        --cp-navy-card: #0B132B;
        --cp-blue-accent: #1D4ED8;
        --cp-cyan-accent: #00D2FF;
        --cp-cyan-bright: #38BDF8;
    }}

    .cp-anchor {{
        position: relative;
        top: -60px;
        visibility: hidden;
    }}

    /* Top Navigation Component */
    .cp-navbar-container {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 26px;
        background: rgba(8, 15, 32, 0.85);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 217, 255, 0.22);
        border-radius: 16px;
        margin-bottom: 32px;
        box-shadow: 0 10px 32px -4px rgba(0, 0, 0, 0.55), 0 0 20px rgba(0, 217, 255, 0.08);
    }}

    .cp-brand {{
        display: flex;
        align-items: center;
        gap: 12px;
        text-decoration: none;
    }}

    .cp-brand-logo {{
        width: 42px;
        height: 42px;
        background: linear-gradient(135deg, #2563EB 0%, #00D9FF 100%);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        box-shadow: 0 0 20px rgba(0, 217, 255, 0.5);
    }}

    .cp-brand-text {{
        font-family: var(--cp-font-sans);
        font-size: 1.45rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #FFFFFF;
        line-height: 1.1;
    }}

    .cp-brand-text span {{
        color: #00D9FF;
    }}

    .cp-brand-sub {{
        font-family: var(--cp-font-mono);
        font-size: 0.72rem;
        font-weight: 600;
        color: #94A3B8;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }}

    .cp-nav-menu {{
        display: flex;
        align-items: center;
        gap: 20px;
        list-style: none;
        margin: 0;
        padding: 0;
    }}

    .cp-nav-link {{
        color: #94A3B8;
        font-size: 0.90rem;
        font-weight: 600;
        text-decoration: none;
        transition: all 0.2s ease;
        padding: 6px 12px;
        border-radius: 8px;
    }}

    .cp-nav-link:hover {{
        color: #00D9FF;
        background: rgba(0, 217, 255, 0.10);
    }}

    /* Hero Section Component */
    .cp-hero-container {{
        text-align: center;
        padding: 40px 16px 28px 16px;
        margin-bottom: 24px;
    }}

    .cp-badge-pill {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 18px;
        background: rgba(37, 99, 235, 0.18);
        border: 1px solid rgba(0, 217, 255, 0.45);
        border-radius: 9999px;
        font-family: var(--cp-font-mono);
        font-size: 0.80rem;
        font-weight: 700;
        color: #00D9FF;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 24px;
        box-shadow: 0 0 24px rgba(0, 217, 255, 0.20);
    }}

    .cp-status-dot {{
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 10px #10B981;
        animation: cp-pulse 2s infinite ease-in-out;
    }}

    .cp-hero-headline {{
        font-family: var(--cp-font-sans);
        font-size: 3.4rem;
        font-weight: 800;
        line-height: 1.15;
        letter-spacing: -0.03em;
        margin-bottom: 18px;
        color: #EAF4FF;
    }}

    .cp-hero-headline .gradient-text {{
        background: linear-gradient(135deg, #00D9FF 0%, #3B82F6 50%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}

    .cp-hero-subheading {{
        font-size: 1.35rem;
        font-weight: 600;
        color: #38BDF8;
        margin-bottom: 14px;
        letter-spacing: -0.01em;
    }}

    .cp-hero-description {{
        font-size: 1.12rem;
        line-height: 1.7;
        color: #94A3B8;
        max-width: 840px;
        margin: 0 auto 32px auto;
    }}

    /* Metrics Strip */
    .cp-metrics-strip {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        max-width: 980px;
        margin: 0 auto 36px auto;
    }}

    .cp-metric-box {{
        background: rgba(16, 27, 48, 0.70);
        border: 1px solid rgba(59, 130, 246, 0.22);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }}

    .cp-metric-box:hover {{
        transform: translateY(-2px);
        border-color: rgba(0, 217, 255, 0.45);
    }}

    .cp-metric-value {{
        font-family: var(--cp-font-mono);
        font-size: 1.65rem;
        font-weight: 800;
        color: #00D9FF;
        margin-bottom: 4px;
    }}

    .cp-metric-label {{
        font-size: 0.82rem;
        font-weight: 600;
        color: #EAF4FF;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    .cp-metric-sub {{
        font-size: 0.72rem;
        color: #64748B;
        margin-top: 2px;
    }}

    /* -------------------------------------------------------------------------
       STORYTELLING SECTIONS
       ------------------------------------------------------------------------- */
    .cp-story-chapter {{
        background: linear-gradient(180deg, rgba(16, 27, 48, 0.65) 0%, rgba(8, 15, 32, 0.85) 100%);
        border: 1px solid rgba(59, 130, 246, 0.20);
        border-radius: 20px;
        padding: 38px 40px;
        margin-bottom: 36px;
        backdrop-filter: blur(14px);
        box-shadow: 0 12px 36px -6px rgba(0, 0, 0, 0.45);
        position: relative;
        overflow: hidden;
    }}

    .cp-story-chapter::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(180deg, #00D9FF, #2563EB);
    }}

    .cp-chapter-badge {{
        display: inline-block;
        font-family: var(--cp-font-mono);
        font-size: 0.75rem;
        font-weight: 700;
        color: #00D9FF;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }}

    .cp-chapter-title {{
        font-family: var(--cp-font-sans);
        font-size: 2.0rem;
        font-weight: 800;
        color: #EAF4FF;
        line-height: 1.25;
        margin-bottom: 16px;
        letter-spacing: -0.02em;
    }}

    .cp-chapter-lead {{
        font-size: 1.08rem;
        line-height: 1.75;
        color: #CBD5E1;
        margin-bottom: 24px;
    }}

    .cp-story-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-top: 20px;
    }}

    .cp-story-card {{
        background: rgba(8, 15, 32, 0.80);
        border: 1px solid rgba(59, 130, 246, 0.18);
        border-radius: 12px;
        padding: 20px;
    }}

    .cp-story-card-title {{
        font-size: 1.0rem;
        font-weight: 700;
        color: #EAF4FF;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .cp-story-card-desc {{
        font-size: 0.88rem;
        line-height: 1.6;
        color: #94A3B8;
    }}

    /* -------------------------------------------------------------------------
       FEATURES GRID
       ------------------------------------------------------------------------- */
    .cp-section-header {{
        text-align: center;
        margin-bottom: 36px;
    }}

    .cp-section-tag {{
        font-family: var(--cp-font-mono);
        font-size: 0.78rem;
        font-weight: 700;
        color: #00D9FF;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 8px;
    }}

    .cp-section-title {{
        font-family: var(--cp-font-sans);
        font-size: 2.4rem;
        font-weight: 800;
        color: #EAF4FF;
        letter-spacing: -0.02em;
        margin-bottom: 12px;
    }}

    .cp-section-subtitle {{
        font-size: 1.05rem;
        color: #94A3B8;
        max-width: 720px;
        margin: 0 auto;
        line-height: 1.6;
    }}

    .cp-features-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 20px;
        margin-bottom: 48px;
    }}

    .cp-feature-card {{
        background: rgba(16, 27, 48, 0.75);
        border: 1px solid rgba(59, 130, 246, 0.20);
        border-radius: 14px;
        padding: 24px;
        display: flex;
        flex-direction: column;
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        backdrop-filter: blur(12px);
    }}

    .cp-feature-card:hover {{
        transform: translateY(-4px);
        border-color: rgba(0, 217, 255, 0.45);
        box-shadow: 0 12px 28px -6px rgba(0, 0, 0, 0.6), 0 0 20px rgba(0, 217, 255, 0.15);
    }}

    .cp-feature-icon {{
        font-size: 1.85rem;
        margin-bottom: 14px;
        display: inline-block;
    }}

    .cp-feature-title {{
        font-family: var(--cp-font-sans);
        font-size: 1.12rem;
        font-weight: 700;
        color: #EAF4FF;
        margin-bottom: 10px;
    }}

    .cp-feature-desc {{
        font-size: 0.88rem;
        line-height: 1.6;
        color: #94A3B8;
        flex-grow: 1;
    }}

    .cp-feature-badge {{
        align-self: flex-start;
        font-family: var(--cp-font-mono);
        font-size: 0.70rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 6px;
        background: rgba(37, 99, 235, 0.18);
        color: #38BDF8;
        border: 1px solid rgba(59, 130, 246, 0.30);
        margin-top: 14px;
    }}

    /* -------------------------------------------------------------------------
       PIPELINE SHOWCASE
       ------------------------------------------------------------------------- */
    .cp-pipeline-container {{
        background: rgba(8, 15, 32, 0.85);
        border: 1px solid rgba(0, 217, 255, 0.25);
        border-radius: 16px;
        padding: 32px 24px;
        margin-bottom: 48px;
        box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5);
    }}

    .cp-pipeline-steps {{
        display: flex;
        align-items: stretch;
        justify-content: space-between;
        gap: 12px;
        overflow-x: auto;
        padding: 10px 0;
    }}

    .cp-pipe-step {{
        flex: 1;
        min-width: 150px;
        background: rgba(16, 27, 48, 0.85);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 10px;
        padding: 18px 12px;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: all 0.2s ease;
        position: relative;
    }}

    .cp-pipe-step:hover {{
        border-color: #00D9FF;
        box-shadow: 0 0 16px rgba(0, 217, 255, 0.2);
    }}

    .cp-pipe-num {{
        font-family: var(--cp-font-mono);
        font-size: 0.72rem;
        font-weight: 700;
        color: #00D9FF;
        margin-bottom: 6px;
    }}

    .cp-pipe-name {{
        font-family: var(--cp-font-sans);
        font-size: 0.88rem;
        font-weight: 700;
        color: #EAF4FF;
        margin-bottom: 6px;
        line-height: 1.25;
    }}

    .cp-pipe-meta {{
        font-size: 0.72rem;
        color: #94A3B8;
        line-height: 1.35;
    }}

    .cp-pipe-arrow {{
        display: flex;
        align-items: center;
        color: #38BDF8;
        font-size: 1.1rem;
        font-weight: 700;
    }}

    /* -------------------------------------------------------------------------
       TECHNOLOGY CARDS
       ------------------------------------------------------------------------- */
    .cp-tech-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 48px;
    }}

    .cp-tech-card {{
        background: rgba(16, 27, 48, 0.70);
        border: 1px solid rgba(59, 130, 246, 0.18);
        border-radius: 12px;
        padding: 18px 16px;
        display: flex;
        align-items: center;
        gap: 14px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }}

    .cp-tech-card:hover {{
        transform: translateY(-2px);
        border-color: rgba(0, 217, 255, 0.4);
    }}

    .cp-tech-icon {{
        font-size: 1.8rem;
        line-height: 1;
    }}

    .cp-tech-name {{
        font-family: var(--cp-font-sans);
        font-size: 0.95rem;
        font-weight: 700;
        color: #EAF4FF;
    }}

    .cp-tech-role {{
        font-family: var(--cp-font-mono);
        font-size: 0.72rem;
        color: #00D9FF;
    }}

    /* -------------------------------------------------------------------------
       APPLICATIONS & ABOUT
       ------------------------------------------------------------------------- */
    .cp-apps-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 18px;
        margin-bottom: 48px;
    }}

    .cp-app-card {{
        background: rgba(16, 27, 48, 0.65);
        border: 1px solid rgba(59, 130, 246, 0.18);
        border-radius: 12px;
        padding: 22px 18px;
        transition: all 0.2s ease;
    }}

    .cp-app-card:hover {{
        border-color: rgba(0, 217, 255, 0.4);
        transform: translateY(-2px);
    }}

    .cp-app-icon {{
        font-size: 1.8rem;
        margin-bottom: 12px;
    }}

    .cp-app-card h4 {{
        font-size: 1.05rem;
        font-weight: 700;
        color: #EAF4FF;
        margin-bottom: 8px;
    }}

    .cp-app-card p {{
        font-size: 0.85rem;
        line-height: 1.6;
        color: #94A3B8;
        margin: 0;
    }}

    .cp-about-card {{
        background: linear-gradient(135deg, rgba(16, 27, 48, 0.80) 0%, rgba(8, 15, 32, 0.90) 100%);
        border: 1px solid rgba(0, 217, 255, 0.22);
        border-radius: 18px;
        padding: 36px 40px;
        margin-bottom: 48px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    }}

    .cp-about-title {{
        font-size: 1.8rem;
        font-weight: 800;
        color: #EAF4FF;
        margin-bottom: 14px;
        letter-spacing: -0.02em;
    }}

    .cp-about-body {{
        font-size: 0.96rem;
        line-height: 1.75;
        color: #CBD5E1;
        margin-bottom: 20px;
    }}

    .cp-about-highlights {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 18px;
        margin-top: 24px;
    }}

    .cp-about-highlight-item {{
        background: rgba(8, 15, 32, 0.80);
        border: 1px solid rgba(59, 130, 246, 0.20);
        border-radius: 10px;
        padding: 16px;
    }}

    .cp-about-highlight-item h5 {{
        font-size: 0.92rem;
        font-weight: 700;
        color: #00D9FF;
        margin-bottom: 6px;
    }}

    .cp-about-highlight-item p {{
        font-size: 0.82rem;
        color: #94A3B8;
        line-height: 1.5;
        margin: 0;
    }}

    /* -------------------------------------------------------------------------
       FINAL CTA & FOOTER
       ------------------------------------------------------------------------- */
    .cp-cta-banner {{
        background: radial-gradient(circle at 50% 50%, rgba(37, 99, 235, 0.30) 0%, rgba(8, 15, 32, 0.95) 100%);
        border: 1px solid rgba(0, 217, 255, 0.35);
        border-radius: 20px;
        padding: 44px 32px 32px 32px;
        text-align: center;
        margin-bottom: 48px;
        box-shadow: 0 14px 40px -8px rgba(0, 0, 0, 0.6), 0 0 28px rgba(0, 217, 255, 0.12);
    }}

    .cp-cta-banner h2 {{
        font-family: var(--cp-font-sans);
        font-size: 2.3rem;
        font-weight: 800;
        color: #EAF4FF;
        margin-bottom: 12px;
        letter-spacing: -0.02em;
    }}

    .cp-cta-banner p {{
        font-size: 1.08rem;
        color: #94A3B8;
        max-width: 680px;
        margin: 0 auto 28px auto;
        line-height: 1.6;
    }}

    .cp-footer {{
        border-top: 1px solid rgba(59, 130, 246, 0.20);
        padding-top: 32px;
        margin-top: 48px;
    }}

    .cp-footer-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
        gap: 16px;
    }}

    .cp-footer-brand-info h4 {{
        font-family: var(--cp-font-sans);
        font-size: 1.2rem;
        font-weight: 800;
        color: #EAF4FF;
        margin-bottom: 4px;
    }}

    .cp-footer-brand-info p {{
        font-size: 0.85rem;
        color: #64748B;
        margin: 0;
    }}

    .cp-footer-links {{
        display: flex;
        gap: 20px;
    }}

    .cp-footer-link {{
        font-size: 0.86rem;
        color: #94A3B8;
        text-decoration: none;
        transition: color 0.2s ease;
    }}

    .cp-footer-link:hover {{
        color: #00D9FF;
    }}

    .cp-footer-bottom {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.78rem;
        color: #64748B;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        padding-top: 18px;
        flex-wrap: wrap;
        gap: 12px;
    }}

    /* -------------------------------------------------------------------------
       RESPONSIVE BREAKPOINTS
       ------------------------------------------------------------------------- */
    @media (max-width: 1024px) {{
        .cp-features-grid,
        .cp-tech-grid,
        .cp-apps-grid,
        .cp-metrics-strip {{
            grid-template-columns: repeat(2, 1fr);
        }}
        .cp-story-grid {{
            grid-template-columns: 1fr;
        }}
        .cp-about-highlights {{
            grid-template-columns: 1fr;
        }}
    }}

    @media (max-width: 768px) {{
        .cp-hero-headline {{
            font-size: 2.2rem;
        }}
        .cp-nav-menu {{
            display: none;
        }}
        .cp-features-grid,
        .cp-tech-grid,
        .cp-apps-grid,
        .cp-metrics-strip {{
            grid-template-columns: 1fr;
        }}
        .cp-pipeline-steps {{
            flex-direction: column;
        }}
        .cp-pipe-arrow {{
            justify-content: center;
            transform: rotate(90deg);
            padding: 4px 0;
        }}
        .cp-story-chapter {{
            padding: 24px 20px;
        }}
        .cp-footer-top,
        .cp-footer-bottom {{
            flex-direction: column;
            text-align: center;
        }}
    }}
</style>
"""
    return base_css + extra_css


def render_landing_page(on_launch: Optional[Callable[[], None]] = None) -> None:
    """
    Renders the CROWDPatrol 2.0 public landing page.
    Args:
        on_launch: Optional callback invoked when the user enters the command center.
    """
    # 1. Inject Comprehensive Global CSS
    st.markdown(get_landing_page_css(), unsafe_allow_html=True)

    def _do_launch():
        if on_launch:
            on_launch()
        else:
            st.session_state["current_page"] = "dashboard"
            st.query_params["page"] = "dashboard"
            st.rerun()

    # ==========================================================================
    # 2. TOP NAVIGATION BAR
    # ==========================================================================
    st.markdown('<div id="hero" class="cp-anchor"></div>', unsafe_allow_html=True)

    # Render custom HTML Navbar layout with anchor links and interactive action
    nav_col1, nav_col2 = st.columns([7, 3])
    with nav_col1:
        st.markdown(
            """
            <div class="cp-navbar-container" style="margin-bottom: 0px;">
                <a href="#hero" class="cp-brand">
                    <div class="cp-brand-logo">🛡️</div>
                    <div>
                        <div class="cp-brand-text">CROWD<span>PATROL</span></div>
                        <div class="cp-brand-sub">AI Crowd Safety & Risk Intelligence</div>
                    </div>
                </a>
                <ul class="cp-nav-menu">
                    <li><a href="#hero" class="cp-nav-link">Home</a></li>
                    <li><a href="#storytelling" class="cp-nav-link">Story</a></li>
                    <li><a href="#features" class="cp-nav-link">Features</a></li>
                    <li><a href="#how-it-works" class="cp-nav-link">How It Works</a></li>
                    <li><a href="#technology" class="cp-nav-link">Technology</a></li>
                    <li><a href="#applications" class="cp-nav-link">Applications</a></li>
                    <li><a href="#about" class="cp-nav-link">About</a></li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )
    with nav_col2:
        st.write("")  # Spacing alignment
        if st.button("🚨 Enter Command Center", key="nav_open_dashboard_btn", use_container_width=True, type="primary"):
            _do_launch()

    st.write("")

    # ==========================================================================
    # 3. CINEMATIC HERO SECTION
    # ==========================================================================
    st.markdown(
        """
        <div class="cp-hero-container">
            <div class="cp-badge-pill">
                <span class="cp-status-dot"></span>
                AUTONOMOUS CROWD SURVEILLANCE &bull; EDGE AI PLATFORM
            </div>
            <h1 class="cp-hero-headline">
                SEE THE CROWD.<br>
                <span class="gradient-text">BEFORE THE RISK.</span>
            </h1>
            <div class="cp-hero-subheading">
                Smarter Crowd Monitoring. Safer Public Spaces.
            </div>
            <p class="cp-hero-description">
                Intelligent crowd monitoring. Real-time awareness. Smarter public safety. 
                AI-powered crowd monitoring and risk assessment platform engineered to transform ordinary CCTV feeds 
                into autonomous, life-saving situational intelligence before critical stampede thresholds occur.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Hero Key Metrics Strip
    st.markdown(
        """
        <div class="cp-metrics-strip">
            <div class="cp-metric-box">
                <div class="cp-metric-value">30+ FPS</div>
                <div class="cp-metric-label">Real-Time Inference</div>
                <div class="cp-metric-sub">Target benchmark on tested GPU/CPU</div>
            </div>
            <div class="cp-metric-box">
                <div class="cp-metric-value">Low Latency</div>
                <div class="cp-metric-label">Edge Ingestion Pipeline</div>
                <div class="cp-metric-sub">Zero-copy architecture target</div>
            </div>
            <div class="cp-metric-box">
                <div class="cp-metric-value">4&times;4 Grid</div>
                <div class="cp-metric-label">Spatial Density Mapping</div>
                <div class="cp-metric-sub">Localized surge & choke analysis</div>
            </div>
            <div class="cp-metric-box">
                <div class="cp-metric-value">Privacy-First</div>
                <div class="cp-metric-label">Privacy by Design</div>
                <div class="cp-metric-sub">No facial recognition or biometric ID</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Hero Action Buttons
    h_col1, h_col2, h_col3 = st.columns([3.5, 3.25, 3.25])
    with h_col1:
        if st.button("🚨 Enter Command Center", key="hero_launch_dashboard_btn", use_container_width=True, type="primary"):
            _do_launch()
    with h_col2:
        st.markdown(
            """
            <a href="#features" style="display:block; text-align:center; padding:9px 16px; background:rgba(16,27,48,0.85); color:#EAF4FF; font-family:var(--cp-font-sans); font-size:0.95rem; font-weight:700; border:1px solid rgba(0,217,255,0.3); border-radius:8px; text-decoration:none; transition:all 0.2s ease;">
                🔍 Explore Features & Platform
            </a>
            """,
            unsafe_allow_html=True
        )
    with h_col3:
        st.markdown(
            """
            <a href="#pipeline" style="display:block; text-align:center; padding:9px 16px; background:rgba(16,27,48,0.85); color:#EAF4FF; font-family:var(--cp-font-sans); font-size:0.95rem; font-weight:700; border:1px solid rgba(0,217,255,0.3); border-radius:8px; text-decoration:none; transition:all 0.2s ease;">
                ⚡ Discover Technology
            </a>
            """,
            unsafe_allow_html=True
        )

    st.write("")
    st.write("")

    # ==========================================================================
    # 4. VISUAL AI SURVEILLANCE CENTERPIECE
    # ==========================================================================
    render_surveillance_centerpiece()

    st.write("")
    st.write("")

    # ==========================================================================
    # 5. CINEMATIC 5-CHAPTER STORYTELLING SECTIONS
    # ==========================================================================
    st.markdown('<div id="storytelling" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-section-header">
            <div class="cp-section-tag">Cinematic Platform Narrative</div>
            <h2 class="cp-section-title">The Evolution of Crowd Safety</h2>
            <p class="cp-section-subtitle">
                How autonomous edge computer vision bridges the gap between passive human observation and proactive life-saving intervention.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Chapter 1: The Problem
    st.markdown(
        """
        <div class="cp-story-chapter">
            <div class="cp-chapter-badge">Chapter 01 &bull; The Vulnerability</div>
            <h3 class="cp-chapter-title">Thousands of People. One Moment Can Change Everything.</h3>
            <p class="cp-chapter-lead">
                In crowded public concourses, religious gatherings, transit hubs, and sports stadiums, catastrophic crowd disasters 
                rarely happen without early physical precursors. Yet traditional CCTV infrastructure remains entirely passive: 
                recording video footage for post-disaster postmortems rather than warning security operators before tragedy strikes.
            </p>
            <div class="cp-story-grid">
                <div class="cp-story-card">
                    <div class="cp-story-card-title">❌ Passive CCTV & Human Operator Fatigue</div>
                    <div class="cp-story-card-desc">
                        Human operators monitoring banks of 20+ video monitors experience severe cognitive fatigue within 20 minutes, 
                        missing subtle localized density accumulation and shockwave turbulence in dense pedestrian crowds until physical collapse begins.
                    </div>
                </div>
                <div class="cp-story-card">
                    <div class="cp-story-card-title">⚡ Proactive Intervention Window</div>
                    <div class="cp-story-card-desc">
                        Crowd safety literature documents that crowd turbulence and high-density crushes can escalate rapidly once local 
                        densities exceed critical physical thresholds. Automated monitoring aims to alert safety teams well before physical collapse conditions manifest.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Chapter 2: The Intelligence
    st.markdown(
        """
        <div class="cp-story-chapter">
            <div class="cp-chapter-badge">Chapter 02 &bull; The Neural Engine</div>
            <h3 class="cp-chapter-title">From Pixels to Intelligence.</h3>
            <p class="cp-chapter-lead">
                CROWDPatrol converts raw unstructured camera pixels into actionable mathematical telemetry. 
                Using high-performance dual-model deep learning, the platform detects, localizes, and tracks every individual 
                at 30+ frames per second directly on commodity edge processors.
            </p>
            <div class="cp-story-grid">
                <div class="cp-story-card">
                    <div class="cp-story-card-title">👥 Person Mode (YOLOv8 &bull; 640&times;640)</div>
                    <div class="cp-story-card-desc">
                        Standard concourses, pedestrian plazas, and perimeter walkways are analyzed with full-body bounding box detection 
                        optimized for standing, walking, and moving crowds under variable lighting conditions.
                    </div>
                </div>
                <div class="cp-story-card">
                    <div class="cp-story-card-title">🎯 Head Mode (Overhead Crowd Counting)</div>
                    <div class="cp-story-card-desc">
                        In extreme high-density choke points where human bodies occlude one another, CROWDPatrol dynamically activates overhead head-detection 
                        (640&times;640 resolution, 0.25 confidence) to preserve count accuracy when bodies are hidden from camera perspective.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Chapter 3: The Awareness
    st.markdown(
        """
        <div class="cp-story-chapter">
            <div class="cp-chapter-badge">Chapter 03 &bull; Spatial Understanding</div>
            <h3 class="cp-chapter-title">See What Ordinary Cameras Cannot.</h3>
            <p class="cp-chapter-lead">
                Individual detections are only the foundation. CROWDPatrol models collective crowd physics across space and time. 
                By subdividing camera viewports into dynamic 4&times;4 spatial density grids and analyzing Farneback dense optical flow vectors, 
                the system visualizes invisible pressure gradients, turbulence, and sudden counter-directional movements.
            </p>
            <div class="cp-story-grid">
                <div class="cp-story-card">
                    <div class="cp-story-card-title">🔥 4&times;4 Spatial Grid & Peak Cell Analysis</div>
                    <div class="cp-story-card-desc">
                        Rather than averaging density across a whole camera view, CROWDPatrol isolates localized choke points. 
                        If an exit door or stairwell experiences acute congestion while the main hall is empty, the system pinpoints the exact cell.
                    </div>
                </div>
                <div class="cp-story-card">
                    <div class="cp-story-card-title">🌊 Thermal Density Heatmaps & Flow Vectors</div>
                    <div class="cp-story-card-desc">
                        Live Gaussian kernel density estimation generates real-time thermal overlays while Farneback optical flow extracts 
                        motion vector fields, detecting rapid panic surges, directional deadlocks, and counterflow turbulence.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Chapter 4: The Response
    st.markdown(
        """
        <div class="cp-story-chapter">
            <div class="cp-chapter-badge">Chapter 04 &bull; Autonomous Action</div>
            <h3 class="cp-chapter-title">Recognize Risk. Stay Ahead.</h3>
            <p class="cp-chapter-lead">
                Data without automated escalation is ineffective. CROWDPatrol features a composite mathematical Risk Engine 
                that combines spatial density (65% weight) and anomalous crowd velocity (35% weight) into an unambiguous 0–100 Risk Score. 
                When critical risk thresholds are crossed, emergency protocols trigger automatically without human delay.
            </p>
            <div class="cp-story-grid">
                <div class="cp-story-card">
                    <div class="cp-story-card-title">🚨 Multi-Tier Risk Escalation</div>
                    <div class="cp-story-card-desc">
                        Color-coded operational alert tiers (NORMAL &bull; CAUTION &bull; WARNING &bull; CRITICAL) give security supervisors 
                        instant situational clarity, backed by moving-average hysteresis filters to eliminate false-positive jitter.
                    </div>
                </div>
                <div class="cp-story-card">
                    <div class="cp-story-card-title">📡 Real-Time Dispatch: Firebase + SMTP</div>
                    <div class="cp-story-card-desc">
                        Critical emergency events automatically dispatch detailed email incident alerts via secure SMTP and synchronize 
                        sub-second event records to Firebase Realtime Database for mobile field personnel and cloud command centers.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Chapter 5: The Platform
    st.markdown(
        """
        <div class="cp-story-chapter">
            <div class="cp-chapter-badge">Chapter 05 &bull; The Enterprise Architecture</div>
            <h3 class="cp-chapter-title">One Platform. Complete Crowd Intelligence.</h3>
            <p class="cp-chapter-lead">
                Built from the ground up for command centers, municipal safety departments, transit authorities, and event organizers. 
                CROWDPatrol unites multi-camera RTSP ingestion, high-FPS interactive telemetry, and strict Privacy-by-Design 
                into a cohesive, low-footprint platform.
            </p>
            <div class="cp-story-grid">
                <div class="cp-story-card">
                    <div class="cp-story-card-title">🎥 Multi-Camera Synchronous Grid</div>
                    <div class="cp-story-card-desc">
                        Ingest up to 4 simultaneous live RTSP video streams, USB webcams, or phone camera feeds. 
                        Seamlessly switch between high-level 2&times;2 grid situational awareness and granular Focus Feed inspection.
                    </div>
                </div>
                <div class="cp-story-card">
                    <div class="cp-story-card-title">🔒 Strict Privacy by Design</div>
                    <div class="cp-story-card-desc">
                        CROWDPatrol strictly calculates density, velocity, and spatial physics. It performs zero facial recognition, 
                        zero biometric fingerprinting, and captures no Personally Identifiable Information (PII)—ensuring full ethical compliance.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")
    st.write("")

    # ==========================================================================
    # 6. FEATURE SHOWCASE (8 CORE CAPABILITIES)
    # ==========================================================================
    st.markdown('<div id="features" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-section-header">
            <div class="cp-section-tag">Autonomous Edge Intelligence</div>
            <h2 class="cp-section-title">Core Safety Capabilities</h2>
            <p class="cp-section-subtitle">
                Eight specialized computer vision and crowd dynamics technologies operating in unison.
            </p>
        </div>
        <div class="cp-features-grid">
            <div class="cp-feature-card">
                <div class="cp-feature-icon">👥</div>
                <div class="cp-feature-title">Person Detection</div>
                <div class="cp-feature-desc">
                    High-performance YOLOv8 model operating at 640&times;640 resolution to detect individuals in wide pedestrian areas, plazas, and open corridors.
                </div>
                <div class="cp-feature-badge">YOLOv8 &bull; 640&times;640</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">🎯</div>
                <div class="cp-feature-title">Head Detection</div>
                <div class="cp-feature-desc">
                    Specialized overhead crowd counting model engineered to preserve accurate person counts in densely occluded environments where full bodies are hidden.
                </div>
                <div class="cp-feature-badge">YOLOv8 Head Model</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">🔄</div>
                <div class="cp-feature-title">Multi-Object Tracking</div>
                <div class="cp-feature-desc">
                    DeepSORT tracker paired with MobileNetV2 appearance embedding and Kalman filtering to maintain persistent individual IDs across temporary occlusions.
                </div>
                <div class="cp-feature-badge">DeepSORT + MobileNetV2</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">📊</div>
                <div class="cp-feature-title">Crowd Density Analysis</div>
                <div class="cp-feature-desc">
                    Dynamic 4&times;4 spatial grid mapping localized crowd concentrations and peak cell density metrics to pinpoint bottleneck danger zones.
                </div>
                <div class="cp-feature-badge">4&times;4 Spatial Grid</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">🔥</div>
                <div class="cp-feature-title">Thermal Density Heatmaps</div>
                <div class="cp-feature-desc">
                    Real-time Gaussian kernel density estimation producing intuitive color-coded overlays that highlight crowd accumulation areas instantaneously.
                </div>
                <div class="cp-feature-badge">Gaussian Heatmap Overlay</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">🌊</div>
                <div class="cp-feature-title">Motion & Anomaly Analysis</div>
                <div class="cp-feature-desc">
                    Farneback dense optical flow tracking crowd velocity vectors, identifying sudden panic runs, directional deadlocks, and turbulent counterflow.
                </div>
                <div class="cp-feature-badge">Farneback Optical Flow</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">⚠️</div>
                <div class="cp-feature-title">Risk Assessment</div>
                <div class="cp-feature-desc">
                    Composite multi-factor risk scoring engine combining spatial crowd density (65%) and velocity anomaly (35%) into an actionable 0–100 index.
                </div>
                <div class="cp-feature-badge">Composite Metric Engine</div>
            </div>
            <div class="cp-feature-card">
                <div class="cp-feature-icon">🚨</div>
                <div class="cp-feature-title">Automated Alerts</div>
                <div class="cp-feature-desc">
                    Automated email alerts via secure SMTP and instant cloud synchronization to Firebase Realtime Database with actionable spatial coordinates.
                </div>
                <div class="cp-feature-badge">SMTP + Firebase RTDB</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==========================================================================
    # 7. HOW IT WORKS / PIPELINE SHOWCASE
    # ==========================================================================
    st.markdown('<div id="how-it-works" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div id="pipeline" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-section-header">
            <div class="cp-section-tag">System Architecture</div>
            <h2 class="cp-section-title">End-to-End Processing Pipeline</h2>
            <p class="cp-section-subtitle">
                End-to-end edge architecture designed for low-latency detection, tracking, and risk alerting.
            </p>
        </div>
        <div class="cp-pipeline-container">
            <div class="cp-pipeline-steps">
                <div class="cp-pipe-step">
                    <div class="cp-pipe-num">STAGE 01</div>
                    <div class="cp-pipe-name">Video Input</div>
                    <div class="cp-pipe-meta">RTSP / USB / File<br>Zero-copy frame capture</div>
                </div>
                <div class="cp-pipe-arrow">&rarr;</div>
                <div class="cp-pipe-step">
                    <div class="cp-pipe-num">STAGE 02</div>
                    <div class="cp-pipe-name">YOLOv8 Detection</div>
                    <div class="cp-pipe-meta">640&times;640 resolution<br>Person / Head Bboxes</div>
                </div>
                <div class="cp-pipe-arrow">&rarr;</div>
                <div class="cp-pipe-step">
                    <div class="cp-pipe-num">STAGE 03</div>
                    <div class="cp-pipe-name">DeepSORT Tracking</div>
                    <div class="cp-pipe-meta">MobileNetV2 ReID<br>Kalman trajectory state</div>
                </div>
                <div class="cp-pipe-arrow">&rarr;</div>
                <div class="cp-pipe-step">
                    <div class="cp-pipe-num">STAGE 04</div>
                    <div class="cp-pipe-name">Density & Motion</div>
                    <div class="cp-pipe-meta">4&times;4 spatial grid<br>Farneback optical flow</div>
                </div>
                <div class="cp-pipe-arrow">&rarr;</div>
                <div class="cp-pipe-step">
                    <div class="cp-pipe-num">STAGE 05</div>
                    <div class="cp-pipe-name">Risk Assessment</div>
                    <div class="cp-pipe-meta">Composite 0–100 score<br>Density 65% + Flow 35%</div>
                </div>
                <div class="cp-pipe-arrow">&rarr;</div>
                <div class="cp-pipe-step">
                    <div class="cp-pipe-num">STAGE 06</div>
                    <div class="cp-pipe-name">Dashboard & Alerts</div>
                    <div class="cp-pipe-meta">Live HUD telemetry<br>SMTP + Firebase RTDB</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==========================================================================
    # 8. TECHNOLOGY STACK
    # ==========================================================================
    st.markdown('<div id="technology" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-section-header">
            <div class="cp-section-tag">Engineering Foundation</div>
            <h2 class="cp-section-title">Enterprise Technology Stack</h2>
            <p class="cp-section-subtitle">
                Built on battle-tested open-source frameworks and modern cloud architectures.
            </p>
        </div>
        <div class="cp-tech-grid">
            <div class="cp-tech-card">
                <div class="cp-tech-icon">👁️</div>
                <div>
                    <div class="cp-tech-name">YOLOv8</div>
                    <div class="cp-tech-role">Ultralytics Neural Detector</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">🎯</div>
                <div>
                    <div class="cp-tech-name">DeepSORT</div>
                    <div class="cp-tech-role">Multi-Object Tracking</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">🧠</div>
                <div>
                    <div class="cp-tech-name">MobileNetV2</div>
                    <div class="cp-tech-role">Appearance Embedder (ReID)</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">⚡</div>
                <div>
                    <div class="cp-tech-name">OpenCV</div>
                    <div class="cp-tech-role">Computer Vision & Optical Flow</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">🐍</div>
                <div>
                    <div class="cp-tech-name">Python</div>
                    <div class="cp-tech-role">High-Performance Runtime</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">📊</div>
                <div>
                    <div class="cp-tech-name">Streamlit</div>
                    <div class="cp-tech-role">Interactive Live Dashboard</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">🔥</div>
                <div>
                    <div class="cp-tech-name">Firebase</div>
                    <div class="cp-tech-role">Realtime Cloud DB & Sync</div>
                </div>
            </div>
            <div class="cp-tech-card">
                <div class="cp-tech-icon">📧</div>
                <div>
                    <div class="cp-tech-name">SMTP Dispatcher</div>
                    <div class="cp-tech-role">Automated Emergency Email Alerts</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==========================================================================
    # 9. DEPLOYMENT APPLICATIONS
    # ==========================================================================
    st.markdown('<div id="applications" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-section-header">
            <div class="cp-section-tag">Operational Venues</div>
            <h2 class="cp-section-title">Deployment Scenarios</h2>
            <p class="cp-section-subtitle">
                Engineered for any public venue where crowd safety and density management are paramount.
            </p>
        </div>
        <div class="cp-apps-grid">
            <div class="cp-app-card">
                <div class="cp-app-icon">🏛️</div>
                <h4>Public Gatherings</h4>
                <p>Municipal plazas, political rallies, cultural parades, and open-air public exhibitions managing high-density pedestrian flow.</p>
            </div>
            <div class="cp-app-card">
                <div class="cp-app-icon">🎪</div>
                <h4>Festivals & Concerts</h4>
                <p>Music festivals, pilgrim processions, and religious events requiring continuous monitoring of stage fronts and choke corridors.</p>
            </div>
            <div class="cp-app-card">
                <div class="cp-app-icon">🏟️</div>
                <h4>Stadiums & Arenas</h4>
                <p>Sports complexes and entertainment arenas managing synchronized gate ingress, concession bottlenecks, and post-match exit crushes.</p>
            </div>
            <div class="cp-app-card">
                <div class="cp-app-icon">🚆</div>
                <h4>Transport Hubs</h4>
                <p>Metro railway stations, international airport terminals, and bus interchanges experiencing intense recurring commuter volume peaks.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==========================================================================
    # 10. ABOUT & ACADEMIC CREDITS
    # ==========================================================================
    st.markdown('<div id="about" class="cp-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-about-card">
            <div class="cp-section-tag" style="text-align: left;">Academic & Engineering Background</div>
            <h3 class="cp-about-title">About the CrowdPatrol Project</h3>
            <p class="cp-about-body">
                Crowd disasters and stampedes around the globe have claimed thousands of lives due to delayed human reaction and lack of automated situational awareness. 
                Traditional CCTV surveillance relies heavily on human operators who experience cognitive fatigue when monitoring dozens of simultaneous camera feeds.
            </p>
            <p class="cp-about-body">
                <strong>CrowdPatrol</strong> was conceived and developed as a <strong>Final Year Major Project</strong> at 
                <strong>AMC Engineering College</strong> (Department of Computer Science & Engineering) to solve this challenge through proactive, automated edge-intelligence. 
                By shifting surveillance from passive recording to active autonomous risk assessment, CrowdPatrol alerts safety officers the moment crowd density or panic velocity crosses safe operational thresholds.
            </p>
            <div class="cp-about-highlights">
                <div class="cp-about-highlight-item">
                    <h5>🔒 Privacy by Design</h5>
                    <p>Focuses on crowd physics, density gradients, and motion dynamics rather than invasive individual facial recognition.</p>
                </div>
                <div class="cp-about-highlight-item">
                    <h5>⚡ Low Latency Edge Ingestion</h5>
                    <p>Optimized for lightweight commodity hardware, edge cameras, and mobile phone RTSP streams.</p>
                </div>
                <div class="cp-about-highlight-item">
                    <h5>🎓 Academic Research Focus</h5>
                    <p>Engineered with reproducible benchmarks, modular pipeline components, and standardized evaluation protocols.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ==========================================================================
    # 11. FINAL CALL TO ACTION BANNER
    # ==========================================================================
    st.markdown(
        """
        <div class="cp-cta-banner">
            <h2>Ready to Monitor Crowd Situational Safety?</h2>
            <p>
                Launch the live interactive command center now to test webcam streams, multi-camera CCTV grids, 
                real-time heatmaps, and automated emergency notification dispatchers.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Final CTA Launch Button
    cta_l, cta_c, cta_r = st.columns([3, 4, 3])
    with cta_c:
        if st.button("🚀 Enter Command Center", key="cta_launch_dashboard_btn", use_container_width=True, type="primary"):
            _do_launch()

    # ==========================================================================
    # 12. FOOTER SECTION
    # ==========================================================================
    st.markdown(
        """
        <footer class="cp-footer">
            <div class="cp-footer-top">
                <div class="cp-footer-brand-info">
                    <h4>🛡️ CrowdPatrol</h4>
                    <p>Autonomous AI Crowd Monitoring & Emergency Risk Mitigation Platform</p>
                </div>
                <div class="cp-footer-links">
                    <a href="#hero" class="cp-footer-link">Home</a>
                    <a href="#storytelling" class="cp-footer-link">Story</a>
                    <a href="#features" class="cp-footer-link">Features</a>
                    <a href="#how-it-works" class="cp-footer-link">How It Works</a>
                    <a href="#technology" class="cp-footer-link">Technology</a>
                    <a href="#applications" class="cp-footer-link">Applications</a>
                    <a href="#about" class="cp-footer-link">About</a>
                </div>
            </div>
            <div class="cp-footer-bottom">
                <div>
                    AMC Engineering College — Department of Computer Science & Engineering<br>
                    Final Year Major Project (7th/8th Semester)
                </div>
                <div>
                    Academic Prototype Notice: For experimental crowd density & safety research benchmarking.
                </div>
            </div>
        </footer>
        """,
        unsafe_allow_html=True
    )
