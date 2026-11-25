# CROWDPatrol 2.0 — Phase 2B.3: Operational Tenant Isolation Implementation Report

**Status:** COMPLETE & VERIFIED  
**Date:** 2026-11-23  
**Schema Version:** 5  
**Automated Test Suite Status:** 119/119 PASSED (100%)  
**Headless Streamlit Execution:** Verified (`AppTest` exited 0 with 0 exceptions)

---

## 1. Executive Summary

Phase 2B.3 successfully extends CrowdPatrol 2.0 from administrative multi-tenancy (organizations, memberships, and secure invitations) into full **operational tenant isolation**. Each organization now owns a strictly isolated operational workspace featuring:

1. **4 Configurable Camera Slots (`CAM-01` through `CAM-04`) per organization**: Each tenant configures its own sources (webcam, RTSP, video file, or test pattern) without conflicting with other tenants.
2. **Physical Device Locking & Contention Handling**: Hardware webcams (`webcam_0`, `webcam_1`, etc.) are protected by `PhysicalDeviceRegistry`, which grants exclusive runtime locks. When a second tenant attempts to monitor a camera source bound to an active webcam, it gracefully reports `DEVICE_IN_USE` without crashing or interrupting the primary tenant.
3. **Compute Capacity Scheduling**: A host-level `ComputeScheduler` bounds concurrent surveillance sessions across tenants (default max 4 concurrent sessions), tracking CPU/GPU usage and automatically releasing abandoned or timed-out locks.
4. **Tenant-Isolated Monitoring Sessions & Alert Lifecycle**: Sessions (`tenant_monitoring_sessions`) and alerts (`tenant_alerts`) are partitioned by `organization_id`. The alert lifecycle (`ACTIVE` -> `ACKNOWLEDGED` -> `RESOLVED`) is strictly enforced through server-side authorization.
5. **Role-Based Access Control (RBAC)**:
   - `PLATFORM_ADMIN` / `ORG_ADMIN`: Full configuration, session control, alert remediation, notification rules, asset management.
   - `OPERATOR`: Session start/stop, camera adjustments, alert acknowledgement/resolution, video file uploads.
   - `VIEWER`: Strictly read-only; denied from starting/stopping sessions, editing camera slots, acknowledging/resolving alerts, uploading videos, or updating notifications.
6. **Isolated Video Assets with Path Traversal Prevention**: Tenant-uploaded videos and artifacts are stored in canonical paths `data/tenants/<org_id>/videos/<asset_id>_<filename>`. Full path normalization and containment verification prevent directory traversal exploits.
7. **Per-Tenant Notification Routing**: Independent email dispatch targets, notification thresholds, and severity filters per organization.
8. **Comprehensive Operational Audit Trail**: Every camera update, session transition, alert lifecycle state change, video upload, and notification modification produces immutable structured audit logs.

---

## 2. Architecture & Data Model (Schema v5)

The database schema has been upgraded from Version 4 to **Version 5** in `src/auth/database.py`. Migration `_apply_migration_v5` executes atomically within a transaction, preserving backward compatibility and existing user/organization data.

### 2.1 Database Tables Added

```sql
-- 1. Tenant Camera Configurations (4 slots per organization)
CREATE TABLE IF NOT EXISTS tenant_camera_configs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    slot_id TEXT NOT NULL, -- CAM-01, CAM-02, CAM-03, CAM-04
    name TEXT NOT NULL,
    source_type TEXT NOT NULL, -- WEBCAM, RTSP, VIDEO_FILE, TEST_PATTERN
    source_uri TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    resolution TEXT DEFAULT '1280x720',
    fps_target INTEGER DEFAULT 30,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE (organization_id, slot_id)
);
CREATE INDEX IF NOT EXISTS idx_tenant_camera_configs_org ON tenant_camera_configs(organization_id);

-- 2. Tenant Monitoring Sessions
CREATE TABLE IF NOT EXISTS tenant_monitoring_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    started_by_user_id TEXT NOT NULL,
    status TEXT NOT NULL, -- ACTIVE, STOPPED, FAILED
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    active_camera_count INTEGER DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (started_by_user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_tenant_monitoring_sessions_org ON tenant_monitoring_sessions(organization_id, status);

-- 3. Tenant Alerts & Lifecycle
CREATE TABLE IF NOT EXISTS tenant_alerts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    session_id TEXT,
    slot_id TEXT NOT NULL,
    severity TEXT NOT NULL, -- HIGH, MEDIUM, LOW, CRITICAL
    alert_type TEXT NOT NULL,
    description TEXT NOT NULL,
    risk_score REAL DEFAULT 0.0,
    crowd_count INTEGER DEFAULT 0,
    status TEXT NOT NULL, -- ACTIVE, ACKNOWLEDGED, RESOLVED
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by_user_id TEXT,
    resolved_at TEXT,
    resolved_by_user_id TEXT,
    resolution_notes TEXT,
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES tenant_monitoring_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (acknowledged_by_user_id) REFERENCES users(id),
    FOREIGN KEY (resolved_by_user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_tenant_alerts_org_status ON tenant_alerts(organization_id, status, created_at DESC);

-- 4. Tenant Notification Settings
CREATE TABLE IF NOT EXISTS tenant_notification_settings (
    organization_id TEXT PRIMARY KEY,
    email_alerts_enabled INTEGER NOT NULL DEFAULT 0,
    recipient_emails TEXT DEFAULT '',
    min_severity TEXT DEFAULT 'HIGH',
    sms_alerts_enabled INTEGER NOT NULL DEFAULT 0,
    sms_recipients TEXT DEFAULT '',
    webhook_url TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- 5. Tenant Uploaded Assets & Videos
CREATE TABLE IF NOT EXISTS tenant_uploaded_assets (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    uploaded_by_user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_hash TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_tenant_uploaded_assets_org ON tenant_uploaded_assets(organization_id, created_at DESC);
```

