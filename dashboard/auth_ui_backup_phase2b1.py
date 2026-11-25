"""
CrowdPatrol 2.0 — Secure Authentication UI Components
Provides styled login interface and minimal authenticated placeholder
using the CROWDPatrol 2.0 Nocturnal Design System.
"""

from typing import Optional, Callable
import streamlit as st

try:
    from dashboard.design_system import COLOR_TOKENS, inject_design_system
except ImportError:
    from design_system import COLOR_TOKENS, inject_design_system

from src.auth.service import AuthService
from src.auth.database import User


def render_login_view(
    auth_service: AuthService,
    on_success: Optional[Callable[[User, str], None]] = None,
    on_cancel: Optional[Callable[[], None]] = None,
    auth_message: Optional[str] = None
) -> None:
    """
    Renders the secure command access login view.
    """
    inject_design_system()
    c = COLOR_TOKENS

    st.markdown("""
    <div style="max-width: 520px; margin: 40px auto 16px auto; text-align: center;">
        <div style="width: 52px; height: 52px; margin: 0 auto 16px auto; background: linear-gradient(135deg, #2563EB 0%, #00D9FF 100%); border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: 0 0 24px rgba(0, 217, 255, 0.45);">
            🛡️
        </div>
        <h2 style="font-family: var(--cp-font-sans); font-size: 2.1rem; font-weight: 800; color: #EAF4FF; margin-bottom: 6px; letter-spacing: -0.02em;">
            CROWD<span style="color: #00D9FF;">PATROL</span>
        </h2>
        <div style="font-family: var(--cp-font-mono); font-size: 0.78rem; font-weight: 700; color: #00D9FF; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px;">
            RESTRICTED ACCESS &bull; COMMAND CENTER PORTAL
        </div>
        <p style="font-size: 0.92rem; color: #94A3B8; line-height: 1.5; margin: 0 auto 24px auto;">
            Enter your provisioned operator or administrative credentials to access situational crowd intelligence.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if auth_message:
        st.markdown(f"""
        <div style="max-width: 520px; margin: 0 auto 20px auto; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 10px; padding: 12px 16px; font-size: 0.88rem; color: #F59E0B; display: flex; align-items: center; gap: 10px;">
            <span>🔒</span>
            <div>{auth_message}</div>
        </div>
        """, unsafe_allow_html=True)

    # Login Form Container
    card_col1, card_col2, card_col3 = st.columns([1, 2, 1])
    with card_col2:
        with st.form("login_form", clear_on_submit=False):
            identity = st.text_input(
                "Username or Registered Email",
                key="login_identity_input",
                placeholder="e.g. operator or admin@crowdpatrol.internal"
            )
            password = st.text_input(
                "Password",
                type="password",
                key="login_password_input",
                placeholder="Enter password"
            )
            
            st.write("")
            submit = st.form_submit_button(
                "🔐 Sign In to Command Center",
                key="login_submit_btn",
                use_container_width=True,
                type="primary"
            )

        if submit:
            user, raw_token, error_msg = auth_service.authenticate(
                identity=identity,
                password=password
            )
            if error_msg:
                st.error(error_msg)
            elif user and raw_token:
                st.session_state["auth_token"] = raw_token
                st.session_state["auth_user"] = user
                st.session_state["current_page"] = "authenticated_home"
                st.query_params["page"] = "authenticated_home"
                if on_success:
                    on_success(user, raw_token)
                st.rerun()

        st.write("")
        if st.button("🏠 ← Return to Public Landing Page", key="login_cancel_btn", use_container_width=True):
            st.session_state["current_page"] = "landing"
            st.query_params["page"] = "landing"
            if on_cancel:
                on_cancel()
            st.rerun()


def render_authenticated_placeholder(
    user: User,
    auth_service: AuthService,
    on_logout: Optional[Callable[[], None]] = None
) -> None:
    """
    Renders the minimal authenticated page showing user account identity
    and logout option as specified for Phase 2A.
    Cameras and alerts are NOT connected yet.
    """
    inject_design_system()
    c = COLOR_TOKENS

    # Top Status Bar
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(8,15,32,0.85); border:1px solid rgba(0,217,255,0.25); border-radius:14px; padding:14px 24px; margin-bottom:28px;">
        <div style="display:flex; align-items:center; gap:12px;">
            <div style="font-size:22px;">🛡️</div>
            <div>
                <div style="font-family:var(--cp-font-sans); font-size:1.15rem; font-weight:800; color:#EAF4FF;">
                    CROWD<span style="color:#00D9FF;">PATROL</span> &bull; COMMAND CENTER
                </div>
                <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:#94A3B8;">
                    AUTHENTICATED OPERATOR SESSION &bull; ACTIVE
                </div>
            </div>
        </div>
        <div style="display:flex; align-items:center; gap:16px;">
            <div style="font-family:var(--cp-font-mono); font-size:0.78rem; color:#EAF4FF; background:rgba(37,99,235,0.2); border:1px solid rgba(59,130,246,0.3); padding:4px 12px; border-radius:6px;">
                ROLE: <strong style="color:#00D9FF;">{user.role}</strong>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Operator Identity Profile Card
    st.markdown(f"""
    <div style="background:rgba(16,27,48,0.75); border:1px solid rgba(59,130,246,0.22); border-radius:18px; padding:32px 36px; max-width:860px; margin:0 auto 32px auto; backdrop-filter:blur(14px);">
        <div style="display:flex; align-items:center; gap:16px; margin-bottom:24px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:20px;">
            <div style="width:56px; height:56px; border-radius:50%; background:linear-gradient(135deg, #2563EB, #00D9FF); display:flex; align-items:center; justify-content:center; font-size:26px; box-shadow:0 0 20px rgba(0,217,255,0.3);">
                👤
            </div>
            <div>
                <h3 style="font-family:var(--cp-font-sans); font-size:1.6rem; font-weight:800; color:#EAF4FF; margin:0 0 4px 0;">
                    {user.username}
                </h3>
                <div style="font-family:var(--cp-font-mono); font-size:0.82rem; color:#94A3B8;">
                    {user.email} &bull; ID: {user.id}
                </div>
            </div>
        </div>

        <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:16px; margin-bottom:28px;">
            <div style="background:rgba(8,15,32,0.8); border:1px solid rgba(59,130,246,0.18); border-radius:10px; padding:16px;">
                <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:#94A3B8; text-transform:uppercase; margin-bottom:4px;">Account Identity</div>
                <div style="font-size:1.05rem; font-weight:700; color:#EAF4FF;">{user.username}</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:2px;">Normalized system principal</div>
            </div>
            <div style="background:rgba(8,15,32,0.8); border:1px solid rgba(59,130,246,0.18); border-radius:10px; padding:16px;">
                <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:#94A3B8; text-transform:uppercase; margin-bottom:4px;">Assigned Role</div>
                <div style="font-size:1.05rem; font-weight:700; color:#00D9FF;">{user.role}</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:2px;">Role-Based Access Control</div>
            </div>
            <div style="background:rgba(8,15,32,0.8); border:1px solid rgba(59,130,246,0.18); border-radius:10px; padding:16px;">
                <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:#94A3B8; text-transform:uppercase; margin-bottom:4px;">Password Security</div>
                <div style="font-size:1.05rem; font-weight:700; color:#10B981;">Scrypt Hashed (RFC 7914)</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:2px;">N=16384, r=8, p=1, 512-bit key</div>
            </div>
            <div style="background:rgba(8,15,32,0.8); border:1px solid rgba(59,130,246,0.18); border-radius:10px; padding:16px;">
                <div style="font-family:var(--cp-font-mono); font-size:0.72rem; color:#94A3B8; text-transform:uppercase; margin-bottom:4px;">Session Security</div>
                <div style="font-size:1.05rem; font-weight:700; color:#00D9FF;">Zero-Knowledge Token</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:2px;">SHA-256 persistent database hash</div>
            </div>
        </div>

        <!-- Security Boundary Notice -->
        <div style="background:rgba(37,99,235,0.12); border:1px solid rgba(0,217,255,0.3); border-radius:12px; padding:20px; margin-bottom:28px;">
            <div style="font-family:var(--cp-font-mono); font-size:0.78rem; font-weight:700; color:#00D9FF; margin-bottom:8px; display:flex; align-items:center; gap:8px;">
                <span>🔒</span> PHASE 2A SECURITY FOUNDATION
            </div>
            <p style="font-size:0.88rem; line-height:1.6; color:#CBD5E1; margin:0;">
                Your authentication identity and session have been cryptographically validated against the persistent security ledger. 
                In compliance with the Phase 2A boundary specification, live surveillance camera feeds, multi-camera grid controls, 
                and automated emergency alert dispatchers remain disarmed until Phase 2B/Phase 3 multi-tenant organization authorization is established.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Logout Action Button
    b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
    with b_col2:
        if st.button("🔒 Sign Out / Revoke Session", key="auth_logout_btn", use_container_width=True, type="secondary"):
            token = st.session_state.get("auth_token")
            if token:
                auth_service.revoke_session(token)
            st.session_state.pop("auth_token", None)
            st.session_state.pop("auth_user", None)
            st.session_state["current_page"] = "landing"
            st.query_params["page"] = "landing"
            if on_logout:
                on_logout()
            st.rerun()
