# CROWDPatrol 2.0 — Master Implementation Plan & Feature Preservation Matrix

**Product:** CROWDPatrol 2.0  
**Target Milestone:** Controlled Multi-Tenant Evolution  
**Version:** 2.0.0-PROPOSED  
**Date:** November 23, 2026  

---

## 1. Feature Preservation Checklist

Before any code modification, every existing feature is cataloged with its preservation mandate:

| Feature / Module | Component File | Preservation Mandate | Validation Method |
| :--- | :--- | :--- | :--- |
| **YOLOv8 Person Detection** | `src/detection.py` | 640×640 input resolution, confidence 0.35, COCO class 0 | Automated unit test |
| **YOLOv8 Overhead Head Detection**| `src/experimental_head_mode.py` | 640×640 input resolution, confidence 0.25 | `test_dual_mode.py` |
| **DeepSORT Multi-Object Tracking** | `src/tracking.py` | `max_age=30, n_init=1`, Channels-Last MobileNetV2 | Cosine similarity test |
| **Farneback Optical Flow Motion** | `src/motion_analysis.py` | Grid size (4×4), flow stride, velocity magnitude | Anomaly score check |
| **Spatial Density Estimation** | `src/density.py` | 4×4 spatial matrix, cell normalization, center-point mapping | Density matrix shape check |
| **Multi-Stage Risk Assessment** | `src/risk_assessment.py` | Low/Medium/High risk tiers, non-linear density scaling | Risk score calculation test |
| **Multi-Camera Engine & CCTV Grid**| `src/multi_camera_manager.py` | 2×2 grid, Focus Feed, staggered detection stride | `test_multi_camera.py` |
| **Physical Camera Capture** | `src/camera_devices.py` | Webcam (0, 1), IP Webcam, RTSP, Video uploads | Hardware probe test |
| **Alert Lifecycle Management** | `src/alert_manager.py` | ACTIVE -> ACKNOWLEDGED -> RESOLVED, cooldown 10s | `test_alert_manager.py` |
| **SMTP Alert Email Dispatch** | `src/notification_dispatcher.py`| Responsive HTML templates, `HIGH,CRITICAL` severities | Mock dispatch test |
| **Firebase Cloud Sync** | `src/alerts.py` | Realtime Database telemetry broadcast | Mock RTDB test |
| **Streamlit Standalone Fallback** | `dashboard/simple_dashboard.py`| Retain fallback launch script without breaking imports | `py_compile` test |

---

## 2. Staged Implementation Roadmap

### Phase 0 — Read-Only Architecture Audit (Current)
- Complete system audit, threat model, visual design tokens, and multi-tenant schema.
- **Milestone:** All architectural specifications approved by user.

### Phase 1 — Design System & Public Cinematic Landing Page
- Build reusable UI design tokens (`dashboard/design_system.py`) and CSS framework.
- Create full-screen cinematic landing experience in Streamlit:
  - Hero: "SEE THE CROWD. BEFORE THE RISK."
  - 5-Chapter Storytelling: The Problem -> Intelligence -> Awareness -> Response -> Platform.
  - Interactive AI capability demonstration widgets (visual bounding boxes, heatmap cards).
  - Navigation action: "Enter Command Center".
- **Safety Gate:** Verify existing operational dashboard remains accessible.

### Phase 2 — Authentication & Organization Foundation
- Create lightweight, secure Data Access Layer (`src/database/`): SQLite engine with foreign key enforcement.
- Implement Scrypt password hashing (`hashlib.scrypt`) and token management (`secrets`).
- Build Authentication UI views:
  - Operator Login.
  - Password Reset (Token-based).
  - Controlled Invitation Acceptance.
  - Multi-Organization Selection Screen.
- Implement server-side session validator with anti-fixation protection.
- **Safety Gate:** 100% pass rate on isolated authentication test suite.

### Phase 3 — Tenant Isolation Layer
- Implement tenant scoping across all data operations:
  - Database queries automatically inject `WHERE organization_id = :org_id`.
  - Scoped camera configurations (`config/tenants/<org_id>/cameras.json`).
  - Isolated uploaded video directories (`data/tenants/<org_id>/videos/`).
- Implement `DeviceLockManager` to resolve hardware camera exclusivity cleanly.
- Scope alert history, notification settings, and incident reports to the active tenant.
- **Safety Gate:** Explicit cross-tenant penetration test suite passes (zero data leakage).

### Phase 4 — Operational Dashboard Redesign
- Redesign Streamlit command-center interface matching the Linear-inspired dark security aesthetic:
  - Navigation tabs: Overview, Live Monitoring, Camera Management, Detection, Analytics, Heatmaps, Risk, Alerts, Reports, Settings.
  - Prominent Active Organization Badge & Operator Role display.
  - Seamless organization switcher for multi-membership operators.
  - Maximized surveillance viewport for the 2×2 CCTV Grid and Focus Feed.
- **Safety Gate:** Camera feeds, tracking overlays, and alerts operate flawlessly.

### Phase 5 — Full Integration & Validation
- Execute end-to-end multi-tenant validation with two isolated test organizations:
  - *Organization A:* "AMC Engineering College" (4 cameras, Operator A).
  - *Organization B:* "Metro Transit Command" (2 cameras, Operator B).
- Validate that Operator A cannot see Operator B's cameras, alerts, reports, or streams.
- Validate that logging out in one browser tab does not affect another user's active session.
- Run complete regression suite across all existing test files.

---

## 3. Rollback & Safety Procedures

1. **Pre-Modification Backups:** Every file modified during Phases 1–5 will be backed up to `backups/crowdpatrol_v2/` prior to editing.
2. **Database Isolation:** Automated tests will run against an in-memory SQLite database (`:memory:`) or temporary test file (`data/test_tenants.db`). Never run tests against production stores.
3. **Rollback Script:** A single command can restore pre-Phase 1 files from `backups/crowdpatrol_v2/`.
4. **Git Safety:** No forced resets (`git reset --hard`) or destructive cleanups.

---

## 4. Execution Commands

### Launch CROWDPatrol 2.0 (Streamlit):
```powershell
$env:PYTHONPATH = "."
streamlit run dashboard/simple_dashboard.py --server.port 8501
```

### Run Regression Test Suite:
```powershell
python -m pytest tests/ -v
```
