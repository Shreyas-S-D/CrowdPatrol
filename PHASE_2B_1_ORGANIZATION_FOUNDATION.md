# CrowdPatrol 2.0 — Phase 2B.1: Organization & Membership Foundation

**Status:** APPROVED FOR EVALUATION  
**Date:** November 23, 2026  
**Subsystem:** Core Multi-Tenancy Data Model & Authorization Services  
**Schema Version:** 2  

---

## 1. Executive Summary

Phase 2B.1 establishes the foundational multi-tenant data architecture and role-based access control (RBAC) subsystem for CrowdPatrol 2.0. Following the approved Phase 2A authentication hardening (scrypt password hashing, timing-safe evaluations, atomic failed-login lockout tracking, and token hashing), Phase 2B.1 introduces strict organizational boundary isolation, relational memberships, and a server-side tenant context resolution engine.

### Key Deliverables Completed:
1. **Schema Migration v2**: Upgraded SQLite database schema (`SCHEMA_VERSION = 2`) with atomic transactional migration creating `organizations`, `organization_memberships`, and `organization_audit_events` tables alongside 8 performance and integrity indexes.
2. **Organization Service (`src/auth/organization_service.py`)**: Business service managing multi-tenant organization creation (restricted to platform administrators), normalized URL-safe slug validation, metadata updates, and status transitions (`ACTIVE`, `SUSPENDED`, `ARCHIVED`).
3. **Membership Service (`src/auth/organization_service.py`)**: Membership lifecycle management enforcing the **Last Active ORG_ADMIN Protection** safeguard against demotion, suspension, or removal of the last administrator.
4. **Server-Side Tenant Context Resolution Engine**: Fail-closed tenant context resolver ensuring client-supplied tenant identifiers are never trusted without server-side membership validation.
5. **Non-Repudiable Audit Event Logging**: Structured audit logging capturing all administrative, organizational, and membership changes.
6. **Comprehensive Automated Test Suite (`tests/test_organizations.py`)**: 25 isolated tests covering slug normalization, organization lifecycle, membership CRUD, last admin protection, RBAC rules, cross-tenant isolation, and audit emission.
7. **Zero Regressions**: 100% pass rate across all test suites (25/25 org tests, 38/38 auth tests, 6/6 landing page tests, and standalone Streamlit AppTest run with 0 exceptions).

---

## 2. Data Model & Schema Description

The multi-tenant schema is defined in `src/auth/database.py` under schema migration version 2 (`_apply_migration_v2`).

### 2.1 Tables and Constraints

#### `organizations` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `TEXT` | `PRIMARY KEY` | Unique organization identifier (e.g. `org_9a4f2b1c8e3d`) |
| `name` | `TEXT` | `NOT NULL` | Human-readable organization name (2–100 chars) |
| `slug` | `TEXT` | `NOT NULL UNIQUE` | URL-safe normalized slug (`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`) |
| `description` | `TEXT` | `NULL` | Optional organization description |
| `status` | `TEXT` | `NOT NULL DEFAULT 'ACTIVE'` | Status: `ACTIVE`, `SUSPENDED`, `ARCHIVED` |
| `created_at` | `TEXT` | `NOT NULL` | UTC ISO-8601 timestamp |
| `updated_at` | `TEXT` | `NOT NULL` | UTC ISO-8601 timestamp |
| `created_by` | `TEXT` | `NULL REFERENCES users(id)` | User ID of the creator |

