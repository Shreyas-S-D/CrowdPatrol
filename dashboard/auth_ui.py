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
    auth_message: Optional[str] = None,
    invitation_service: Optional[Any] = None
) -> None:
    """
    Renders the secure command access authentication view with two accessible options:
    - Login: Sign in for existing provisioned users.
    - Create Account: Invitation-gated account creation & organization joining.
    """
    inject_design_system()
    c = COLOR_TOKENS

    if invitation_service is None:
        try:
            from src.auth.invitation_service import InvitationService
            invitation_service = InvitationService(auth_service.db, auth_service)
        except Exception:
            pass

    st.markdown("""
    <div style="max-width: 540px; margin: 36px auto 16px auto; text-align: center;">
        <div style="width: 52px; height: 52px; margin: 0 auto 16px auto; background: linear-gradient(135deg, #2563EB 0%, #00D9FF 100%); border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: 0 0 24px rgba(0, 217, 255, 0.45);">
            🛡️
        </div>
        <h2 style="font-family: var(--cp-font-sans); font-size: 2.1rem; font-weight: 800; color: #EAF4FF; margin-bottom: 6px; letter-spacing: -0.02em;">
            CROWD<span style="color: #00D9FF;">PATROL</span>
        </h2>
        <div style="font-family: var(--cp-font-mono); font-size: 0.78rem; font-weight: 700; color: #00D9FF; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px;">
            RESTRICTED ACCESS &bull; COMMAND CENTER PORTAL
        </div>
        <p style="font-size: 0.92rem; color: #94A3B8; line-height: 1.5; margin: 0 auto 20px auto;">
            Enter your credentials to access situational crowd intelligence, or activate an official organization invitation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if auth_message:
        st.markdown(f"""
        <div style="max-width: 540px; margin: 0 auto 20px auto; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 10px; padding: 12px 16px; font-size: 0.88rem; color: #F59E0B; display: flex; align-items: center; gap: 10px;">
            <span>🔒</span>
            <div>{auth_message}</div>
        </div>
        """, unsafe_allow_html=True)

    # Auth Container with Accessible Tabs
    card_col1, card_col2, card_col3 = st.columns([1, 2, 1])
    with card_col2:
        auth_tabs = st.tabs(["🔐 Sign In", "📝 Create Account"])

        # TAB 1: LOGIN
        with auth_tabs[0]:
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

        # TAB 2: CREATE ACCOUNT (INVITATION GATED)
        with auth_tabs[1]:
            candidate_token = st.session_state.get("invitation_token") or st.query_params.get("token", "")

            # If no invitation token is available, explain requirement and prompt for token
            if not candidate_token:
                st.markdown("""
                <div style="background: rgba(37, 99, 235, 0.12); border: 1px solid rgba(0, 217, 255, 0.3); border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                    <div style="font-family: var(--cp-font-mono); font-size: 0.8rem; font-weight: 700; color: #00D9FF; margin-bottom: 6px;">
                        🔒 INVITATION REQUIRED FOR REGISTRATION
                    </div>
                    <p style="font-size: 0.88rem; color: #CBD5E1; margin: 0; line-height: 1.5;">
                        CrowdPatrol 2.0 operates with restricted access and strict tenant isolation. Unrestricted public registration is disabled.
                        To create an account, you must possess an official invitation token issued by an authorized Organization Administrator.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                with st.form("enter_invite_token_form"):
                    token_in = st.text_input(
                        "Invitation Token",
                        placeholder="Paste the 32-character token from your invitation",
                        key="create_acct_token_input",
                        help="Enter the security token provided by your organization administrator"
                    )
                    submit_token = st.form_submit_button(
                        "🔍 Verify Invitation & Proceed",
                        type="primary",
                        use_container_width=True
                    )

                if submit_token:
                    if not token_in or len(token_in.strip()) < 16:
                        st.error("Please enter a valid invitation token (at least 16 characters).")
                    else:
                        st.session_state["invitation_token"] = token_in.strip()
                        st.rerun()

                st.write("")
                st.caption("Already registered or don't have an invitation?")
                if st.button("← Return to Sign In", key="create_no_token_back_login_btn", use_container_width=True):
                    st.session_state.pop("invitation_token", None)
                    st.rerun()

            else:
                # Validate Candidate Invitation Token
                if invitation_service is None:
                    st.error("Invitation verification service is currently unavailable.")
                else:
                    invitation, org, val_err = invitation_service.validate_invitation_token(candidate_token)

                    if val_err or not invitation or not org:
                        st.markdown(f"""
                        <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 10px; padding: 16px; margin-bottom: 16px; text-align: center;">
                            <div style="font-size: 24px; margin-bottom: 6px;">🚫</div>
                            <div style="font-weight: 700; color: #EF4444; margin-bottom: 4px;">Invitation Verification Failed</div>
                            <p style="font-size: 0.86rem; color: #CBD5E1; margin: 0;">{val_err}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        col_rst1, col_rst2 = st.columns(2)
                        with col_rst1:
                            if st.button("🔄 Try Another Token", key="retry_invite_token_btn", use_container_width=True):
                                st.session_state.pop("invitation_token", None)
                                st.rerun()
                        with col_rst2:
                            if st.button("← Return to Sign In", key="invalid_invite_to_login_btn", use_container_width=True):
                                st.session_state.pop("invitation_token", None)
                                st.rerun()
                    else:
                        # Valid Invitation Details Box
                        st.markdown(f"""
                        <div style="background: rgba(16, 27, 48, 0.85); border: 1px solid rgba(0, 217, 255, 0.35); border-radius: 10px; padding: 16px; margin-bottom: 18px; text-align: center;">
                            <div style="font-family: var(--cp-font-mono); font-size: 0.72rem; color: #00D9FF; text-transform: uppercase;">
                                OFFICIAL INVITATION VERIFIED
                            </div>
                            <div style="font-size: 1.25rem; font-weight: 800; color: #FFFFFF; margin: 4px 0;">
                                {org.name}
                            </div>
                            <div style="font-size: 0.82rem; color: #94A3B8; margin-top: 4px;">
                                Role: <strong style="color: #00D9FF;">{invitation.invited_role}</strong> &bull; Recipient: <strong style="color: #EAF4FF;">{invitation.normalized_email}</strong><br>
                                <span style="font-size: 0.75rem; color: #64748B;">Expires: {invitation.expires_at.strftime('%Y-%m-%d %H:%M UTC')}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        existing_user = auth_service.db.get_user_by_identity(invitation.normalized_email)

                        if existing_user:
                            # Flow A: Existing user joins additional organization
                            st.info(f"An existing account for **{invitation.normalized_email}** was detected. Enter your password to join **{org.name}** as **{invitation.invited_role}** without creating a duplicate account.")
                            with st.form("accept_existing_in_tab_form"):
                                existing_pw = st.text_input("Password", type="password", key="tab_existing_pw_in")
                                submit_join = st.form_submit_button("🔐 Accept Invitation & Join Organization", type="primary", use_container_width=True)

                            if submit_join:
                                u, tok, l_err = auth_service.authenticate(existing_user.username, existing_pw)
                                if l_err:
                                    st.error(l_err)
                                elif u:
                                    success, mem, a_err = invitation_service.accept_invitation(candidate_token, user=u)
                                    if success:
                                        st.session_state["auth_user"] = u
                                        st.session_state["auth_token"] = tok
                                        st.session_state["active_org"] = org
                                        st.session_state["active_membership"] = mem
                                        st.session_state["current_page"] = "authenticated_home"
                                        st.session_state.pop("invitation_token", None)
                                        st.success(f"Welcome to {org.name}! Your {invitation.invited_role} role is active.")
                                        if on_success:
                                            on_success(u, tok)
                                        st.rerun()
                                    else:
                                        st.error(a_err)
                        else:
                            # Flow B: New user account creation
                            st.markdown(f"Create your operator credentials to join **{org.name}** as **{invitation.invited_role}**.")
                            with st.form("tab_create_account_form"):
                                new_full_name = st.text_input("Full Name (Optional)", placeholder="e.g. Jane Doe", key="tab_reg_fullname")
                                new_username = st.text_input("Choose Username", placeholder="e.g. operator_smith", key="tab_reg_user")
                                st.text_input("Authorized Email", value=invitation.normalized_email, disabled=True, key="tab_reg_email_locked", help="Locked to the verified invitation email")
                                new_pass1 = st.text_input("Choose Strong Password", type="password", placeholder="At least 8 characters", key="tab_reg_pass1")
                                new_pass2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="tab_reg_pass2")
                                submit_create = st.form_submit_button("🛡️ Create Account & Accept Invitation", type="primary", use_container_width=True)

                            if submit_create:
                                if not new_username or len(new_username.strip()) < 3:
                                    st.error("Username must be between 3 and 32 characters.")
                                elif not new_pass1 or len(new_pass1) < 8:
                                    st.error("Password must be at least 8 characters long.")
                                elif new_pass1 != new_pass2:
                                    st.error("Passwords do not match.")
                                else:
                                    success, mem, a_err = invitation_service.accept_invitation(
                                        raw_token=candidate_token,
                                        new_user_credentials={"username": new_username.strip(), "password": new_pass1}
                                    )
                                    if success:
                                        new_user, new_tok, _ = auth_service.authenticate(new_username.strip(), new_pass1)
                                        st.session_state["auth_user"] = new_user
                                        st.session_state["auth_token"] = new_tok
                                        st.session_state["active_org"] = org
                                        st.session_state["active_membership"] = mem
                                        st.session_state["current_page"] = "authenticated_home"
                                        st.session_state.pop("invitation_token", None)
                                        st.success(f"Account created! Welcome to {org.name}.")
                                        if on_success:
                                            on_success(new_user, new_tok)
                                        st.rerun()
                                    else:
                                        st.error(a_err)

                        st.write("")
                        col_can1, col_can2 = st.columns(2)
                        with col_can1:
                            if st.button("🔄 Clear Invitation Token", key="clear_invite_token_btn", use_container_width=True):
                                st.session_state.pop("invitation_token", None)
                                st.rerun()
                        with col_can2:
                            if st.button("← Return to Sign In", key="invite_view_return_login_btn", use_container_width=True):
                                st.session_state.pop("invitation_token", None)
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
