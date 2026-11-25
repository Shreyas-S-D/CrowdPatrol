# CrowdPatrol 2.0 — Phase 2B.2 Architecture & Implementation Report
## Organization Workspace UI & Member Invitations Subsystem

**Document Version:** 1.0.0  
**Phase:** Phase 2B.2 (Organization Workspace UI & Member Invitations)  
**Date:** November 23, 2026  
**Status:** IMPLEMENTED, VERIFIED & PASSING (89/89 Unit & UI Tests Passing)  
**Security Status:** STRICT FAIL-CLOSED ISOLATION & NON-FABRICATED SURVEILLANCE BOUNDARIES  

---

## 1. Executive Summary

Phase 2B.2 delivers the complete user-facing multi-tenant organization experience and secure invitation lifecycle for **CrowdPatrol 2.0**, layered directly on top of the approved Phase 2A persistent authentication foundation, Phase 2A.4 atomic lockout fixes, and Phase 2B.1 organization data model.

Prior to Phase 2B.2, the platform possessed robust server-side organization schemas, membership roles, and context resolution, but lacked an interactive organization management surface and a secure mechanism to invite and onboard organization personnel.

In Phase 2B.2, we implemented:
1. **Schema Migration v3**: Added `organization_invitations` table with cryptographically secure token hashing (SHA-256), strict status transitions, and single-use atomic acceptance guarantees (`BEGIN IMMEDIATE`).
2. **Cryptographic Invitation Service (`src/auth/invitation_service.py`)**: End-to-end token generation (256-bit cryptographically secure entropy), time-bounded validity (72-hour default), anti-escalation validation, duplicate invitation suppression, existing member check, and SMTP email dispatch with fallback handling.
3. **8 Nocturnal Design System UI Views (`dashboard/org_ui.py`)**:
   - Organization Selector View (`render_org_selector`)
   - Organization Workspace & Navigation Shell (`render_org_workspace`)
   - Members Administration Tab (`render_members_tab`)
   - Member Invitations Issuance & Revocation Tab (`render_invitations_tab`)
   - Organization Settings Tab (`render_settings_tab`)
   - Immutable Audit Trail Viewer Tab (`render_audit_tab`)
   - Platform Administrator Control Center (`render_platform_admin_orgs`)
   - Public Invitation Acceptance & Onboarding View (`render_invitation_acceptance_view`)
4. **App Navigation Routing (`dashboard/simple_dashboard.py`)**: Deep linking for `?page=accept_invite&token=...`, session-state context preservation, workspace switching, and session revocation.
5. **Operational Boundaries**: Zero leakage between multi-tenant organization workspaces and real-time surveillance pipelines. Video streams, YOLOv8/DeepSORT AI inference, and alert managers operate strictly as dedicated edge sensors and are NOT represented or partitioned as mock tenant data.

---

## 2. Architecture & Data Model (Schema v3)

### 2.1 Database Schema Migration (`SCHEMA_VERSION = 3`)
The SQLite schema was migrated from version 2 to version 3 in `src/auth/database.py` via `_apply_migration_v3`.

```sql
CREATE TABLE IF NOT EXISTS organization_invitations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    normalized_email TEXT NOT NULL,
    invited_role TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    invited_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    expires_at TIMESTAMP NOT NULL,
    accepted_at TIMESTAMP,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_invitations_token_hash ON organization_invitations(token_hash);
CREATE INDEX IF NOT EXISTS idx_invitations_org_id ON organization_invitations(organization_id);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON organization_invitations(normalized_email);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON organization_invitations(status);
```