#### `organization_memberships` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `TEXT` | `PRIMARY KEY` | Unique membership identifier (e.g. `mem_0d8e7f6a5b4c`) |
| `organization_id`| `TEXT` | `NOT NULL REFERENCES organizations(id) ON DELETE CASCADE` | Associated organization |
| `user_id` | `TEXT` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE` | Enrolled user ID |
| `role` | `TEXT` | `NOT NULL` | Role: `ORG_ADMIN`, `OPERATOR`, `VIEWER` |
| `status` | `TEXT` | `NOT NULL DEFAULT 'ACTIVE'` | Membership status: `ACTIVE`, `INVITED`, `SUSPENDED` |
| `joined_at` | `TEXT` | `NULL` | UTC ISO-8601 timestamp when user activated |
| `created_at` | `TEXT` | `NOT NULL` | UTC ISO-8601 timestamp |
| `updated_at` | `TEXT` | `NOT NULL` | UTC ISO-8601 timestamp |
| *Constraint* | `UNIQUE` | `(organization_id, user_id)` | Prevents duplicate user memberships per organization |

#### `organization_audit_events` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `TEXT` | `PRIMARY KEY` | Unique audit record identifier (e.g. `aud_1b2c3d4e5f6a`) |
| `organization_id`| `TEXT` | `NOT NULL REFERENCES organizations(id) ON DELETE CASCADE` | Target organization ID |
| `actor_user_id` | `TEXT` | `NOT NULL` | User ID of actor performing the mutation |
| `action` | `TEXT` | `NOT NULL` | Action descriptor (e.g. `ORGANIZATION_CREATED`, `MEMBER_ADDED`) |
| `target_type` | `TEXT` | `NOT NULL` | Target entity type (`ORGANIZATION`, `MEMBERSHIP`, `CAMERA`, `SETTINGS`) |
| `target_id` | `TEXT` | `NULL` | Identifier of the affected entity |
| `metadata` | `TEXT` | `NULL` | Structured JSON details of changes |
| `created_at` | `TEXT` | `NOT NULL` | UTC ISO-8601 timestamp |

### 2.2 Relational Indexes
```sql
CREATE INDEX IF NOT EXISTS idx_org_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_org_status ON organizations(status);
CREATE INDEX IF NOT EXISTS idx_org_created_by ON organizations(created_by);
CREATE INDEX IF NOT EXISTS idx_mem_org_id ON organization_memberships(organization_id);
CREATE INDEX IF NOT EXISTS idx_mem_user_id ON organization_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_mem_role ON organization_memberships(role);
CREATE INDEX IF NOT EXISTS idx_mem_status ON organization_memberships(status);
CREATE INDEX IF NOT EXISTS idx_audit_org_created ON organization_audit_events(organization_id, created_at);
```

---

## 3. OrganizationService API Reference

The `OrganizationService` class (`src/auth/organization_service.py`) encapsulates all tenant lifecycle mutations.

### 3.1 `create_organization`
```python
def create_organization(
    self,
    name: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    actor: Optional[User] = None,
    initial_admin_user_id: Optional[str] = None,
) -> Organization
```
- **Authorization**: Strict `PLATFORM_ADMIN` privilege required. Non-platform users raise `PermissionError`.
- **Validation**: Name length 2–100 characters; slug normalized to `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`; slug uniqueness checked against active and non-archived tenants.
- **Initial Admin**: If `initial_admin_user_id` is supplied, an `ORG_ADMIN` membership is automatically provisioned for that user.
- **Audit**: Emits `ORGANIZATION_CREATED` audit event.

### 3.2 `get_organization` & `get_organization_by_slug`
```python
def get_organization(self, org_id: str) -> Optional[Organization]
def get_organization_by_slug(self, slug: str) -> Optional[Organization]
```
- **Retrieval**: Safe lookup by primary ID or normalized slug; returns `None` if not found.

### 3.3 `list_accessible_organizations`
```python
def list_accessible_organizations(self, user: User) -> List[Organization]
```
- **Platform Admins**: Returns all non-archived organizations across the platform.
- **Standard Users**: Returns strictly those organizations where the user holds an active membership.

### 3.4 `update_organization`
```python
def update_organization(
    self,
    org_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    actor: Optional[User] = None,
) -> Organization
```
- **Authorization**: `PLATFORM_ADMIN` or active `ORG_ADMIN` of the organization.
- **Audit**: Emits `ORGANIZATION_UPDATED` audit record with diff metadata.

### 3.5 `suspend_organization`, `reactivate_organization`, `archive_organization`
```python
def suspend_organization(self, org_id: str, actor: Optional[User] = None, reason: Optional[str] = None) -> Organization
def reactivate_organization(self, org_id: str, actor: Optional[User] = None) -> Organization
def archive_organization(self, org_id: str, actor: Optional[User] = None) -> Organization
```
- **Authorization**: Platform administrators only. Non-platform administrators raise `PermissionError`.
- **Audit**: Emits `ORGANIZATION_SUSPENDED`, `ORGANIZATION_REACTIVATED`, or `ORGANIZATION_ARCHIVED`.

---

## 4. MembershipService API Reference

The `MembershipService` class (`src/auth/organization_service.py`) manages tenant user enrollments, role reassignments, and administrative protections.

### 4.1 `add_member`
```python
def add_member(
    self,
    org_id: str,
    user_id: str,
    role: str = "VIEWER",
    actor: Optional[User] = None,
    organization_id: Optional[str] = None
) -> OrganizationMembership
```
- **Authorization**: `PLATFORM_ADMIN` or active `ORG_ADMIN` of the organization.
- **Validation**: Enforces valid role (`ORG_ADMIN`, `OPERATOR`, `VIEWER`). Verifies target user exists. Rejects duplicate enrollments (`ValueError`).
- **Audit**: Emits `MEMBER_ADDED` audit event.

### 4.2 `list_members` & `list_organization_members`
```python
def list_members(self, org_id: str, actor: Optional[User] = None, organization_id: Optional[str] = None) -> List[OrganizationMembership]
def list_organization_members(self, org_id: str, actor: Optional[User] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]
```
- **Authorization**: Active member of the organization or platform admin. Returns typed membership objects or detailed user identity dictionaries.

### 4.3 `change_member_role`
```python
def change_member_role(
    self,
    org_id: str,
    user_id: str,
    new_role: str,
    actor: Optional[User] = None,
    organization_id: Optional[str] = None,
    target_user_id: Optional[str] = None
) -> OrganizationMembership
```
- **Authorization**: `PLATFORM_ADMIN` or active `ORG_ADMIN`.
- **Safeguard**: Prevents demoting the last active `ORG_ADMIN` (`ValueError: Cannot demote the last active ORG_ADMIN`).
- **Audit**: Emits `MEMBER_ROLE_CHANGED` audit event.

### 4.4 `suspend_member` & `reactivate_member`
```python
def suspend_member(self, org_id: str, user_id: str, actor: Optional[User] = None, ...) -> OrganizationMembership
def reactivate_member(self, org_id: str, user_id: str, actor: Optional[User] = None, ...) -> OrganizationMembership
```
- **Safeguard**: Prevents suspending the last active `ORG_ADMIN` (`ValueError: Cannot suspend the last active ORG_ADMIN`).
- **Audit**: Emits `MEMBER_SUSPENDED` and `MEMBER_REACTIVATED` audit records.

### 4.5 `remove_member`
```python
def remove_member(self, org_id: str, user_id: str, actor: Optional[User] = None, ...) -> bool
```
- **Safeguard**: Prevents removing the last active `ORG_ADMIN` (`ValueError: Cannot remove the last active ORG_ADMIN`).
- **Audit**: Emits `MEMBER_REMOVED` audit record.

---

## 5. Role & Capability Matrix

| Operation | `PLATFORM_ADMIN` (or `SUPER_ADMIN`) | `ORG_ADMIN` | `OPERATOR` | `VIEWER` |
| :--- | :---: | :---: | :---: | :---: |
| **Create New Organizations** | Allowed | Denied | Denied | Denied |
| **Suspend / Archive Organizations** | Allowed | Denied | Denied | Denied |
| **View Cross-Organization Directory** | Allowed | Denied | Denied | Denied |
| **Update Org Name & Settings** | Allowed | Allowed | Denied | Denied |
| **Invite & Add Members** | Allowed | Allowed | Denied | Denied |
| **Change Member Roles** | Allowed | Allowed | Denied | Denied |
| **Suspend / Remove Members** | Allowed | Allowed | Denied | Denied |
| **View Organization Audit Logs** | Allowed | Allowed | Denied | Denied |
| **Configure Cameras & Alert Rules** | Allowed | Allowed | Denied | Denied |
| **Start / Stop AI Monitoring Streams**| Allowed | Allowed | Allowed | Denied |
| **Acknowledge Security Alerts** | Allowed | Allowed | Allowed | Denied |
| **View Analytics & Live Telemetry** | Allowed | Allowed | Allowed | Allowed |

*Note: The platform role check (`is_platform_admin`) explicitly recognizes both `PLATFORM_ADMIN` and `SUPER_ADMIN` to maintain backwards compatibility with existing developer/admin credentials.*

---

## 6. Last Active ORG_ADMIN Protection Mechanism

A critical operational requirement in multi-tenant architectures is ensuring an organization is never orphaned without an active administrator.

### Implementation Details:
In `src/auth/database.py`, an atomic query calculates active administrators:
```sql
SELECT COUNT(*) FROM organization_memberships
WHERE organization_id = ? AND role = 'ORG_ADMIN' AND status = 'ACTIVE';
```

In `MembershipService`:
1. **On Demotion (`change_member_role`)**: If target user is `ORG_ADMIN` and `new_role != 'ORG_ADMIN'`, `count_active_org_admins` is evaluated. If count is $\le 1$, the operation fails-closed with `ValueError("Cannot demote the last active ORG_ADMIN.")`.
2. **On Suspension (`suspend_member`)**: If target user is `ORG_ADMIN` with status `ACTIVE`, count is evaluated. If count is $\le 1$, operation raises `ValueError("Cannot suspend the last active ORG_ADMIN.")`.
3. **On Removal (`remove_member`)**: If target user is `ORG_ADMIN` with status `ACTIVE`, count is evaluated. If count is $\le 1$, operation raises `ValueError("Cannot remove the last active ORG_ADMIN.")`.
4. **Permitted Demotion/Removal**: If another active `ORG_ADMIN` exists (`count > 1`), the demotion, suspension, or removal proceeds normally.

---

## 7. Server-Side Tenant Context Resolution Engine

The `resolve_tenant_context` function (`src/auth/organization_service.py`) provides fail-closed resolution of the active organization:

```python
def resolve_tenant_context(
    user: Optional[User],
    requested_org_id: Optional[str] = None,
    requested_slug: Optional[str] = None,
    db: Optional[AuthDatabase] = None
) -> Tuple[Optional[Organization], Optional[OrganizationMembership]]
```

### Security Guarantees:
1. **Never Trusts Client Input**: The client can propose an `org_id` or `slug`, but the resolver queries the database directly to confirm authenticity and relationship.
2. **Fail-Closed on Unenrolled Access**: If a user attempts to access an organization where they do not possess an active membership, a `PermissionError` is raised immediately.
3. **Status Enforcement**:
   - Suspended organization $\rightarrow$ raises `PermissionError("Organization '<name>' is currently suspended.")`.
   - Archived organization $\rightarrow$ raises `PermissionError("Organization '<name>' is archived.")`.
   - Suspended member $\rightarrow$ raises `PermissionError("Membership of user '<username>' in organization '<name>' is SUSPENDED.")`.
4. **Platform Administrator Elevation**: Platform administrators can resolve context for any active organization. If they lack an explicit membership record, a virtual administrative membership is synthesized granting `ORG_ADMIN` operational scope for that organization.
5. **Default Resolution**: If neither `org_id` nor `slug` is requested, the system automatically resolves to the user's primary active enrolled organization.

---

## 8. Non-Repudiable Audit Event Logging

All state modifications are recorded in the `organization_audit_events` table:
- **Event Actions**: `ORGANIZATION_CREATED`, `ORGANIZATION_UPDATED`, `ORGANIZATION_SUSPENDED`, `ORGANIZATION_REACTIVATED`, `ORGANIZATION_ARCHIVED`, `MEMBER_ADDED`, `MEMBER_ROLE_CHANGED`, `MEMBER_SUSPENDED`, `MEMBER_REACTIVATED`, `MEMBER_REMOVED`.
- **Querying**: `db.list_audit_events(organization_id, limit=50)` retrieves events sorted by `created_at DESC`.
- **Metadata**: JSON payload capturing previous vs. new values and actor identity.

---

## 9. Verification & Test Results

### 9.1 Organization & Multi-Tenancy Test Suite (`tests/test_organizations.py`)
```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Shreyas Files\AMC Engineering College\7th sem\Major Project\CrowdPatrol
plugins: anyio-4.14.2
collected 25 items

