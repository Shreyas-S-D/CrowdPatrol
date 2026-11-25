"""
CrowdPatrol 2.0 — Organization Workspace & Member Management UI
Provides styled multi-tenant organization selector, workspace administration,
member management, invitation workflows, and invitation acceptance views.
"""

from typing import Optional, Callable, Dict, Any, List
import streamlit as st
from datetime import datetime, timezone

try:
    from dashboard.design_system import COLOR_TOKENS, inject_design_system
except ImportError:
    from design_system import COLOR_TOKENS, inject_design_system

from src.auth.database import User, Organization, OrganizationMembership, OrganizationInvitation
from src.auth.service import AuthService
from src.auth.organization_service import (
    OrganizationService,
    MembershipService,
    resolve_tenant_context,
    is_platform_admin,
    can_manage_organization,
    can_manage_members,
    VALID_ORG_ROLES
)
from src.auth.invitation_service import InvitationService


def _role_badge_html(role: str) -> str:
    """Returns styled HTML badge for an organization role."""
    colors = {
        "PLATFORM_ADMIN": ("#8B5CF6", "rgba(139, 92, 246, 0.15)", "rgba(139, 92, 246, 0.4)"),
        "SUPER_ADMIN": ("#8B5CF6", "rgba(139, 92, 246, 0.15)", "rgba(139, 92, 246, 0.4)"),
        "ORG_ADMIN": ("#00D9FF", "rgba(0, 217, 255, 0.15)", "rgba(0, 217, 255, 0.4)"),
        "OPERATOR": ("#10B981", "rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.4)"),
        "VIEWER": ("#94A3B8", "rgba(148, 163, 184, 0.15)", "rgba(148, 163, 184, 0.4)")
    }
    fg, bg, border = colors.get(role.upper(), ("#94A3B8", "rgba(148, 163, 184, 0.15)", "rgba(148, 163, 184, 0.4)"))
    return (
        f'<span style="background:{bg}; color:{fg}; border:1px solid {border}; '
        f'padding:3px 8px; border-radius:5px; font-family:var(--cp-font-mono); '
        f'font-size:0.75rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase;">'
        f'{role}</span>'
    )


def _status_badge_html(status: str) -> str:
    """Returns styled HTML badge for organization or membership status."""
    colors = {
        "ACTIVE": ("#10B981", "rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.4)"),
        "SUSPENDED": ("#EF4444", "rgba(239, 68, 68, 0.15)", "rgba(239, 68, 68, 0.4)"),
        "ARCHIVED": ("#64748B", "rgba(100, 116, 139, 0.15)", "rgba(100, 116, 139, 0.4)"),
        "PENDING": ("#F59E0B", "rgba(245, 158, 11, 0.15)", "rgba(245, 158, 11, 0.4)"),
        "ACCEPTED": ("#10B981", "rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.4)"),
        "REVOKED": ("#DC2626", "rgba(220, 38, 38, 0.15)", "rgba(220, 38, 38, 0.4)"),
        "EXPIRED": ("#64748B", "rgba(100, 116, 139, 0.15)", "rgba(100, 116, 139, 0.4)")
    }
    fg, bg, border = colors.get(status.upper(), ("#94A3B8", "rgba(148, 163, 184, 0.15)", "rgba(148, 163, 184, 0.4)"))
    return (
        f'<span style="background:{bg}; color:{fg}; border:1px solid {border}; '
        f'padding:3px 8px; border-radius:5px; font-family:var(--cp-font-mono); '
        f'font-size:0.75rem; font-weight:700; text-transform:uppercase;">'
        f'{status}</span>'
    )


# =============================================================================
# 1. ORGANIZATION SELECTOR VIEW
# =============================================================================

