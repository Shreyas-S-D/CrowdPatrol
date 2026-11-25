# CROWDPatrol 2.0 — Multi-Tenancy Architecture & Pipeline Orchestration Specification

**Product:** CROWDPatrol  
**Version:** 2.0.0-PROPOSED  
**Date:** November 23, 2026  

---

## 1. Multi-Tenant Relational Schema Architecture

To support isolated organizational workspaces (e.g. *AMC Engineering College*, *Stadium Security Command*, *Metro Transit Hub*), CROWDPatrol 2.0 implements a **shared-process, pooled-database with tenant-discriminator architecture**.

### 1.1 Storage Technology Choice
- **Local Development & Automated Testing:** Embedded SQLite (`data/crowdpatrol_tenants.db`) with `PRAGMA foreign_keys = ON;`. Requires zero external services or daemon management, runs safely under Windows, and guarantees isolated transactional tests.
- **Production Readiness:** Schema DDL and Data Access Layer (DAL) are written to be 100% compatible with PostgreSQL 15+ using parameterized queries and standard SQL types.

### 1.2 Entity Relationship Model

```
┌─────────────────────────┐           ┌─────────────────────────┐
│      organizations      │           │          users          │
├─────────────────────────┤           ├─────────────────────────┤
│ id (PK, VARCHAR)        │           │ id (PK, VARCHAR)        │
│ name (VARCHAR)          │           │ username (UNIQUE)       │
│ slug (UNIQUE, VARCHAR)  │           │ email (UNIQUE)          │
│ status (ACTIVE/SUSPEND) │           │ password_hash (Scrypt)  │
│ created_at (TIMESTAMP)  │           │ full_name (VARCHAR)     │
└────────────┬────────────┘           │ is_active (BOOLEAN)     │
             │ 1                      │ created_at (TIMESTAMP)  │
             │                        └────────────┬────────────┘
             │ N                                   │ 1
┌────────────▼─────────────────────────────────────▼────────────┐
│                          memberships                          │
├───────────────────────────────────────────────────────────────┤
│ id (PK, VARCHAR)                                              │
│ organization_id (FK -> organizations.id, INDEXED)             │
│ user_id (FK -> users.id, INDEXED)                             │
│ role (PLATFORM_ADMIN, ORG_ADMIN, OPERATOR, VIEWER)            │
│ created_at (TIMESTAMP)                                        │
│ UNIQUE (organization_id, user_id)                             │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ├─────────────────────────────────────────────────┐
                             │ 1                                               │ 1
┌────────────────────────────▼──────────────┐     ┌────────────────────────────▼──────────────┐
│                  cameras                  │     │                   alerts                  │
├───────────────────────────────────────────┤     ├───────────────────────────────────────────┤
│ id (PK, VARCHAR)                          │     │ id (PK, VARCHAR)                          │
│ organization_id (FK, INDEXED)             │     │ organization_id (FK, INDEXED)             │
│ camera_code (e.g. 'CAM-01')               │     │ camera_id (VARCHAR)                       │
│ name (VARCHAR)                            │     │ risk_level (LOW, MEDIUM, HIGH, CRITICAL)  │
│ source (VARCHAR)                          │     │ severity (LOW, MEDIUM, HIGH, CRITICAL)    │
│ source_type (video, webcam, rtsp, phone)  │     │ risk_score (FLOAT)                        │
│ enabled (BOOLEAN)                         │     │ max_density (INTEGER)                     │
│ detection_mode (PERSON, HEAD)             │     │ primary_zone (VARCHAR)                    │
│ created_at (TIMESTAMP)                    │     │ status (ACTIVE, ACKNOWLEDGED, RESOLVED)   │
│ UNIQUE (organization_id, camera_code)     │     │ acknowledged_by (VARCHAR, NULLABLE)       │
└───────────────────────────────────────────┘     │ resolved_by (VARCHAR, NULLABLE)           │
                                                  │ resolution_note (TEXT)                    │
                                                  │ created_at (TIMESTAMP)                    │
                                                  └───────────────────────────────────────────┘
```

---

## 2. Multi-Tenant Pipeline Feasibility & Orchestration Model

### 2.1 Critical Investigation: Can `MultiCameraManager` Support Multiple Organizations?

During Phase 0 audit, the AI engine concurrency constraints were scrutinized:

1. **Hardware Resource Contention:**
   - In Phase 11 benchmarks, running one `MultiCameraManager` with 4 cameras in staggered stride saturated ~8 cores (800% psutil) on the Intel Core i7-13700H CPU.
   - If two organizations concurrently run live 4-camera CCTV grids on the same CPU, thread contention would cause loop rates to drop from 3.6 iters/s to < 1.5 iters/s, resulting in degraded video updates.
2. **Physical Hardware Locks:**
   - DirectShow hardware devices (laptop webcam index 0, external USB webcam index 1) are single-consumer on Windows. If Organization A opens device 0, Organization B attempting to capture device 0 will fail with `OFFLINE`.
3. **Streamlit Session Model:**
   - In Streamlit, each browser tab runs in its own thread with private `st.session_state`.
   - Storing `MultiCameraManager` inside `st.session_state.multi_cam` creates session-level isolation, but without tenant management, both sessions would read/write to the same global `config/cameras.json` and share Firebase RTDB `alerts/` keys.

### 2.2 The Solution: Scoped Multi-Tenant Orchestrator

To guarantee strict multi-tenant isolation without resource crashes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   Tenant-Scoped AI Orchestration Architecture               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Scoped Configurations:                                                   │
│    - Each organization maintains its own camera inventory in the database.  │
│    - MultiCameraManager is instantiated with tenant-specific camera paths:  │
│      config/tenants/<org_id>/cameras.json                                   │
│                                                                             │
│ 2. Scoped Alert & Telemetry Dispatchers:                                    │
│    - Each tenant has an independent AlertManager instance.                  │
│    - Firebase RTDB paths are namespaced:                                    │
│      tenants/<org_id>/alerts/<alert_id>                                     │
│      tenants/<org_id>/telemetry/latest                                      │
│                                                                             │
│ 3. Hardware Device Conflict Guard:                                          │
│    - A central DeviceLockManager checks whether a physical camera index     │
│      is already actively streaming in another tenant session.               │
│    - If acquired, reports clean status: "DEVICE_IN_USE_BY_ANOTHER_TENANT"   │
│                                                                             │
│ 4. Isolated File Storage:                                                   │
│    - Uploaded video files: data/tenants/<org_id>/videos/                    │
│    - Exported PDF/CSV reports: data/tenants/<org_id>/reports/               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Isolation & Security Enforcement

### Rule 1: Zero Client-Side Trust
The tenant identifier is **never accepted from query parameters or client input**.
When an authenticated user requests an action, the server resolves:
```python
active_org_id = st.session_state.get("active_organization_id")
user_id = st.session_state.get("auth_user_id")

# Verify server-side membership in database
membership = dal.get_membership(user_id=user_id, organization_id=active_org_id)
if not membership or not membership.is_active:
    raise SecurityException("Cross-tenant access violation: Unauthorized organization context")
```

### Rule 2: Universal Scoped Queries in the DAL
Every SQL query executed across the application is parameterized and forcibly scoped:
```python
# CORRECT (Tenant-Scoped):
cursor.execute(
    "SELECT * FROM cameras WHERE organization_id = :org_id AND id = :cam_id",
    {"org_id": active_org_id, "cam_id": requested_cam_id}
)

# STRICTLY PROHIBITED:
cursor.execute("SELECT * FROM cameras WHERE id = :cam_id", {"cam_id": requested_cam_id})
```

### Rule 3: File System Path Traversal Prevention
When accessing uploaded video files:
```python
def resolve_tenant_video_path(organization_id: str, filename: str) -> Path:
    base_dir = (Path("data") / "tenants" / organization_id / "videos").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    target_path = (base_dir / filename).resolve()
    if not str(target_path).startswith(str(base_dir)):
        raise SecurityException("Path traversal attempt detected")
    return target_path
```

---

## 4. Tenant-Aware Notifications & Alerts

1. **SMTP Configuration Isolation:**
   - Each organization can define its own notification recipients (`ALERT_EMAIL_RECIPIENTS`) and severity threshold (`HIGH`, `CRITICAL`).
   - Global SMTP credentials (username/password) are managed solely by environment variables or encrypted platform config; tenant operators cannot view or extract SMTP passwords.
2. **Alert Lifecycle Integrity:**
   - `ACTIVE` -> `ACKNOWLEDGED` -> `RESOLVED`.
   - Operator acknowledgments log `operator_id`, `organization_id`, and `timestamp`.
   - An operator from Tenant A cannot see, acknowledge, or resolve alerts generated by Tenant B's cameras.
