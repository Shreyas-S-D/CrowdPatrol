"""
CrowdPatrol Dashboard
Streamlit-based web interface for live monitoring, alert history, and analytics.
"""

from .app import DashboardApp, AlertDashboard, AnalyticsDashboard

__all__ = [
    "DashboardApp",
    "AlertDashboard",
    "AnalyticsDashboard"
]