def render_org_selector(
    user: User,
    org_service: OrganizationService,
    on_select_org: Callable[[Organization, OrganizationMembership], None],
    on_platform_admin: Optional[Callable[[], None]] = None,
    on_logout: Optional[Callable[[], None]] = None
) -> None:
    """
    Renders the organization selection interface displaying all accessible tenants.
    """
    inject_design_system()
    st.markdown("""
    <div style="margin-bottom: 24px;">
        <h2 style="color: #EAF4FF; font-family: var(--cp-font-sans); font-size: 1.8rem; font-weight: 800; margin-bottom: 4px;">
            🏢 Organization Workspaces
        </h2>
        <p style="color: #94A3B8; font-size: 0.92rem; margin: 0;">
            Select an authorized organization workspace to access surveillance intelligence, member management, and telemetry.
        </p>
    </div>
    """, unsafe_allow_html=True)

    accessible_orgs = org_service.list_accessible_organizations(user)
    is_p_admin = is_platform_admin(user)

    top_c1, top_c2 = st.columns([3, 1])
    with top_c1:
        st.caption(f"Authenticated as: **{user.username}** ({user.email}) &bull; Platform Role: `{user.role}`")
    with top_c2:
        if is_p_admin and on_platform_admin:
            if st.button("⚙️ Platform Admin Center", key="btn_go_platform_admin", use_container_width=True, type="secondary"):
                on_platform_admin()

    st.write("")

    if not accessible_orgs:
        # Empty state
        st.markdown("""
        <div style="background: rgba(16, 27, 48, 0.65); border: 1px dashed rgba(59, 130, 246, 0.3); border-radius: 12px; padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 38px; margin-bottom: 12px;">🏢</div>
            <h3 style="color: #EAF4FF; font-size: 1.25rem; font-weight: 700; margin-bottom: 8px;">No Accessible Organizations</h3>
            <p style="color: #94A3B8; font-size: 0.9rem; max-width: 480px; margin: 0 auto 20px auto; line-height: 1.5;">
                You currently do not hold an active membership in any organization. Please contact your organization administrator to request an official invitation.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Organization Grid Cards
        for org in accessible_orgs:
            # Query user membership
            mem = org_service.db.get_membership(org.id, user.id)
            user_role = mem.role if mem else ("PLATFORM_ADMIN" if is_p_admin else "UNKNOWN")

            with st.container():
                st.markdown(f"""
                <div style="background: rgba(16, 27, 48, 0.75); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.35);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <div>
                            <span style="font-size: 1.25rem; font-weight: 800; color: #FFFFFF; font-family: var(--cp-font-sans);">{org.name}</span>
                            <span style="margin-left: 10px; font-family: var(--cp-font-mono); font-size: 0.8rem; color: #64748B;">slug: {org.slug}</span>
                        </div>
                        <div>
                            {_status_badge_html(org.status)}
                            <span style="margin-left: 6px;">{_role_badge_html(user_role)}</span>
                        </div>
                    </div>
                    <p style="color: #94A3B8; font-size: 0.88rem; line-height: 1.4; margin: 0 0 14px 0;">
                        {org.description or 'Autonomous surveillance intelligence operational zone.'}
                    </p>
                </div>
                """, unsafe_allow_html=True)

                col_btn, col_space = st.columns([1, 4])
                with col_btn:
                    if org.status != "ACTIVE":
                        st.button(f"🚫 {org.status}", key=f"btn_enter_{org.id}", disabled=True, use_container_width=True)
                    else:
                        if st.button(f"🚀 Enter Workspace", key=f"btn_enter_{org.id}", use_container_width=True, type="primary"):
                            try:
                                resolved_org, resolved_mem = resolve_tenant_context(
                                    user=user,
                                    requested_org_id=org.id,
                                    db=org_service.db
                                )
                                on_select_org(resolved_org, resolved_mem)
                            except PermissionError as pe:
                                st.error(str(pe))

    st.write("")
    st.divider()
    if on_logout and st.button("🔒 Sign Out / Revoke Session", key="auth_logout_btn"):
        on_logout()


# =============================================================================
# 2. ORGANIZATION WORKSPACE & ADMINISTRATION VIEW
# =============================================================================

def render_org_workspace(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    org_service: OrganizationService,
    member_service: MembershipService,
    invitation_service: InvitationService,
    on_switch_org: Callable[[], None],
    on_logout: Callable[[], None]
) -> None:
    """
    Renders the active organization workspace view with member list,
    invitations tab, settings tab, and operational surveillance readiness notice.
    """
    inject_design_system()

    # Organization Header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(8, 15, 32, 0.95) 0%, rgba(16, 27, 48, 0.95) 100%); border: 1px solid rgba(0, 217, 255, 0.35); border-radius: 14px; padding: 22px 28px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div>
                <span style="font-family: var(--cp-font-mono); font-size: 0.75rem; color: #00D9FF; letter-spacing: 0.1em; text-transform: uppercase;">ORGANIZATION WORKSPACE</span>
                <h1 style="color: #FFFFFF; font-family: var(--cp-font-sans); font-size: 2.1rem; font-weight: 800; margin: 2px 0 4px 0; letter-spacing: -0.02em;">
                    {organization.name}
                </h1>
                <span style="color: #64748B; font-family: var(--cp-font-mono); font-size: 0.8rem;">ID: {organization.id} &bull; Slug: {organization.slug}</span>
            </div>
            <div style="text-align: right;">
                <div style="margin-bottom: 6px;">
                    {_status_badge_html(organization.status)}
                    <span style="margin-left: 6px;">{_role_badge_html(membership.role)}</span>
                </div>
                <div style="color: #94A3B8; font-size: 0.8rem;">
                    Active Operator: <strong style="color: #EAF4FF;">{user.username}</strong>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Operational Boundary Notice
    st.markdown("""
    <div style="background: rgba(37, 99, 235, 0.12); border: 1px solid rgba(0, 217, 255, 0.4); border-radius: 10px; padding: 14px 18px; margin-bottom: 22px; display: flex; align-items: center; gap: 14px;">
        <span style="font-size: 24px;">🛡️</span>
        <div>
            <div style="color: #00D9FF; font-family: var(--cp-font-mono); font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                Surveillance Isolation Boundary (Phase 2B Scope)
            </div>
            <div style="color: #94A3B8; font-size: 0.85rem; line-height: 1.4; margin-top: 2px;">
                Workspace membership and administrative controls are isolated. Physical camera partitions and tenant-scoped AI inference streams are scheduled for activation in Phase 2B.3. Global surveillance feeds remain separated.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Top Controls
    top_c1, top_c2, top_c3 = st.columns([2, 1, 1])
    with top_c2:
        if st.button("🔄 Switch Workspace", key="btn_switch_workspace", use_container_width=True):
            on_switch_org()
    with top_c3:
        if st.button("🔒 Sign Out", key="btn_workspace_logout", use_container_width=True):
            on_logout()

    can_manage = can_manage_members(user, organization, membership)

    if can_manage:
        tabs = st.tabs(["👥 Members", "✉️ Invitations", "⚙️ Organization Settings", "📋 Audit Log"])
        with tabs[0]:
            render_members_tab(user, organization, membership, member_service)
        with tabs[1]:
            render_invitations_tab(user, organization, invitation_service)
        with tabs[2]:
            render_settings_tab(user, organization, membership, org_service)
        with tabs[3]:
            render_audit_tab(organization, org_service)
    else:
        tabs = st.tabs(["👥 Members Directory", "ℹ️ Organization Details"])
        with tabs[0]:
            render_members_tab(user, organization, membership, member_service, read_only=True)
        with tabs[1]:
            st.write("")
            st.markdown(f"**Organization Name:** {organization.name}")
            st.markdown(f"**Slug:** `{organization.slug}`")
            st.markdown(f"**Description:** {organization.description or 'No description provided.'}")
            st.markdown(f"**Your Role:** `{membership.role}`")


# =============================================================================
# 3. MEMBERS TAB
# =============================================================================

def render_members_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    member_service: MembershipService,
    read_only: bool = False
) -> None:
    """Renders the members directory with role modification, suspension, and removal controls."""
    st.write("")
    members_data = member_service.list_organization_members(organization.id, actor=user)

    st.markdown(f"#### Active Roster ({len(members_data)} Members)")

    can_manage = not read_only and can_manage_members(user, organization, membership)

    for idx, item in enumerate(members_data):
        mem: OrganizationMembership = item["membership"]
        username = item["username"]
        email = item["email"]

        with st.container():
            col1, col2, col3 = st.columns([3, 2, 3])
            with col1:
                st.markdown(f"**{username}** (`{email}`)")
                st.caption(f"Joined: {mem.joined_at.strftime('%Y-%m-%d') if mem.joined_at else 'Pending'}")
            with col2:
                st.markdown(f"{_status_badge_html(mem.status)} {_role_badge_html(mem.role)}", unsafe_allow_html=True)
            with col3:
                if can_manage:
                    # Role selector and action buttons
                    action_c1, action_c2, action_c3 = st.columns([2, 1, 1])
                    with action_c1:
                        new_role = st.selectbox(
                            "Role",
                            options=VALID_ORG_ROLES,
                            index=VALID_ORG_ROLES.index(mem.role) if mem.role in VALID_ORG_ROLES else 0,
                            key=f"sel_role_{mem.id}",
                            label_visibility="collapsed"
                        )
                        if new_role != mem.role:
                            if st.button("Apply", key=f"apply_role_{mem.id}"):
                                try:
                                    member_service.change_member_role(
                                        org_id=organization.id,
                                        user_id=mem.user_id,
                                        new_role=new_role,
                                        actor=user
                                    )
                                    st.success(f"Role updated to {new_role}.")
                                    st.rerun()
                                except ValueError as ve:
                                    st.error(str(ve))

                    with action_c2:
                        if mem.status == "ACTIVE":
                            if st.button("⏸️", key=f"btn_susp_{mem.id}", help="Suspend Member"):
                                try:
                                    member_service.suspend_member(organization.id, mem.user_id, actor=user)
                                    st.success("Member suspended.")
                                    st.rerun()
                                except ValueError as ve:
                                    st.error(str(ve))
                        else:
                            if st.button("▶️", key=f"btn_react_{mem.id}", help="Reactivate Member"):
                                member_service.reactivate_member(organization.id, mem.user_id, actor=user)
                                st.success("Member reactivated.")
                                st.rerun()

                    with action_c3:
                        if st.button("🗑️", key=f"btn_rem_{mem.id}", help="Remove Member"):
                            try:
                                member_service.remove_member(organization.id, mem.user_id, actor=user)
                                st.success("Member removed.")
                                st.rerun()
                            except ValueError as ve:
                                st.error(str(ve))
            st.divider()


