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
from src.auth.tenant_operational_service import TenantOperationalService

try:
    from src.multi_camera_manager import MultiCameraManager
except ImportError:
    MultiCameraManager = None


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
    on_logout: Callable[[], None],
    tenant_op_service: Optional[TenantOperationalService] = None
) -> None:
    """
    Renders the active organization workspace view with operational multi-camera surveillance,
    slot configuration, alert management, analytics, asset uploads, notification routing,
    team roster, and non-repudiable audit trails.
    """
    inject_design_system()
    op_service = tenant_op_service or TenantOperationalService(org_service.db)

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
    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 14px 18px; margin-bottom: 22px; display: flex; align-items: center; gap: 14px;">
        <span style="font-size: 24px;">🛡️</span>
        <div>
            <div style="color: #10B981; font-family: var(--cp-font-mono); font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                Surveillance Isolation Boundary Active (Phase 2B.3)
            </div>
            <div style="color: #94A3B8; font-size: 0.85rem; line-height: 1.4; margin-top: 2px;">
                Camera slot configurations, surveillance sessions, alerts, uploaded video assets, and notifications are strictly isolated to this organization workspace. Global surveillance feeds remain separated.
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

    tabs = st.tabs([
        "📹 CCTV Monitoring",
        "⚙️ Camera Slots",
        "🚨 Alerts Center",
        "📊 Analytics & Trends",
        "📁 Video Uploads & Sessions",
        "🔔 Notifications",
        "👥 Team Roster",
        "📋 Audit Trail"
    ])

    with tabs[0]:
        render_tenant_cctv_tab(user, organization, membership, op_service)
    with tabs[1]:
        render_tenant_cameras_tab(user, organization, membership, op_service)
    with tabs[2]:
        render_tenant_alerts_tab(user, organization, membership, op_service)
    with tabs[3]:
        render_tenant_analytics_tab(user, organization, membership, op_service)
    with tabs[4]:
        render_tenant_assets_tab(user, organization, membership, op_service)
    with tabs[5]:
        render_tenant_notifications_tab(user, organization, membership, op_service)
    with tabs[6]:
        if can_manage:
            render_members_tab(user, organization, membership, member_service)
            st.divider()
            render_invitations_tab(user, organization, invitation_service)
        else:
            render_members_tab(user, organization, membership, member_service, read_only=True)
    with tabs[7]:
        render_audit_tab(organization, org_service)


# =============================================================================
# 2A. TENANT CCTV MONITORING TAB
# =============================================================================