### 2.2 PostgreSQL Migration Strategy

For production deployment to PostgreSQL:
1. Column types map cleanly (`TEXT` -> `VARCHAR`/`TEXT`, `INTEGER` -> `BOOLEAN` / `INT`, `REAL` -> `NUMERIC`/`REAL`).
2. Schema versioning logic in `_apply_migration_v5` uses standardized SQL DDL compatible with PostgreSQL `CREATE TABLE IF NOT EXISTS` and `ON CONFLICT DO UPDATE`.
3. Row-level security (RLS) can be enabled directly on PostgreSQL tables using `USING (organization_id = current_setting('app.current_org_id'))`.

---

## 3. Subsystem Implementation Details

### 3.1 Physical Device Registry & Compute Scheduler (`src/resource_manager.py`)
- **`PhysicalDeviceRegistry`**:
  - Maintains in-memory thread-safe locks (`threading.Lock()`) mapping physical camera device indices (e.g. `webcam_0`) to owning organizations and session IDs.
  - Returns `(acquired: bool, reason: str)`. When locked by another tenant, returns `(False, "DEVICE_IN_USE: Physical device held by org <org_id> in session <session_id>")`.
  - Releases device locks cleanly when sessions terminate or encounter errors.
- **`ComputeScheduler`**:
  - Enforces `MAX_CONCURRENT_SESSIONS` (default: 4 concurrent monitoring sessions).
  - Rejects session initiation when capacity is exhausted (`CAPACITY_EXCEEDED`).
  - Stale session recovery: active sessions older than a configurable threshold without keepalive are automatically swept.

### 3.2 Tenant Operational Service (`src/auth/tenant_operational_service.py`)
- Sits between the UI/API and the database.
- Every operational method requires:
  1. `actor: User`
  2. `organization_id: str`
- Calls `resolve_tenant_context(user=actor, requested_org_id=organization_id, db=self.db)`:
  - Validates organization existence and active state (`ACTIVE`).
  - Verifies actor's membership and active state (`ACTIVE`).
  - Bypasses only for `PLATFORM_ADMIN`.
- Enforces RBAC permissions via `has_permission` (`can_view`, `can_operate`, `can_admin`):
  - Viewers are rejected with `PermissionError` on all mutating actions.
- Enforces strict path traversal defenses for file uploads:
  ```python
  canonical_target = os.path.realpath(target_path)
  canonical_base = os.path.realpath(org_upload_dir)
  if not canonical_target.startswith(canonical_base + os.path.sep):
      raise PermissionError("Path traversal rejected")
  ```

### 3.3 MultiCameraManager Integration (`src/multi_camera_manager.py`)
- Updated `MultiCameraManager` to accept dynamic `camera_configs: List[TenantCameraConfig]` and `session_id: str`.
- When opening sources, `CameraState.open_source()` requests a physical device lock from `get_physical_device_registry()`.
- If the lock is refused (`acquired == False`), it marks the camera status as `"DEVICE_IN_USE"` without raising an unhandled exception or crashing the surveillance loop.
- Automatically releases all held physical locks in `release_all()`.

### 3.4 AlertManager Tenant Integration (`src/alert_manager.py`)
- Updated `AlertManager`, `CameraAlertTracker`, and `AlertEvent` with optional `organization_id` and `session_id`.
- When an alert event fires with `organization_id`, it records the alert through `TenantOperationalService.record_alert(...)`, syncing real-time AI alert detections into the tenant's isolated database.