# =============================================================================
# 4. INVITATIONS TAB
# =============================================================================

def render_invitations_tab(
    user: User,
    organization: Organization,
    invitation_service: InvitationService
) -> None:
    """Renders the invitation creation form and list of pending invitations."""
    st.write("")

    with st.expander("➕ Issue New Member Invitation", expanded=False):
        with st.form("invite_form", clear_on_submit=True):
            st.markdown("##### Invite New Team Member")
            email_in = st.text_input("Recipient Email Address", placeholder="operator@precinct.internal")
            col_r, col_exp = st.columns(2)
            with col_r:
                role_in = st.selectbox("Assigned Role", options=["OPERATOR", "VIEWER", "ORG_ADMIN"])
            with col_exp:
                exp_in = st.selectbox("Invitation Validity", options=[24, 48, 72, 168], format_func=lambda h: f"{h} hours ({h//24} days)")

            send_email_chk = st.checkbox("Attempt SMTP email delivery", value=True)
            submit_inv = st.form_submit_button("🚀 Generate & Send Official Invitation", type="primary")

        if submit_inv:
            try:
                inv, raw_token, err = invitation_service.create_invitation(
                    actor=user,
                    organization_id=organization.id,
                    email=email_in,
                    role=role_in,
                    expires_in_hours=exp_in,
                    send_email=send_email_chk
                )
                st.success(f"Invitation successfully generated for **{inv.normalized_email}** as `{inv.invited_role}`!")

                invite_link = f"?page=accept_invite&token={raw_token}"
                st.info(f"📋 Invitation Link (Single-use token): `{invite_link}`")

                if err:
                    st.warning(f"SMTP delivery notice: {err}. Please share the link manually with the recipient.")
                else:
                    st.caption("✅ Invitation email queued for delivery via SMTP.")
            except Exception as e:
                st.error(f"Failed to issue invitation: {e}")

    st.write("")
    st.markdown("#### Pending & Recent Invitations")

    invitations = invitation_service.list_invitations(user, organization.id)
    if not invitations:
        st.info("No active invitations for this organization.")
        return

    for inv in invitations:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**{inv.normalized_email}**")
                st.caption(f"Expires: {inv.expires_at.strftime('%Y-%m-%d %H:%M UTC')}")
            with col2:
                st.markdown(f"{_status_badge_html(inv.status)} {_role_badge_html(inv.invited_role)}", unsafe_allow_html=True)
            with col3:
                if inv.status == "PENDING":
                    if st.button("🚫 Revoke", key=f"btn_revoke_{inv.id}"):
                        invitation_service.revoke_invitation(user, inv.id)
                        st.success("Invitation revoked.")
                        st.rerun()
            st.divider()