### 2.2 Dataclass & Immutability
`OrganizationInvitation` represents immutable invitation state:
```python
@dataclass
class OrganizationInvitation:
    id: str
    organization_id: str
    normalized_email: str
    invited_role: str
    token_hash: str
    invited_by: str
    status: str          # PENDING, ACCEPTED, REVOKED, EXPIRED
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 3. Secure Member Invitation Lifecycle

### 3.1 Cryptographic Token Architecture
- **Raw Token**: Generated via `secrets.token_urlsafe(32)` (256 bits of entropy). Never persisted in plain text in the database or system logs.
- **Token Hash**: Computed via `hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()`. Stored with a `UNIQUE` database constraint.
- **Validation**: Incoming query parameters `?page=accept_invite&token=<raw>` are hashed server-side and matched against `token_hash`.

### 3.2 Security Constraints Enforced by `InvitationService`
1. **Permission Gating**: Only actors holding `ORG_ADMIN` (or system `PLATFORM_ADMIN`) can issue or revoke invitations (`can_manage_members`).
2. **Anti-Escalation Safeguard**: Invitations are strictly restricted to valid organization roles: `ORG_ADMIN`, `OPERATOR`, `VIEWER`. Issuing invitations for system-level roles (`PLATFORM_ADMIN`, `SUPER_ADMIN`) is hard-blocked with `PermissionError`.
3. **Duplicate Prevention**: A user cannot be invited if an active invitation already exists with `status = 'PENDING'` for that email and organization.
4. **Active Member Check**: If a user with the normalized email already holds an active membership in the organization, invitation issuance is rejected.
5. **Single-Use Atomic Acceptance**:
   Acceptance is executed inside an atomic transaction using `BEGIN IMMEDIATE`:
   ```python
   cur.execute("""
       UPDATE organization_invitations
       SET status = 'ACCEPTED', accepted_at = ?, updated_at = ?
       WHERE id = ? AND status = 'PENDING';
   """, (now_iso, now_iso, invitation.id))
   if cur.rowcount == 0:
       raise ValueError("Invitation was already accepted, revoked, or expired.")
   
   cur.execute("""
       INSERT INTO organization_memberships (
           id, organization_id, user_id, role, status, joined_at, created_at, updated_at
       ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?);
   """, (membership_id, org.id, user_id, invitation.invited_role, now_iso, now_iso, now_iso))
   ```
6. **Concurrent Race Protection**: Concurrent acceptance requests cannot double-accept; the first transaction transitions the row to `ACCEPTED`, while all subsequent transactions encounter `rowcount == 0` and fail closed.

### 3.3 SMTP Notification Delivery
- Reuses existing `NotificationConfig.from_env()` infrastructure.
- Generates professional HTML & plain-text invitation emails with Nocturnal styling.
- **Fail-Open Delivery**: If SMTP fails (e.g. invalid server credentials in dev/test), the invitation remains securely created in the database, and the UI displays the invitation link for direct administrative retrieval.

---

## 4. UI Architecture & View Implementations (`dashboard/org_ui.py`)

All views strictly implement the **CrowdPatrol 2.0 Nocturnal Design System** with CSS variables (`--cp-bg-base`, `--cp-border-subtle`, `--cp-cyan`, `--cp-font-sans`, `--cp-font-mono`).

### 4.1 Organization Selector (`render_org_selector`)
- Displays all organizations accessible to the authenticated user.
- Visual hierarchy: Organization card with title, slug, status badge (`ACTIVE`, `SUSPENDED`, `ARCHIVED`), and user role badge (`ORG_ADMIN`, `OPERATOR`, `VIEWER`).
- **One-Click Context Switching**: "🚀 Enter Workspace" executes `resolve_tenant_context()`, sets `active_org` and `active_membership` in session state, and switches view mode.
- **Empty State**: Renders informative zero-state card for users without memberships.
- **Platform Admin Quick Switch**: If the user is `PLATFORM_ADMIN`, displays "⚙️ Platform Admin Center".
- **Session Revocation**: Provides standardized "🔒 Sign Out / Revoke Session" button (`auth_logout_btn`).

### 4.2 Organization Workspace Shell (`render_org_workspace`)
- Header displaying Organization Name, Unique ID, Slug, Organization Status, Active Role badge, and current authenticated operator.
- **Operational Boundary Banner**: Explicit warning card informing operators of data separation between workspace metadata and real-time sensor streams.
- **Tabbed Interface**:
  1. `👥 Members`: Roster management, role updates, suspensions, removals.
  2. `✉️ Invitations`: New invitation form and pending invitations roster.
  3. `⚙️ Organization Settings`: Metadata editing (ORG_ADMIN only).
  4. `📜 Audit Log`: Immutable cryptographic audit trail.

### 4.3 Members Tab (`render_members_tab`)
- Tabular roster of members with username, email, role, membership status, and join date.
- **Role Modifications**: Role selector allowing `ORG_ADMIN` to promote/demote members with last-admin safeguards.
- **Member Status Actions**: "Suspend Member", "Reactivate Member", and "Remove Member".
- **Permission Restraints**: `OPERATOR` and `VIEWER` see read-only information without action buttons.

### 4.4 Invitations Tab (`render_invitations_tab`)
- **Issuance Form** (ORG_ADMIN only):
  - Target Email Address (`email_input`)
  - Assigned Role (`ORG_ADMIN`, `OPERATOR`, `VIEWER`)
  - Expiration Window slider (1 to 168 hours; default 72 hours)
  - SMTP Delivery toggle
- **Pending Invitations Table**:
  - Email, Assigned Role, Inviter, Expiry Timestamp, and Revocation action.
  - Revoke button triggers immediate invalidation and non-repudiable audit logging.

### 4.5 Organization Settings Tab (`render_settings_tab`)
- Organization Name and Description inputs.
- Read-only display of Slug, Organization ID, and Creation Timestamp.
- Disabled for non-administrators.

### 4.6 Audit Trail Tab (`render_audit_tab`)
- Formatted audit log displaying timestamp, actor, action (`INVITATION_CREATED`, `INVITATION_ACCEPTED`, `INVITATION_REVOKED`, `MEMBER_ADDED`, `MEMBER_ROLE_UPDATED`, etc.), target, and structured metadata.

### 4.7 Platform Admin Center (`render_platform_admin_orgs`)
- **Organization Provisioning**: Name, unique slug, description, and optional initial administrator.
- **Directory Table**: Lists all organizations system-wide with live status toggle:
  - "⏸️ Suspend Org" -> `status = 'SUSPENDED'`
  - "▶️ Reactivate Org" -> `status = 'ACTIVE'`

### 4.8 Public Invitation Acceptance View (`render_invitation_acceptance_view`)
- Accessible publicly at `?page=accept_invite&token=<raw_token>`.
- **Validation**: Token hashed and checked for status, expiration, and organization standing.
- **Mode 1: Existing Authenticated User**:
  - Displays invitation details.
  - Validates that logged-in email matches invitation email. If mismatched, blocks acceptance with security message.
  - One-click "Accept & Enter Workspace" button.
- **Mode 2: New User Registration**:
  - Pre-fills email from invitation.
  - Collects username and password with confirmation.
  - Automatically provisions new user account with Scrypt password hash (`N=16384, r=8, p=1`).
  - Atomically accepts invitation, binds membership, signs in the user, and routes directly to the organization workspace.

---

## 5. Strict Operational Boundaries & Non-Fabricated Data

### 5.1 Verification of Data Separation
Surveillance telemetry and video feeds are strictly separated from multi-tenant organizational records:
1. **Zero Tenant Partitioning on Real-time Streams**: Live surveillance RTSP streams, YOLOv8 object detection, DeepSORT multi-person tracking, and optical flow vectors run on dedicated edge hardware and are not falsified as tenant-isolated data.
2. **Explicit UI Boundary Warnings**:
   The organization workspace displays a prominent isolation notice:
   > **Surveillance Isolation Boundary (Phase 2B Scope)**  
   > *Workspace membership and administrative controls are isolated. Physical camera partitions and tenant-scoped AI inference streams are scheduled for activation in Phase 2B.3. Global surveillance feeds remain separated.*
3. **No Synthetic Metrics**: No fake metrics or simulated tenant telemetry was added.

---

## 6. Complete Verification Matrix & Test Results

All test suites were executed in the Windows 11 sandbox environment using Python 3.14.6 and pytest 9.1.1.

### 6.1 Test Summary
| Test Suite | Total Tests | Passed | Failed | Execution Time | Scope / Coverage |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `tests/test_invitations.py` | 14 | 14 | 0 | 2.40s | Cryptographic tokens, hashing, roles, anti-escalation, expiry, atomic acceptance, concurrency, email delivery |
| `tests/test_organizations.py` | 25 | 25 | 0 | 7.43s | Schema v2, tenant context resolution, RBAC, last-admin protection, platform admin cross-tenant access |
| `tests/test_organization_ui.py` | 6 | 6 | 0 | 0.93s | Selector multi-tenancy, empty states, boundary notices, invitation lifecycle, revocation, platform admin provisioning |
| `tests/test_auth.py` | 38 | 38 | 0 | 45.18s | Scrypt hashing, rate limiting, atomic concurrency lockout, Streamlit AppTest login/logout cycle |
| `tests/test_landing_page.py` | 6 | 6 | 0 | 21.66s | Nocturnal design system, CSS variables, illustrative data notices, AppTest navigation |
| **TOTAL** | **89** | **89** | **0** | **~77s** | **100% Passing Test Suite Across All Subsystems** |

### 6.2 Streamlit AppTest Full Integration
Executing direct AppTest execution against the application entry point:
```powershell
python -c "from streamlit.testing.v1 import AppTest; at = AppTest.from_file('dashboard/simple_dashboard.py'); at.run(timeout=30); assert len(at.exception) == 0; print('APPTEST_SUCCESS')"
```
**Result:** `APPTEST_SUCCESS` (0 exceptions, 0 runtime tracebacks).

---

## 7. Modified & Created Files Inventory

### 7.1 New Subsystems & Files
- `src/auth/invitation_service.py` (Invitation service, token generator, email sender)
- `dashboard/org_ui.py` (8 nocturnal organization & member administration views)
- `tests/test_invitations.py` (14 unit tests for invitations)
- `tests/test_organization_ui.py` (6 unit tests for organization UI flows)
- `PHASE_2B_2_ORGANIZATION_UI_INVITATIONS.md` (This document)

### 7.2 Updated Files
- `src/auth/database.py` (Schema version 3, `organization_invitations` table, CRUD & atomic acceptance helpers)
- `src/auth/__init__.py` (Subsystem exports for invitations)
- `dashboard/simple_dashboard.py` (Invitation query param routing, workspace integration, session revocation handling)

### 7.3 Backups Retained
- `src/auth/database_backup_phase2b2.py`
- `src/auth/organization_service_backup_phase2b2.py`
- `src/auth/__init___backup_phase2b2.py`
- `dashboard/simple_dashboard_backup_phase2b2.py`
- `dashboard/auth_ui_backup_phase2b2.py`

---

## 8. Conclusion & Readiness for Review

Phase 2B.2 has met all objective requirements:
- Organizations and memberships can now be browsed, selected, and managed in a responsive, Nocturnal-styled Streamlit UI.
- Secure, cryptographically hashed member invitations can be issued, revoked, and accepted with single-use atomic guarantees.
- The existing Streamlit surveillance system, landing page, and authentication mechanisms remain fully functional with zero regressions across all 89 tests.
- Operational boundaries are cleanly established with no fabricated data.

**Phase 2B.2 is complete and ready for review and audit.**