### 3.5 Organization Workspace UI (`dashboard/org_ui.py`)
The organization workspace now renders 8 dedicated tabs styled in the Nocturnal Design System:
1. **📹 CCTV Monitoring**: Live multi-camera grid for `CAM-01` through `CAM-04`, status badges (`ACTIVE`, `STANDBY`, `DEVICE_IN_USE`), Start/Stop Monitoring controls.
2. **⚙️ Camera Slots**: Edit source type (Webcam, RTSP, Video File, Test Pattern), URIs, and resolutions for all 4 slots.
3. **🚨 Alerts Center**: Real-time alerts table, acknowledge/resolve workflows with resolution notes, severity badges (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
4. **📊 Analytics & Trends**: Active vs Resolved alerts metrics, high-risk incident counters, risk distribution across cameras.
5. **📁 Video Uploads & Sessions**: Upload surveillance video clips (MP4, AVI, MOV), asset checksums, session history log.
6. **🔔 Notifications**: Tenant email alert toggles, recipient lists, minimum severity filters.
7. **👥 Team Roster**: Member management and invitations (from Phase 2B.2).
8. **📋 Audit Trail**: Searchable audit log covering operational and administrative actions.

---

## 4. Verification & Testing

A comprehensive automated test suite of **119 tests** was executed, validating all components across security, multi-tenancy, authentication, and UI:

### 4.1 Test Suites Executed

| Test Suite File | Tests | Status | Scope |
|---|---|---|---|
| `tests/test_tenant_isolation.py` | 10 | **PASSED** | Schema v5, Slot isolation, Device locking, Compute scheduling, Alert lifecycle, VIEWER read-only, Path traversal prevention, Cross-tenant denial, Notification isolation, Streamlit AppTest |
| `tests/test_security_remediation_sec01_sec02.py` | 10 | **PASSED** | SEC-01 concurrent invitation locks, SEC-02 token sanitization |
| `tests/test_audit_phase2b2.py` | 10 | **PASSED** | Single-use invitation acceptance, token security, RBAC fail-closed |
| `tests/test_invitations.py` | 14 | **PASSED** | Invitation issuance, token hashing, email matching, role escalation blocks |
| `tests/test_organization_ui.py` | 6 | **PASSED** | Workspace rendering, org selector, boundary notice, invite UI |
| `tests/test_organizations.py` | 25 | **PASSED** | Multi-organization foundation, membership transitions, last admin protections |
| `tests/test_auth.py` | 38 | **PASSED** | Passwords, sessions, atomic lockout, account enumeration defenses |
| `tests/test_landing_page.py` | 6 | **PASSED** | Landing page UI, theme consistency, query param deep-linking |
| **TOTAL** | **119** | **PASSED (100%)** | |

### 4.2 Streamlit Headless Execution
Executed headless application verification using Streamlit `AppTest`:
```bash
python -c "from streamlit.testing.v1 import AppTest; at = AppTest.from_file('dashboard/simple_dashboard.py'); at.run(timeout=30); assert len(at.exception) == 0; print('APPTEST_SUCCESS')"
```
**Result**: `APPTEST_SUCCESS` (0 unhandled exceptions).

---

## 5. Security Summary & Findings

1. **Client Trust Elimination**: Organization context is derived strictly from verified database memberships via `resolve_tenant_context`. Tampering with session state or passing arbitrary org IDs fails closed with `PermissionError`.
2. **Strict Read-Only Enforcement for Viewers**: All write operations (camera updates, session toggles, alert lifecycle transitions, video uploads, notification changes) enforce role checks on the server side.
3. **Physical Hardware Protection**: Direct concurrent access to the same local webcam index is blocked before OpenCV device initialization, preventing driver deadlocks.
4. **Filesystem Isolation**: File uploads are forced into `data/tenants/<org_id>/videos/` with double-checked directory prefixes, eliminating relative path traversal (`../`) attacks.
5. **No Secret Leaks**: Audit logs and error messages never expose passwords, password hashes, or session tokens.

---

## 6. Phase 2B.3 Completion Checklist

- [x] Schema Version 5 with tables for cameras, sessions, alerts, notifications, and assets.
- [x] 4 camera slots per organization initialized automatically.
- [x] Physical device locking (`PhysicalDeviceRegistry`) with `DEVICE_IN_USE` handling.
- [x] Host compute scheduling (`ComputeScheduler`) with bounded session limits.
- [x] Tenant-isolated alert lifecycle (`ACTIVE` -> `ACKNOWLEDGED` -> `RESOLVED`).
- [x] Server-side RBAC enforcement for `PLATFORM_ADMIN`, `ORG_ADMIN`, `OPERATOR`, and `VIEWER`.
- [x] Path-traversal-resistant video asset storage partitioned by tenant.
- [x] Organization-specific notification settings.
- [x] Operational UI integrated with 8 tabs in `dashboard/org_ui.py`.
- [x] Full regression test pass (119/119 tests passing).
- [x] Headless Streamlit `AppTest` execution confirmed clean.