# =============================================================================
# 5. SETTINGS TAB
# =============================================================================

def render_settings_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    org_service: OrganizationService
) -> None:
    """Renders organization metadata editor for ORG_ADMINs."""
    st.write("")
    st.markdown("#### Organization Settings")

    with st.form("org_settings_form"):
        name_in = st.text_input("Organization Name", value=organization.name)
        desc_in = st.text_area("Description", value=organization.description or "")
        save_btn = st.form_submit_button("💾 Save Changes", type="primary")

    if save_btn:
        try:
            org_service.update_organization(
                org_id=organization.id,
                name=name_in,
                description=desc_in,
                actor=user
            )
            st.success("Organization settings successfully updated.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to update settings: {e}")


# =============================================================================
# 6. AUDIT LOG TAB
# =============================================================================

def render_audit_tab(organization: Organization, org_service: OrganizationService) -> None:
    """Renders recent administrative audit records for the organization."""
    st.write("")
    st.markdown("#### Non-Repudiable Administrative Audit Trail")
    events = org_service.db.list_audit_events(organization.id, limit=50)

    if not events:
        st.info("No audit events recorded yet.")
        return

    for ev in events:
        st.markdown(f"""
        <div style="background: rgba(16, 27, 48, 0.5); border-left: 3px solid #00D9FF; padding: 10px 14px; margin-bottom: 8px; border-radius: 0 8px 8px 0; font-family: var(--cp-font-mono); font-size: 0.8rem;">
            <span style="color: #00D9FF; font-weight: 700;">{ev.action}</span> &bull; 
            <span style="color: #94A3B8;">Target: {ev.target_type} ({ev.target_id})</span> &bull; 
            <span style="color: #64748B;">Actor: {ev.actor_user_id}</span><br>
            <span style="color: #CBD5E1; font-size: 0.75rem;">Metadata: {ev.metadata}</span> &bull; 
            <span style="color: #64748B; font-size: 0.72rem;">{ev.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# 7. PLATFORM ADMIN ORGANIZATION DIRECTORY
# =============================================================================

def render_platform_admin_orgs(
    user: User,
    org_service: OrganizationService,
    on_return: Callable[[], None]
) -> None:
    """Renders platform-wide organization administration for PLATFORM_ADMIN."""
    inject_design_system()
    st.markdown("""
    <div style="margin-bottom: 24px;">
        <span style="font-family: var(--cp-font-mono); font-size: 0.75rem; color: #8B5CF6; letter-spacing: 0.1em; text-transform: uppercase;">PLATFORM COMMAND CENTER</span>
        <h2 style="color: #EAF4FF; font-family: var(--cp-font-sans); font-size: 1.8rem; font-weight: 800; margin-bottom: 4px;">
            Platform Organization Administration
        </h2>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Return to Organization Workspaces", key="btn_return_from_admin"):
        on_return()

    st.write("")

    # Create New Organization Section
    with st.expander("➕ Provision New Organization", expanded=False):
        with st.form("create_org_form", clear_on_submit=True):
            new_org_name = st.text_input("Organization Name", placeholder="e.g. Harbor Security Division")
            new_org_slug = st.text_input("Custom Slug (Optional)", placeholder="harbor-security")
            new_org_desc = st.text_area("Description", placeholder="Primary waterside operational surveillance zone.")
            create_submit = st.form_submit_button("🚀 Provision Organization", type="primary")

        if create_submit:
            try:
                created = org_service.create_organization(
                    name=new_org_name,
                    slug=new_org_slug or None,
                    description=new_org_desc or None,
                    actor=user,
                    initial_admin_user_id=user.id
                )
                st.success(f"Organization **{created.name}** (slug: `{created.slug}`) successfully provisioned!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to create organization: {e}")

    st.write("")
    st.markdown("#### Global Organization Directory")
    all_orgs = org_service.db.list_all_organizations()

    for org in all_orgs:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 3])
            with col1:
                st.markdown(f"**{org.name}** (`{org.slug}`)")
                st.caption(f"Created: {org.created_at.strftime('%Y-%m-%d')}")
            with col2:
                st.markdown(_status_badge_html(org.status), unsafe_allow_html=True)
            with col3:
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if org.status == "ACTIVE":
                        if st.button("Suspend", key=f"p_susp_{org.id}"):
                            org_service.suspend_organization(org.id, actor=user)
                            st.rerun()
                    elif org.status == "SUSPENDED":
                        if st.button("Reactivate", key=f"p_react_{org.id}"):
                            org_service.reactivate_organization(org.id, actor=user)
                            st.rerun()
                with btn_c2:
                    if org.status != "ARCHIVED":
                        if st.button("Archive", key=f"p_arch_{org.id}"):
                            org_service.archive_organization(org.id, actor=user)
                            st.rerun()
            st.divider()