tests/test_organizations.py::test_slug_normalization_valid PASSED        [  4%]
tests/test_organizations.py::test_slug_normalization_invalid PASSED      [  8%]
tests/test_organizations.py::test_create_organization_by_platform_admin PASSED [ 12%]
tests/test_organizations.py::test_create_organization_unauthorized PASSED [ 16%]
tests/test_organizations.py::test_create_organization_duplicate_slug_rejected PASSED [ 20%]
tests/test_organizations.py::test_get_organization_by_id_and_slug PASSED [ 24%]
tests/test_organizations.py::test_list_accessible_organizations_platform_admin_vs_member PASSED [ 28%]
tests/test_organizations.py::test_update_organization_metadata PASSED    [ 32%]
tests/test_organizations.py::test_organization_status_transitions_and_archival PASSED [ 36%]
tests/test_organizations.py::test_membership_lifecycle_add_list_role_change PASSED [ 40%]
tests/test_organizations.py::test_add_member_duplicate_rejected PASSED   [ 44%]
tests/test_organizations.py::test_last_active_org_admin_protection_demotion PASSED [ 48%]
tests/test_organizations.py::test_last_active_org_admin_protection_suspension PASSED [ 52%]
tests/test_organizations.py::test_last_active_org_admin_protection_removal PASSED [ 56%]
tests/test_organizations.py::test_demote_permitted_when_another_org_admin_exists PASSED [ 60%]
tests/test_organizations.py::test_rbac_permission_helpers PASSED         [ 64%]
tests/test_organizations.py::test_unauthorized_member_management PASSED  [ 68%]
tests/test_organizations.py::test_resolve_tenant_context_success_by_id_and_slug PASSED [ 72%]
tests/test_organizations.py::test_resolve_tenant_context_cross_tenant_access_denied PASSED [ 76%]
tests/test_organizations.py::test_resolve_tenant_context_suspended_org_denied PASSED [ 80%]
tests/test_organizations.py::test_resolve_tenant_context_suspended_member_denied PASSED [ 84%]
tests/test_organizations.py::test_resolve_tenant_context_platform_admin_elevation PASSED [ 88%]
tests/test_organizations.py::test_resolve_tenant_context_default_to_first_accessible_org PASSED [ 92%]
tests/test_organizations.py::test_multi_organization_membership_switching PASSED [ 96%]
tests/test_organizations.py::test_audit_events_emitted PASSED            [100%]

