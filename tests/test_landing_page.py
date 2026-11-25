"""
Phase 6.1 Unit & Integration Test Suite — Landing Page UI & Navigation
Verifies:
1. CSS styling: dark navy/charcoal background, blue accents, typography, responsive media queries.
2. Section content integrity:
   - Navigation (CrowdPatrol logo, Home, Features, How It Works, Technology, Applications, About, Open Dashboard)
   - Hero (Heading: "Smarter Crowd Monitoring. Safer Public Spaces.", AI platform description, Primary/Secondary CTAs, stats bar)
   - Features (Person detection, head detection, multi-object tracking, density analysis, heatmaps, motion analysis, risk assessment, automated alerts)
   - How It Works (6-stage pipeline: Camera/video input -> YOLOv8 -> DeepSORT -> Density/Motion -> Risk Assessment -> Dashboard/Alerts)
   - Technology (YOLOv8, DeepSORT, MobileNetV2, OpenCV, Python, Streamlit, Firebase)
   - Applications (Public gatherings, festivals, stadiums, transport hubs)
   - About (AMC Engineering College Major Project, mission, ethics)
   - Footer (CrowdPatrol branding, project credits, prototype notice)
3. Navigation and AppTest state transitions:
   - Initial page is 'landing'
   - Launch Dashboard button transitions to 'dashboard'
   - Return to Landing Page button transitions to 'landing'
   - Query parameter deep-linking (?page=dashboard)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.landing_page import get_landing_page_css, render_landing_page


def test_landing_page_css_theme_and_colors():
    """Verify CSS incorporates dark navy/charcoal background, blue accents, and responsive layout."""
    css = get_landing_page_css()
    assert css is not None and len(css) > 500

    # Dark navy / charcoal background colors
    assert "#070B14" in css or "#0A0F1D" in css or "#0B132B" in css

    # Vibrant blue & cyan accents
    assert "#00D2FF" in css or "#38BDF8" in css
    assert "#1D4ED8" in css or "#2563EB" in css or "#3B82F6" in css

    # Modern security-tech typography and fonts
    assert "Plus Jakarta Sans" in css or "system-ui" in css
    assert "JetBrains Mono" in css or "monospace" in css

    # Responsive media queries
    assert "@media (max-width: 768px)" in css
    assert "@media (max-width: 1024px)" in css

    # Hover animations and smooth scroll
    assert "scroll-behavior: smooth" in css
    assert "transition:" in css
    assert "keyframes" in css


def test_landing_page_sections_rendered():
    """Verify render_landing_page renders all required sections with accurate content."""
    mock_markdown_calls = []

    def mock_markdown(content, unsafe_allow_html=False):
        mock_markdown_calls.append(content)

    mock_columns = MagicMock()
    mock_columns.side_effect = lambda spec: [MagicMock() for _ in range(len(spec) if isinstance(spec, list) else spec)]

    mock_button = MagicMock(return_value=False)

    with patch("streamlit.markdown", side_effect=mock_markdown), \
         patch("streamlit.columns", side_effect=mock_columns), \
         patch("streamlit.button", side_effect=mock_button), \
         patch("streamlit.session_state", {}):

        render_landing_page()

    full_rendered_text = " ".join(str(c) for c in mock_markdown_calls)

    # 1. Navigation
    assert "Crowd<span>Patrol</span>" in full_rendered_text or "CrowdPatrol" in full_rendered_text
    assert "Home" in full_rendered_text
    assert "Features" in full_rendered_text
    assert "How It Works" in full_rendered_text
    assert "Technology" in full_rendered_text
    assert "Applications" in full_rendered_text
    assert "About" in full_rendered_text

    # 2. Hero Section
    assert "Smarter Crowd Monitoring.<br>Safer Public Spaces." in full_rendered_text or "Smarter Crowd Monitoring" in full_rendered_text
    assert "AI-powered crowd monitoring and risk assessment platform" in full_rendered_text or "AI-powered" in full_rendered_text
    assert "Explore Features" in full_rendered_text
    assert "30+ FPS" in full_rendered_text
    assert "Real-Time Inference" in full_rendered_text

    # 3. Features Section (All 8 core capabilities)
    assert "Person Detection" in full_rendered_text
    assert "Head Detection" in full_rendered_text
    assert "Multi-Object Tracking" in full_rendered_text
    assert "Crowd Density Analysis" in full_rendered_text
    assert "Heatmaps" in full_rendered_text or "Thermal Density Heatmaps" in full_rendered_text
    assert "Motion & Anomaly Analysis" in full_rendered_text or "Motion Analysis" in full_rendered_text
    assert "Risk Assessment" in full_rendered_text
    assert "Automated Alerts" in full_rendered_text or "Automated email alerts" in full_rendered_text or "SMTP" in full_rendered_text

    # 4. How It Works Pipeline (All 6 stages)
    assert "Video Input" in full_rendered_text
    assert "YOLOv8 Detection" in full_rendered_text
    assert "DeepSORT Tracking" in full_rendered_text
    assert "Density & Motion" in full_rendered_text
    assert "Risk Assessment" in full_rendered_text
    assert "Dashboard & Alerts" in full_rendered_text

    # 5. Technology Stack (All 7 technologies)
    assert "YOLOv8" in full_rendered_text
    assert "DeepSORT" in full_rendered_text
    assert "MobileNetV2" in full_rendered_text
    assert "OpenCV" in full_rendered_text
    assert "Python" in full_rendered_text
    assert "Streamlit" in full_rendered_text
    assert "Firebase" in full_rendered_text

    # 6. Applications (All 4 sectors)
    assert "Public Gatherings" in full_rendered_text
    assert "Festivals & Concerts" in full_rendered_text
    assert "Stadiums & Arenas" in full_rendered_text
    assert "Transport Hubs" in full_rendered_text

    # 7. About Section
    assert "AMC Engineering College" in full_rendered_text
    assert "Final Year Major Project" in full_rendered_text
    assert "Privacy by Design" in full_rendered_text or "privacy" in full_rendered_text.lower()

    # 8. Footer Section
    assert "CrowdPatrol" in full_rendered_text
    assert "Department of Computer Science & Engineering" in full_rendered_text
    assert "Academic Prototype Notice" in full_rendered_text


def test_landing_page_launch_callback():
    """Verify launch callback is triggered when button is clicked."""
    launch_called = []

    def mock_launch():
        launch_called.append(True)

    def mock_button(label, **kwargs):
        if "hero_launch_dashboard_btn" in kwargs.get("key", ""):
            return True
        return False

    mock_columns = MagicMock()
    mock_columns.side_effect = lambda spec: [MagicMock() for _ in range(len(spec) if isinstance(spec, list) else spec)]

    with patch("streamlit.markdown"), \
         patch("streamlit.columns", side_effect=mock_columns), \
         patch("streamlit.button", side_effect=mock_button), \
         patch("streamlit.session_state", {}):

        render_landing_page(on_launch=mock_launch)

    assert len(launch_called) == 1, "Expected launch callback to be triggered on hero button click"


def test_apptest_initial_page_is_landing():
    """Verify Streamlit AppTest opens on the landing page first."""
    from streamlit.testing.v1 import AppTest
    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path).run(timeout=30)
    assert len(at.exception) == 0, f"App execution failed: {at.exception}"
    assert at.session_state["current_page"] == "landing"

    # Buttons rendered on landing page
    button_keys = [b.key for b in at.button if b.key]
    assert "hero_launch_dashboard_btn" in button_keys
    assert "nav_open_dashboard_btn" in button_keys
    assert "cta_launch_dashboard_btn" in button_keys
    assert "sidebar_landing_launch_btn" in button_keys


def test_apptest_navigation_cycle():
    """Verify complete bidirectional navigation cycle: Landing -> Dashboard -> Landing."""
    from streamlit.testing.v1 import AppTest
    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path).run(timeout=30)
    assert at.session_state["current_page"] == "landing"

    # Click Launch Dashboard
    at.button(key="hero_launch_dashboard_btn").click().run(timeout=30)
    assert len(at.exception) == 0, f"Exceptions on dashboard launch: {at.exception}"
    assert at.session_state["current_page"] == "dashboard"

    # Verify return button exists on dashboard
    dashboard_button_keys = [b.key for b in at.button if b.key]
    assert "sidebar_dashboard_return_btn" in dashboard_button_keys

    # Click Return to Landing Page
    at.button(key="sidebar_dashboard_return_btn").click().run(timeout=30)
    assert len(at.exception) == 0, f"Exceptions on returning to landing page: {at.exception}"
    assert at.session_state["current_page"] == "landing"


def test_apptest_query_param_deep_linking():
    """Verify ?page=dashboard deep-links directly to the monitoring dashboard."""
    from streamlit.testing.v1 import AppTest
    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "dashboard"
    at.run(timeout=30)
    assert len(at.exception) == 0, f"Exceptions on deep-link: {at.exception}"
    assert at.session_state["current_page"] == "dashboard"
    dashboard_button_keys = [b.key for b in at.button if b.key]
    assert "sidebar_dashboard_return_btn" in dashboard_button_keys