def render_tenant_cctv_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    tenant_op_service: TenantOperationalService
) -> None:
    """Renders the 4-slot CCTV live monitoring grid and start/stop surveillance controls."""
    st.write("")
    is_viewer = membership.role == "VIEWER" and not is_platform_admin(user)
    active_sess = tenant_op_service.get_active_session(actor=user, organization_id=organization.id)
    configs = tenant_op_service.get_camera_configs(actor=user, organization_id=organization.id)

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])
    with ctrl_col1:
        if active_sess:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 8px; padding: 10px 16px;">
                <span style="color: #10B981; font-weight: 800; font-family: var(--cp-font-mono);">🟢 SURVEILLANCE ACTIVE</span>
                <span style="color: #94A3B8; font-size: 0.85rem; margin-left: 10px;">Session: <code>{active_sess.id}</code></span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(148, 163, 184, 0.1); border: 1px solid #64748B; border-radius: 8px; padding: 10px 16px;">
                <span style="color: #94A3B8; font-weight: 800; font-family: var(--cp-font-mono);">⚪ SURVEILLANCE STANDBY</span>
                <span style="color: #64748B; font-size: 0.85rem; margin-left: 10px;">4 Camera Slots Configured</span>
            </div>
            """, unsafe_allow_html=True)

    with ctrl_col3:
        if is_viewer:
            st.button("🔒 Start Monitoring (Viewer)", disabled=True, key=f"btn_viewer_start_{organization.id}", help="Viewer role is read-only")
        else:
            if not active_sess:
                if st.button("▶️ Start Monitoring", key=f"btn_start_sess_{organization.id}", type="primary", use_container_width=True):
                    try:
                        sess, res = tenant_op_service.start_monitoring_session(actor=user, organization_id=organization.id)
                        issues = res.get("device_issues", [])
                        if issues:
                            for iss in issues:
                                st.warning(f"⚠️ {iss['slot_id']}: {iss['message']}")
                        st.success(f"Monitoring session started for {organization.name}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to start monitoring: {e}")
            else:
                if st.button("⏹️ Stop Monitoring", key=f"btn_stop_sess_{organization.id}", use_container_width=True):
                    try:
                        mc_key = f"tenant_multi_cam_{organization.id}"
                        old_mc = st.session_state.pop(mc_key, None)
                        if old_mc:
                            try:
                                old_mc.stop_all_cameras()
                            except Exception:
                                pass
                        tenant_op_service.stop_monitoring_session(actor=user, organization_id=organization.id, session_id=active_sess.id)
                        st.info("Monitoring session terminated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to stop monitoring: {e}")

    if is_viewer:
        st.markdown("""
        <div style="color: #94A3B8; font-size: 0.82rem; margin: 8px 0;">
            👀 <em>Viewer Role: You have read-only access to monitoring telemetry and alerts. Camera controls and configuration are restricted to Operators and Administrators.</em>
        </div>
        """, unsafe_allow_html=True)

    # MultiCameraManager integration for active sessions
    mc = None
    mc_key = f"tenant_multi_cam_{organization.id}"
    if active_sess and MultiCameraManager is not None:
        mc = st.session_state.get(mc_key)
        if mc is None:
            try:
                det_mode = st.session_state.get(f"det_mode_val_{organization.id}", "PERSON")
                mc = MultiCameraManager(
                    camera_configs=configs,
                    detection_mode=det_mode,
                    device="cpu",
                    detect_interval=3,
                    organization_id=organization.id,
                    session_id=active_sess.id,
                    tenant_op_service=tenant_op_service
                )
                try:
                    notif_disp = tenant_op_service.get_notification_dispatcher(actor=user, organization_id=organization.id, autostart=True)
                    mc.attach_notification_dispatcher(notif_disp)
                except Exception:
                    pass
                mc.start_all_cameras()
                st.session_state[mc_key] = mc
            except Exception as e_mc:
                st.warning(f"Surveillance initialization note: {e_mc}")

    st.write("")
    st.markdown("#### Operational Camera Grid")

    # If surveillance is active, provide view mode selector and frame stepping
    is_focus_mode = False
    focus_slot_id = None
    if active_sess and mc is not None:
        bar_col1, bar_col2, bar_col3 = st.columns([2, 1, 1])
        with bar_col1:
            display_opts = [
                "🎛️ 2x2 CCTV Grid (All Feeds)",
                "🔍 Focus Feed: CAM-01",
                "🔍 Focus Feed: CAM-02",
                "🔍 Focus Feed: CAM-03",
                "🔍 Focus Feed: CAM-04"
            ]
            selected_display = st.radio(
                "📺 Display Mode:",
                display_opts,
                horizontal=True,
                key=f"cctv_view_mode_{organization.id}"
            )
            is_focus_mode = "Focus Feed" in selected_display
            if is_focus_mode:
                focus_slot_id = selected_display.split(":")[1].strip()

        with bar_col2:
            mode_options = ["👤 Person Mode", "🗣️ Head Mode"]
            curr_idx = 1 if mc.detection_mode == "HEAD" else 0
            sel_mode = st.selectbox(
                "Detection Mode:",
                mode_options,
                index=curr_idx,
                key=f"cctv_det_mode_{organization.id}",
                disabled=is_viewer
            )
            target_mode = "HEAD" if "Head" in sel_mode else "PERSON"
            if target_mode != mc.detection_mode:
                mc.set_detection_mode(target_mode)
                st.session_state[f"det_mode_val_{organization.id}"] = target_mode
                st.rerun()

        with bar_col3:
            st.write("")
            step_clicked = st.button("⏩ Step Feeds", key=f"btn_step_feeds_{organization.id}", use_container_width=True)

        # Trigger frame processing when stepped or on initial frame render
        if step_clicked or not any(c.annotated_frame is not None for c in mc.cameras.values()):
            try:
                if is_focus_mode and focus_slot_id:
                    mc.step_focus(focus_slot_id, step_background=True)
                else:
                    mc.step_all()
            except Exception:
                pass

    # Retrieve active alerts for inline alert badges
    active_tenant_alerts = tenant_op_service.list_alerts(actor=user, organization_id=organization.id, status="ACTIVE")
    active_alerts_by_cam = {a.camera_id: a for a in active_tenant_alerts}

    # Render Focus Mode
    if is_focus_mode and focus_slot_id and mc and focus_slot_id in mc.cameras:
        f_cam = mc.cameras[focus_slot_id]
        st.markdown(f"### 🔍 Detailed Inspection Feed: `{f_cam.id}` ({f_cam.name})")

        f_status = f_cam.status
        f_status_color = "#10B981" if f_status in ("ONLINE", "STREAMING") else ("#EF4444" if f_status == "DEVICE_IN_USE" else "#64748B")

        if f_status == "DEVICE_IN_USE":
            st.warning(f"⚠️ **DEVICE IN USE**: {f_cam.error_message}")

        if f_cam.annotated_frame is not None:
            st.image(f_cam.annotated_frame, channels="BGR", use_container_width=True)
        else:
            st.markdown(f"""
            <div style="background: #0B1120; border-radius: 8px; height: 320px; display: flex; flex-direction: column; justify-content: center; align-items: center; border: 1px dashed rgba(255,255,255,0.15);">
                <span style="font-size: 48px;">📹</span>
                <span style="color: #64748B; font-size: 0.95rem; margin-top: 10px;">
                    Focus Feed Active — Click 'Step Feeds' to refresh frame.
                </span>
            </div>
            """, unsafe_allow_html=True)

        # Telemetry Metrics Bar
        m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
        with m_c1:
            st.metric("Persons / Heads", f_cam.visible_count)
        with m_c2:
            st.metric("Peak Density", f"{f_cam.max_density} p/cell")
        with m_c3:
            st.metric("Motion Speed", f"{f_cam.avg_speed:.1f} px/f")
        with m_c4:
            st.metric("Risk Score", f"{f_cam.risk_score:.1f}/100")
        with m_c5:
            st.metric("Risk Level", f_cam.risk_level)

        if focus_slot_id in active_alerts_by_cam:
            alt = active_alerts_by_cam[focus_slot_id]
            st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 12px 18px; margin: 12px 0;">
                <span style="color: #EF4444; font-weight: 800; font-family: var(--cp-font-mono);">🚨 ACTIVE ALERT:</span>
                <span style="color: #FFFFFF; font-weight: 600; margin-left: 8px;">{alt.reason}</span>
                <span style="color: #F87171; margin-left: 10px;">({alt.severity}) &bull; Risk Score: {alt.risk_score:.1f}</span>
            </div>
            """, unsafe_allow_html=True)
            if not is_viewer:
                btn_c1, btn_c2, _ = st.columns([1, 1, 3])
                with btn_c1:
                    if st.button("🔔 Acknowledge", key=f"f_ack_{alt.id}_{organization.id}"):
                        tenant_op_service.acknowledge_alert(actor=user, organization_id=organization.id, alert_id=alt.id)
                        st.rerun()
                with btn_c2:
                    if st.button("✅ Resolve", key=f"f_res_{alt.id}_{organization.id}"):
                        tenant_op_service.resolve_alert(actor=user, organization_id=organization.id, alert_id=alt.id, note="Resolved in Focus view")
                        st.rerun()
        return

    # Render 2x2 Grid Mode (or Standby Mode)
    c_grid1, c_grid2 = st.columns(2)
    grid_cols = [c_grid1, c_grid2, c_grid1, c_grid2]

    for idx, cam in enumerate(configs):
        with grid_cols[idx]:
            is_enabled = cam.enabled
            cam_obj = mc.cameras.get(cam.slot_id) if (mc and cam.slot_id in mc.cameras) else None
            runtime_status = cam_obj.status if cam_obj else ("DISABLED" if not is_enabled else ("STREAMING" if active_sess else "STANDBY"))

            if runtime_status == "DEVICE_IN_USE":
                status_color = "#EF4444"
                status_text = "DEVICE_IN_USE"
            elif runtime_status in ("ONLINE", "STREAMING"):
                status_color = "#10B981"
                status_text = "STREAMING" if active_sess else "ONLINE"
            elif not is_enabled:
                status_color = "#64748B"
                status_text = "DISABLED"
            else:
                status_color = "#00D9FF"
                status_text = "STANDBY"

            st.markdown(f"""
            <div style="background: rgba(16, 27, 48, 0.7); border: 1px solid rgba(0, 217, 255, 0.3); border-radius: 10px; padding: 14px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-family: var(--cp-font-mono); font-weight: 700; color: #FFFFFF; font-size: 0.95rem;">
                        {cam.slot_id}: {cam.name}
                    </span>
                    <span style="color: {status_color}; font-family: var(--cp-font-mono); font-size: 0.75rem; font-weight: 700; border: 1px solid {status_color}; padding: 2px 6px; border-radius: 4px;">
                        {status_text}
                    </span>
                </div>
                <div style="color: #94A3B8; font-size: 0.8rem; margin-bottom: 8px;">
                    Type: <code style="color: #00D9FF;">{cam.source_type.upper()}</code> &bull; 
                    Target: <span style="color: #CBD5E1;">{cam.source or 'None'}</span> &bull; 
                    Mode: <span style="color: #A78BFA;">{cam.detection_mode}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if runtime_status == "DEVICE_IN_USE" and cam_obj:
                st.warning(f"⚠️ **Device in use**: {cam_obj.error_message}")

            # Display feed image if available
            if active_sess and cam_obj and cam_obj.annotated_frame is not None:
                st.image(cam_obj.annotated_frame, channels="BGR", use_container_width=True)
                st.caption(
                    f"👤 {cam_obj.visible_count} count | "
                    f"📊 {cam_obj.max_density} dens | "
                    f"⚡ {cam_obj.avg_speed:.1f} spd | "
                    f"🛡️ {cam_obj.risk_level} ({cam_obj.risk_score:.1f})"
                )
            else:
                st.markdown(f"""
                <div style="background: #0B1120; border-radius: 6px; height: 160px; display: flex; flex-direction: column; justify-content: center; align-items: center; border: 1px dashed rgba(255,255,255,0.1);">
                    <span style="font-size: 32px;">📹</span>
                    <span style="color: #64748B; font-size: 0.8rem; margin-top: 6px;">
                        {'Live Feed Operational — Monitoring Active' if active_sess and is_enabled else ('Camera Slot Disabled' if not is_enabled else 'Standby — Ready for Monitoring')}
                    </span>
                </div>
                """, unsafe_allow_html=True)

            # Check for active alert on this slot
            if cam.slot_id in active_alerts_by_cam:
                alt = active_alerts_by_cam[cam.slot_id]
                st.markdown(f"""
                <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 6px; padding: 6px 10px; margin-top: 6px;">
                    <span style="color: #EF4444; font-weight: 700; font-size: 0.8rem;">🚨 {alt.severity}: {alt.reason[:28]}</span>
                </div>
                """, unsafe_allow_html=True)
                if not is_viewer:
                    b_c1, b_c2 = st.columns(2)
                    with b_c1:
                        if st.button(f"🔔 Ack {cam.slot_id}", key=f"grid_ack_{alt.id}_{organization.id}", use_container_width=True):
                            tenant_op_service.acknowledge_alert(actor=user, organization_id=organization.id, alert_id=alt.id)
                            st.rerun()
                    with b_c2:
                        if st.button(f"✅ Resolve {cam.slot_id}", key=f"grid_res_{alt.id}_{organization.id}", use_container_width=True):
                            tenant_op_service.resolve_alert(actor=user, organization_id=organization.id, alert_id=alt.id, note="Resolved in Grid")
                            st.rerun()


# =============================================================================
# 2B. TENANT CAMERA SLOTS CONFIGURATION TAB
# =============================================================================

def render_tenant_cameras_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    tenant_op_service: TenantOperationalService
) -> None:
    """Renders the 4 configurable camera slots for the organization."""
    st.write("")
    is_viewer = membership.role == "VIEWER" and not is_platform_admin(user)
    configs = tenant_op_service.get_camera_configs(actor=user, organization_id=organization.id)

    st.markdown("#### Configured Camera Slots (4 Dedicated Channels)")
    st.caption("Each organization maintains independent camera definitions. Physical devices such as webcams are protected with exclusive locking.")

    if is_viewer:
        st.info("👀 Viewing in read-only mode. Configuration edits require Operator or Administrator privileges.")

    for cam in configs:
        with st.expander(f"⚙️ {cam.slot_id}: {cam.name} ({cam.source_type.upper()})", expanded=False):
            if is_viewer:
                st.markdown(f"**Camera Name:** {cam.name}")
                st.markdown(f"**Source Type:** `{cam.source_type}`")
                st.markdown(f"**Source:** `{cam.source}`")
                st.markdown(f"**Device Name:** {cam.device_name or 'N/A'}")
                st.markdown(f"**Status:** {'Enabled' if cam.enabled else 'Disabled'}")
                st.markdown(f"**Detection Mode:** `{cam.detection_mode}`")
            else:
                with st.form(f"form_cam_cfg_{cam.slot_id}_{organization.id}"):
                    c_name = st.text_input("Camera Name", value=cam.name, key=f"name_{cam.slot_id}_{organization.id}")
                    c_enabled = st.checkbox("Enable Camera Slot", value=cam.enabled, key=f"en_{cam.slot_id}_{organization.id}")

                    type_options = ["video", "webcam", "phone", "rtsp"]
                    curr_type_idx = type_options.index(cam.source_type) if cam.source_type in type_options else 0
                    c_type = st.selectbox("Source Type", type_options, index=curr_type_idx, key=f"type_{cam.slot_id}_{organization.id}")

                    c_source = st.text_input("Source Path / Device Index / Stream URL", value=str(cam.source), key=f"src_{cam.slot_id}_{organization.id}")
                    c_mode = st.selectbox("Detection Mode", ["PERSON", "HEAD"], index=0 if cam.detection_mode == "PERSON" else 1, key=f"mode_{cam.slot_id}_{organization.id}")

                    submitted = st.form_submit_button("💾 Save Slot Configuration", type="primary")

                if submitted:
                    try:
                        tenant_op_service.update_camera_config(
                            actor=user,
                            organization_id=organization.id,
                            slot_id=cam.slot_id,
                            name=c_name,
                            source_type=c_type,
                            source=c_source,
                            enabled=c_enabled,
                            detection_mode=c_mode
                        )
                        st.success(f"Slot {cam.slot_id} updated successfully.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to update slot: {e}")


# =============================================================================
# 2C. TENANT ALERTS TAB
# =============================================================================

def render_tenant_alerts_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    tenant_op_service: TenantOperationalService
) -> None:
    """Renders active alerts, acknowledgment/resolution controls, and historical alert records."""
    st.write("")
    is_viewer = membership.role == "VIEWER" and not is_platform_admin(user)

    active_alerts = tenant_op_service.list_alerts(actor=user, organization_id=organization.id, status="ACTIVE")
    all_alerts = tenant_op_service.list_alerts(actor=user, organization_id=organization.id, limit=50)

    st.markdown(f"#### Active Operational Alerts ({len(active_alerts)})")

    if not active_alerts:
        st.info("✅ No active high-risk alerts logged for this organization.")
    else:
        for a in active_alerts:
            sev_colors = {
                "CRITICAL": ("#EF4444", "rgba(239, 68, 68, 0.15)"),
                "HIGH": ("#F97316", "rgba(249, 115, 22, 0.15)"),
                "MEDIUM": ("#FBBF24", "rgba(251, 191, 36, 0.15)")
            }
            fg, bg = sev_colors.get(a.severity.upper(), ("#00D9FF", "rgba(0, 217, 255, 0.15)"))

            with st.container():
                st.markdown(f"""
                <div style="background: {bg}; border-left: 4px solid {fg}; border-radius: 0 8px 8px 0; padding: 14px 18px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: {fg}; font-weight: 800; font-family: var(--cp-font-mono); font-size: 0.95rem;">
                            [{a.severity}] {a.camera_name} ({a.camera_id})
                        </span>
                        <span style="color: #94A3B8; font-size: 0.78rem;">
                            {a.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
                        </span>
                    </div>
                    <div style="color: #E2E8F0; font-size: 0.88rem; margin: 6px 0;">
                        <b>Reason:</b> {a.reason}
                    </div>
                    <div style="color: #94A3B8; font-size: 0.8rem;">
                        Zone: <code style="color: {fg};">{a.primary_risk_zone} ({a.zone_description})</code> &bull; 
                        Peak Density: <b>{a.primary_zone_density}</b> &bull; 
                        Persons: <b>{a.person_count}</b> &bull; 
                        Score: <b>{a.risk_score:.1f}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if not is_viewer:
                    c_btn1, c_btn2, _ = st.columns([1, 1, 3])
                    with c_btn1:
                        if st.button("👁️ Acknowledge", key=f"ack_{a.id}_{organization.id}"):
                            try:
                                tenant_op_service.acknowledge_alert(actor=user, organization_id=organization.id, alert_id=a.id)
                                st.success("Alert acknowledged.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    with c_btn2:
                        if st.button("✅ Resolve", key=f"res_{a.id}_{organization.id}"):
                            try:
                                tenant_op_service.resolve_alert(actor=user, organization_id=organization.id, alert_id=a.id, note="Resolved by operator")
                                st.success("Alert resolved.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

    st.write("")
    st.markdown("#### Alert History Log")
    if all_alerts:
        table_lines = [
            "| Time | Camera | Severity | Status | Reason | Zone |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for a in all_alerts[:25]:
            t_str = a.created_at.strftime("%H:%M:%S")
            table_lines.append(f"| {t_str} | {a.camera_id} | {a.severity} | {a.status} | {a.reason[:32]} | {a.primary_risk_zone} |")
        st.markdown("\n".join(table_lines))
    else:
        st.caption("No historical alerts found for this organization.")


# =============================================================================
# 2D. TENANT ANALYTICS & TRENDS TAB
# =============================================================================

def render_tenant_analytics_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    tenant_op_service: TenantOperationalService
) -> None:
    """Renders tenant-scoped metrics, risk distribution, and historical statistics."""
    st.write("")
    st.markdown("#### Tenant Surveillance Analytics")
    st.caption("Aggregated strictly from the active organization's surveillance sessions and cameras.")

    summary = tenant_op_service.get_analytics_summary(actor=user, organization_id=organization.id)
    counts = summary.get("alert_counts", {})

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Incidents", counts.get("total", 0))
    with m2:
        st.metric("Active Alerts", counts.get("active", 0))
    with m3:
        st.metric("Acknowledged", counts.get("acknowledged", 0))
    with m4:
        st.metric("Resolved", counts.get("resolved", 0))
    with m5:
        st.metric("Critical Alerts", counts.get("critical", 0))

    st.write("")
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        st.markdown("##### Camera Alert Distribution")
        cam_dist = summary.get("camera_alert_distribution", {})
        if cam_dist:
            for cam_id, count in cam_dist.items():
                st.markdown(f"- **{cam_id}:** {count} incidents recorded")
        else:
            st.info("No camera alert events recorded yet.")

    with c_col2:
        st.markdown("##### Severity Breakdown")
        st.markdown(f"""
        - 🔴 **Critical:** `{counts.get('critical', 0)}`
        - 🟠 **High:** `{counts.get('high', 0)}`
        - 🟡 **Medium:** `{counts.get('medium', 0)}`
        """)

    st.write("")
    st.markdown("##### Recent Surveillance Sessions")
    sessions = summary.get("recent_sessions", [])
    if sessions:
        sess_lines = [
            "| Session ID | Status | Started At | Ended At |",
            "| :--- | :--- | :--- | :--- |"
        ]
        for s in sessions[:10]:
            st_str = s.started_at.strftime("%Y-%m-%d %H:%M:%S")
            end_str = s.ended_at.strftime("%Y-%m-%d %H:%M:%S") if s.ended_at else "Active"
            sess_lines.append(f"| `{s.id}` | {s.status} | {st_str} | {end_str} |")
        st.markdown("\n".join(sess_lines))
    else:
        st.caption("No historical sessions recorded.")


# =============================================================================
# 2E. TENANT VIDEO ASSETS & SESSIONS TAB
# =============================================================================

def render_tenant_assets_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    tenant_op_service: TenantOperationalService
) -> None:
    """Renders isolated video asset uploads and surveillance session logs."""
    st.write("")
    is_viewer = membership.role == "VIEWER" and not is_platform_admin(user)

    st.markdown("#### Upload Video for Organization Surveillance")
    st.caption("Uploaded videos are securely stored in isolated tenant directories with path traversal protection.")

    if is_viewer:
        st.info("👀 Uploading video assets requires Operator or Administrator privileges.")
    else:
        uploaded_file = st.file_uploader(
            "Select Video File",
            type=["mp4", "avi", "mov", "webm"],
            key=f"file_up_{organization.id}"
        )
        target_slot = st.selectbox(
            "Assign to Camera Slot (Optional):",
            ["None", "CAM-01", "CAM-02", "CAM-03", "CAM-04"],
            key=f"slot_up_{organization.id}"
        )
        if uploaded_file is not None:
            if st.button("📤 Upload and Store", key=f"btn_up_store_{organization.id}", type="primary"):
                try:
                    file_bytes = uploaded_file.read()
                    slot = target_slot if target_slot != "None" else None
                    asset = tenant_op_service.save_uploaded_video(
                        actor=user,
                        organization_id=organization.id,
                        file_bytes=file_bytes,
                        original_filename=uploaded_file.name,
                        slot_id=slot
                    )
                    if slot:
                        tenant_op_service.update_camera_config(
                            actor=user,
                            organization_id=organization.id,
                            slot_id=slot,
                            name=f"Uploaded: {uploaded_file.name[:20]}",
                            source_type="video",
                            source=asset.storage_path,
                            enabled=True
                        )
                    st.success(f"Video '{uploaded_file.name}' stored successfully under tenant storage.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload failed: {e}")

    st.write("")
    st.markdown("##### Uploaded Assets Directory")
    assets = tenant_op_service.list_uploaded_assets(actor=user, organization_id=organization.id)
    if assets:
        for a in assets:
            sz_mb = a.file_size_bytes / (1024 * 1024)
            st.markdown(f"- **{a.filename}** ({sz_mb:.2f} MB) &bull; Slot: `{a.slot_id or 'None'}` &bull; Uploaded: {a.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    else:
        st.caption("No video assets uploaded for this organization.")

    st.write("")
    st.markdown("##### Historical Monitoring Sessions")
    sessions = tenant_op_service.list_monitoring_sessions(actor=user, organization_id=organization.id, limit=20)
    if sessions:
        s_lines = [
            "| Session ID | Status | Started At | Ended At |",
            "| :--- | :--- | :--- | :--- |"
        ]
        for s in sessions:
            st_str = s.started_at.strftime("%Y-%m-%d %H:%M:%S")
            end_str = s.ended_at.strftime("%Y-%m-%d %H:%M:%S") if s.ended_at else "Active"
            s_lines.append(f"| `{s.id}` | {s.status} | {st_str} | {end_str} |")
        st.markdown("\n".join(s_lines))
    else:
        st.caption("No historical sessions recorded.")


# =============================================================================
# 2F. TENANT NOTIFICATION SETTINGS TAB
# =============================================================================

def render_tenant_notifications_tab(
    user: User,
    organization: Organization,
    membership: OrganizationMembership,
    tenant_op_service: TenantOperationalService
) -> None:
    """Renders organization-specific notification settings."""
    st.write("")
    can_admin = is_platform_admin(user) or (membership and membership.role in ("ORG_ADMIN", "ADMIN"))
    settings = tenant_op_service.get_notification_settings(actor=user, organization_id=organization.id)

    st.markdown("#### Organization Notification Routing")
    st.caption("Alerts generated within this workspace are routed strictly to this organization's configured recipients.")

    if not can_admin:
        st.info("👀 Viewing in read-only mode. Notification settings can be modified by Organization Administrators.")
        st.markdown(f"**Email Delivery:** {'Enabled' if settings.email_notifications_enabled else 'Disabled'}")
        st.markdown(f"**Email Recipients:** {', '.join(settings.email_recipients) if settings.email_recipients else 'None configured'}")
        st.markdown(f"**Email Severities:** {', '.join(settings.email_severities)}")
        st.markdown(f"**SMTP Host:** {settings.smtp_host or 'System Default'}")
        st.markdown(f"**SMS Delivery:** {'Enabled' if settings.sms_notifications_enabled else 'Disabled'}")
    else:
        with st.form(f"form_notif_{organization.id}"):
            em_enabled = st.checkbox("Enable Email Notifications", value=settings.email_notifications_enabled)
            recipients_str = st.text_area(
                "Email Recipients (comma-separated)",
                value=", ".join(settings.email_recipients),
                help="Alert emails for this organization will be sent strictly to these addresses."
            )
            severities_sel = st.multiselect(
                "Trigger Alert Severities",
                ["CRITICAL", "HIGH", "MEDIUM"],
                default=[s for s in settings.email_severities if s in ["CRITICAL", "HIGH", "MEDIUM"]]
            )
            st.divider()
            st.markdown("##### Custom SMTP Server (Optional Override)")
            c_host = st.text_input("SMTP Host (Leave empty for system default)", value=settings.smtp_host or "")
            c_port = st.number_input("SMTP Port", value=settings.smtp_port or 587, min_value=1, max_value=65535)
            c_user = st.text_input("SMTP Username", value=settings.smtp_username or "")
            c_pass = st.text_input("SMTP Password", value=settings.smtp_password or "", type="password")
            c_sender = st.text_input("Email Sender Address", value=settings.email_sender or "")

            sub_notif = st.form_submit_button("💾 Save Notification Settings", type="primary")

        if sub_notif:
            try:
                rec_list = [r.strip().lower() for r in recipients_str.split(",") if r.strip() and "@" in r]
                tenant_op_service.update_notification_settings(
                    actor=user,
                    organization_id=organization.id,
                    email_enabled=em_enabled,
                    email_recipients=rec_list,
                    email_severities=severities_sel or ["HIGH", "CRITICAL"],
                    smtp_host=c_host.strip() or None,
                    smtp_port=int(c_port) if c_host.strip() else None,
                    smtp_username=c_user.strip() or None,
                    smtp_password=c_pass.strip() or None,
                    email_sender=c_sender.strip() or None
                )
                st.success("Notification settings saved successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update notifications: {e}")


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