# =============================================================================
# 8. INVITATION ACCEPTANCE VIEW
# =============================================================================

def render_invitation_acceptance_view(
    invitation_service: InvitationService,
    auth_service: AuthService,
    raw_token: str,
    on_success: Callable[[Organization], None],
    on_cancel: Callable[[], None]
) -> None:
    """
    Renders the public/operator invitation acceptance interface.
    Validates the token and allows an existing user to join or a new user to register.
    """
    inject_design_system()

    invitation, org, err = invitation_service.validate_invitation_token(raw_token)

    st.markdown("""
    <div style="max-width: 520px; margin: 30px auto 16px auto; text-align: center;">
        <div style="font-size: 38px; margin-bottom: 12px;">🛡️</div>
        <h2 style="font-family: var(--cp-font-sans); font-size: 2rem; font-weight: 800; color: #EAF4FF; margin-bottom: 6px;">
            CrowdPatrol Command Invitation
        </h2>
    </div>
    """, unsafe_allow_html=True)

    if err or not invitation or not org:
        st.session_state.pop("invitation_token", None)
        st.markdown(f"""
        <div style="max-width: 520px; margin: 0 auto; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 24px; text-align: center;">
            <div style="font-size: 28px; margin-bottom: 8px;">🚫</div>
            <h4 style="color: #EF4444; margin: 0 0 8px 0;">Invitation Unavailable</h4>
            <p style="color: #94A3B8; font-size: 0.9rem; margin: 0 0 16px 0;">{err}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
        with col_c2:
            if st.button("🏠 Return to Landing Page", use_container_width=True):
                on_cancel()
        return

    # Valid Invitation Details Box
    st.markdown(f"""
    <div style="max-width: 520px; margin: 0 auto 24px auto; background: rgba(16, 27, 48, 0.75); border: 1px solid rgba(0, 217, 255, 0.35); border-radius: 12px; padding: 24px; text-align: center;">
        <span style="font-family: var(--cp-font-mono); font-size: 0.75rem; color: #00D9FF; text-transform: uppercase;">OFFICIAL INVITATION</span>
        <h3 style="color: #FFFFFF; font-size: 1.5rem; font-weight: 800; margin: 4px 0 12px 0;">{org.name}</h3>
        <div style="margin-bottom: 12px;">
            {_role_badge_html(invitation.invited_role)}
        </div>
        <div style="color: #94A3B8; font-size: 0.85rem;">
            Invited Recipient: <strong style="color: #EAF4FF;">{invitation.normalized_email}</strong><br>
            Valid until: <span style="color: #CBD5E1;">{invitation.expires_at.strftime('%Y-%m-%d %H:%M UTC')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    current_user = st.session_state.get("auth_user")

    card_c1, card_c2, card_c3 = st.columns([1, 2, 1])
    with card_c2:
        if current_user:
            # Logged-in user flow
            if current_user.email.lower() == invitation.normalized_email:
                st.markdown(f"Signed in as: **{current_user.username}** (`{current_user.email}`)")
                if st.button("✅ Accept Invitation & Enter Workspace", type="primary", use_container_width=True):
                    success, mem, accept_err = invitation_service.accept_invitation(
                        raw_token=raw_token,
                        user=current_user
                    )
                    if success:
                        st.success(f"Welcome to {org.name}! Your {invitation.invited_role} membership is active.")
                        on_success(org)
                    else:
                        st.error(accept_err)
            else:
                st.warning(
                    f"You are currently signed in as **{current_user.email}**, but this invitation was sent to **{invitation.normalized_email}**."
                )
                if st.button("Sign Out of Current Account", use_container_width=True):
                    st.session_state.pop("auth_user", None)
                    st.session_state.pop("auth_token", None)
                    st.rerun()
        else:
            # Unauthenticated flow: check if account exists
            existing_user = auth_service.db.get_user_by_identity(invitation.normalized_email)
            if existing_user:
                st.info(f"An existing account for **{invitation.normalized_email}** was detected. Please enter your password to accept.")
                with st.form("accept_existing_login_form"):
                    pw_in = st.text_input("Password", type="password")
                    sub_login = st.form_submit_button("🔐 Sign In & Accept Invitation", type="primary", use_container_width=True)

                if sub_login:
                    user, token, login_err = auth_service.authenticate(existing_user.username, pw_in)
                    if login_err:
                        st.error(login_err)
                    elif user:
                        st.session_state["auth_user"] = user
                        st.session_state["auth_token"] = token
                        success, mem, accept_err = invitation_service.accept_invitation(raw_token=raw_token, user=user)
                        if success:
                            st.success(f"Welcome to {org.name}!")
                            on_success(org)
                        else:
                            st.error(accept_err)
            else:
                st.markdown("##### Create Operator Account & Accept")
                with st.form("accept_register_form"):
                    reg_user = st.text_input("Choose Username", placeholder="e.g. operator_smith")
                    reg_pass1 = st.text_input("Choose Strong Password", type="password")
                    reg_pass2 = st.text_input("Confirm Password", type="password")
                    sub_reg = st.form_submit_button("🛡️ Create Account & Accept Invitation", type="primary", use_container_width=True)

                if sub_reg:
                    if reg_pass1 != reg_pass2:
                        st.error("Passwords do not match.")
                    else:
                        success, mem, accept_err = invitation_service.accept_invitation(
                            raw_token=raw_token,
                            new_user_credentials={"username": reg_user, "password": reg_pass1}
                        )
                        if success:
                            # Log user in
                            new_user, new_token, _ = auth_service.authenticate(reg_user, reg_pass1)
                            st.session_state["auth_user"] = new_user
                            st.session_state["auth_token"] = new_token
                            st.success(f"Account created! Welcome to {org.name}.")
                            on_success(org)
                        else:
                            st.error(accept_err)

        st.write("")
        if st.button("Cancel & Return to Public Home", use_container_width=True):
            on_cancel()