============================= 25 passed in 11.72s =============================
```

### 9.2 Complete Test Suite Summary
| Test Suite | File | Tests Run | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Organization & Multi-Tenancy** | `tests/test_organizations.py` | 25 | **25 PASSED** | 11.72s |
| **Authentication & Security** | `tests/test_auth.py` | 38 | **38 PASSED** | 49.28s |
| **Landing Page & UI Integration** | `tests/test_landing_page.py` | 6 | **6 PASSED** | 23.74s |
| **Streamlit AppTest Standalone** | `dashboard/simple_dashboard.py` | 1 | **APPTEST_SUCCESS (0 exceptions)** | ~1.5s |
| **Total** | | **70** | **70 PASSED (0 Failures)** | |

---

## 10. Preservation Confirmation

The following subsystems and configurations were **strictly preserved and remain 100% untouched**:
- **YOLOv8 Object Detection**: Model configurations, weights (`yolov8n.pt`), image dimensions ($640 \times 640$), person confidence ($0.35$), head mode confidence ($0.25$), and NMS thresholds remain unmodified in `src/detection.py` and `src/experimental_head_mode.py`.
- **DeepSORT Multi-Object Tracking**: Tracking parameters (`max_age=30`, `n_init=3`, `nn_budget=100`, cosine distance metrics) remain untouched in `src/tracking.py`.
- **MobileNetV2 Appearance Embedder**: Cosine distance feature extraction and embedding pipelines remain unmodified.
- **Farneback Optical Flow**: Optical flow matrices and grid velocity computations remain untouched in `src/motion_analysis.py`.
- **Camera Management & Capture**: Multi-camera manager (`src/multi_camera_manager.py`), capture threads (`src/capture.py`), and device enumeration (`src/camera_devices.py`) remain untouched.
- **Alert Dispatching & Notifications**: Firebase Realtime Database sync and Gmail SMTP dispatchers in `src/alert_manager.py` and `src/alerts.py` remain untouched.
- **Landing Page & Dashboard UI**: Landing page presentation, theme constants, and primary Streamlit navigation remain untouched and operational.

---

## 11. Readiness Statement & Next Steps

Phase 2B.1 (Organization & Membership Foundation) is fully implemented, verified, and backed up.

### Current State:
- All core multi-tenant data structures, constraints, services, RBAC checks, and tenant context resolution engines are validated and operational.
- The system is completely prepared for Phase 2B.2 (Organization Workspace UI & Member Invitations).

### Strict Boundary Enforcement:
As directed, implementation has stopped here. **No workspace UI, member invitation flows, or AI monitoring integrations will be initiated until explicit user approval is granted.**
