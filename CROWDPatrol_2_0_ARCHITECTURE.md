# CROWDPatrol 2.0 — System Architecture Specification

**Product:** CROWDPatrol — Intelligent Multi-Tenant Crowd Safety & Risk Intelligence Platform
**Version:** 2.0.0-PROPOSED (Phase 0 Audit)
**Date:** November 23, 2026
**Status:** ARCHITECTURAL SPECIFICATION & AUDIT COMPLETE — PENDING IMPLEMENTATION APPROVAL

---

## 1. System Vision & Architecture Paradigm

CROWDPatrol 2.0 elevates the proven computer vision surveillance core of CrowdPatrol into an enterprise-grade, multi-tenant public safety intelligence platform. The architecture transitions from a single-tenant local prototype into a secure, multi-organization operational command center while strictly preserving the existing, working AI inference pipeline.

### Architectural Core Principles:
1. **Source of Truth:** The Streamlit application (`dashboard/simple_dashboard.py`) is the primary source of truth. The architecture is a controlled evolution, **not a greenfield rewrite**.
2. **Strict Multi-Tenancy:** Complete logical isolation across organizations (data, cameras, alerts, notifications, and analytics).
3. **Defense in Depth:** Zero client-side authorization trust. Tenant boundaries are enforced in the service and data-access layers.
4. **AI Pipeline Integrity:** YOLOv8, DeepSORT, MobileNetV2, optical flow, density mapping, risk scoring, and alert generation remain bit-for-bit identical to Phase 11.
5. **Operating System Safety:** Windows Smart App Control compliance is strictly maintained by relying on standard library cryptography and pure Python components without unverified binary `.pyd` extensions.

---

## 2. End-to-End User Experience & Navigation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PUBLIC CINEMATIC LANDING PAGE                         │
│  - Hero: "SEE THE CROWD. BEFORE THE RISK."                                  │
│  - 5-Chapter Storytelling: The Problem -> Intelligence -> Awareness ->      │
│    Response -> Platform                                                     │
│  - Interactive AI Capabilities & Technology Showcase                        │
│  - Strict Privacy Guard: Zero organizational/live surveillance data exposed │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Action: "Enter Command Center"
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                        SECURE AUTHENTICATION PORTAL                         │
│  - Secure Login (Username/Email + Scrypt Password Hash)                     │
│  - Rate-Limited Login Throttling & Audit Logging                            │
│  - Password Reset via Expiring Single-Use Cryptographic Tokens             │
│  - Controlled Registration via Administrator Invitation Tokens              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Authenticated Session Established
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    ORGANIZATION WORKSPACE ROUTER                            │
│  - Inspect Authenticated User's Memberships Server-Side                     │
│  - Single Organization: Direct Auto-Routing                                 │
│  - Multiple Organizations: Authorized Workspace Selection Grid              │
│  - Enforce Active Tenant Context in Cryptographic Session State             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Scoped to Active Tenant Context
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                   PRIVATE CROWDPATROL COMMAND CENTER                        │
│  - 10 Enterprise Tabs: Overview, Live Monitoring, Camera Management,       │
│    Detection, Analytics, Heatmaps, Risk, Alerts, Reports, Settings          │
│  - Strict Data Scoping: Queries, Camera Streams, Alerts, History           │
│  - Active Organization Identifier & Operator Role Displayed                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            STREAMLIT PRESENTATION LAYER                     │
│                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │ Public Landing Page  │  │ Authentication Portal│  │ Command Center    │  │
│  │ (Cinematic Showcase) │  │ (Login, Reset, Invite│  │ Dashboard (10 Tabs│  │
│  └──────────┬───────────┘  └──────────┬───────────┘  └─────────┬─────────┘  │
│             │                         │                        │            │
│             └─────────────────────────┼────────────────────────┘            │
│                                       ▼                                     │
│                     DESIGN SYSTEM & UI TOKEN CONTROLLER                     │
│                (#050816, Glassmorphism, Illumination, Badges)                │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                       APPLICATION & SECURITY CONTROLLER                     │
│                                                                             │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │ Session & Identity Guard         │  │ Role-Based Access Control (RBAC) │ │
│  │ - Scrypt Password Verifier       │  │ - PLATFORM_ADMIN                 │ │
│  │ - Session Expiration Tracker     │  │ - ORG_ADMIN                      │ │
│  │ - Anti-Fixation Session Token    │  │ - OPERATOR / VIEWER              │ │
│  └──────────────────────────────────┘  └──────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Tenant Context Scope Resolver (Server-Side Organization Resolution)    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                     MULTI-TENANT DATA ACCESS LAYER (DAL)                    │
│                                                                             │
│  - Isolated Scoped Queries (WHERE organization_id = :active_org_id)         │
│  - Schema Entities: Organizations, Users, Memberships, Cameras, Alerts,    │
│    Analytics Snapshots, Audit Logs, Notification Configs                   │
│  - Storage Engine: SQLite (Local Dev/Isolated Tests) / PostgreSQL Ready     │
│  - File System Scoping: data/tenants/<org_id>/videos/                       │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                     MULTI-CAMERA AI INFERENCE ORCHESTRATION                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ MultiCameraManager (Tenant-Scoped Pipeline Controller)                │  │
│  │ - Isolated CameraState instances per tenant camera                    │  │
│  │ - Dynamic Config Loader (config/tenants/<org_id>/cameras.json)        │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                      │
│  ┌───────────────────────────────────┴───────────────────────────────────┐  │
│  │ Core Vision Engine (100% Preserved)                                   │  │
│  │ - YOLOv8n / Head v4 (640×640 input, conf 0.35 / 0.25)                │  │
│  │ - DeepSORT Tracker + MobileNetV2 Channels-Last Feature Embedder       │  │
│  │ - Farneback Optical Flow Motion Analyzer                              │  │
│  │ - 4×4 Spatial Grid Density Estimator & Thermal Heatmap Generator      │  │
│  │ - Multi-Stage Dynamic Risk Assessor                                   │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                      │
│  ┌───────────────────────────────────┴───────────────────────────────────┐  │
│  │ External Integrations Layer                                           │  │
│  │ - AlertManager (Active -> Acknowledged -> Resolved lifecycle)         │  │
│  │ - NotificationDispatcher (SMTP Gmail with HTML templates, Twilio SMS) │  │
│  │ - Firebase Realtime Database Telemetry Synchronization                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. State Management Architecture

Streamlit executes by re-running the script on user interaction. To maintain high-fidelity multi-tenancy and live video streaming without state pollution, the state architecture is partitioned into three tiers:

### 1. Browser/Connection State (`st.session_state`)
- `session_id`: Unique cryptographically random session identifier.
- `auth_user`: Active authenticated user object (id, username, email).
- `active_organization_id`: Current active tenant ID (validated server-side).
- `user_role`: Active role within the selected tenant.
- `multi_cam`: The active tenant-scoped `MultiCameraManager` instance.
- `telemetry_history`: Circular deques (30 frames) for UI charts.

### 2. Global Persistent State (Relational Database)
- Manages durable state that spans across sessions:
  - Users, Organizations, and Memberships.
  - Camera definitions and configurations.
  - Historical alerts and resolution logs.
  - Audit trail of administrative and security events.

### 3. Ephemeral AI Inference State (In-Memory per Tenant)
- Video capture handles (`cv2.VideoCapture`).
- DeepSORT track states and Kalman filter covariance matrices.
- Frame buffers and current thermal heatmaps.
- Staggered round-robin scheduling counters.

---

## 5. Performance Budget & Resource Allocations

On commodity hardware (e.g. Intel Core i7-13700H, CPU-only execution):
- **Memory Footprint:** < 1.8 GB RAM per active surveillance session.
- **Inference Budget:**
  - Focus Feed: ~4.15 YOLO FPS, ~13.4 Display FPS.
  - 4-Camera Grid: ~0.95 YOLO FPS per camera (staggered stride), ~3.6 Display FPS.
- **HUD & Annotation Overhead:** < 0.5 ms per frame using sub-region ROI alpha blending.
- **Database Query Latency:** < 5 ms for tenant-scoped relational queries (indexed by `organization_id`).

---

## 6. Compatibility & Coexistence with Previous Implementations

- **Experimental React/Starlette Application:** Remains completely preserved in `frontend/` and `backend/`. Not used as primary execution target, but maintained intact for future headless microservice deployment.
- **Streamlit Source of Truth:** `dashboard/simple_dashboard.py` and `dashboard/landing_page.py` are extended and refactored into modular components without breaking single-tenant fallback functionality.
