# CROWDPatrol 2.0 — Security Architecture & Test Strategy Report

**Product:** CROWDPatrol  
**Scope:** Multi-Tenant Isolation, Authentication & Authorization Assurance  
**Version:** 2.0.0-PROPOSED  
**Date:** November 23, 2026  

---

## 1. Security Architecture Summary

CROWDPatrol 2.0 enforces strict multi-tenant boundaries and authentication controls at the data and service layers. Security is treated as an architectural guarantee rather than an afterthought.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL UNTRUSTED INPUT                           │
│  (Browser requests, Streamlit session inputs, URL params, video file uploads)│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. PERIMETER & SESSION VALIDATION                                           │
│  - Validate cryptographically random 256-bit session token.                 │
│  - Verify session timestamp against inactivity TTL (4 hours).               │
│  - Check client IP against rate-limiting lockout ledger.                    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. SERVER-SIDE TENANT CONTEXT RESOLUTION                                     │
│  - Retrieve authenticated user ID from server-side session.                 │
│  - Query database: Does user hold active membership in target organization? │
│  - If membership invalid or missing: Reject immediately (403 Forbidden).    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. ROLE-BASED ACCESS CONTROL (RBAC) GUARD                                   │
│  - Check requested action against role matrix:                              │
│    (PLATFORM_ADMIN, ORG_ADMIN, OPERATOR, VIEWER).                           │
│  - Unauthorized action: Block and record in audit log.                      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. FORCED TENANT-SCOPED DATA ACCESS LAYER (DAL)                             │
│  - All SQL queries parameterized with :active_organization_id.              │
│  - File uploads strictly restricted to data/tenants/<org_id>/videos/.       │
│  - Path traversal checks (resolve() prefix matching).                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Security Test Matrix

The following comprehensive automated security test suite (`tests/test_multitenant_security.py`) will be executed during Phase 5 validation:

### 2.1 Authentication & Password Security Tests

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `SEC-AUTH-01` | Password hashing with Scrypt | Generates valid `$scrypt$` hash with 16-byte random salt and 64-byte key; plaintext is never stored. |
| `SEC-AUTH-02` | Password verification timing attack resistance | `verify_password()` uses `hmac.compare_digest` in constant time; returns True for correct password, False for incorrect. |
| `SEC-AUTH-03` | Brute-force rate limiting | 5 consecutive failed logins for the same username triggers exponential lockout; 6th attempt rejected immediately. |
| `SEC-AUTH-04` | Session fixation prevention | Successful login regenerates session ID; old session ID is completely invalidated. |
| `SEC-AUTH-05` | Inactivity session expiration | Sessions older than TTL (4 hours) are automatically invalidated, redirecting user to login. |
| `SEC-AUTH-06` | Single-use password reset tokens | Token expires in 15 minutes; token cannot be reused after a successful reset. |

### 2.2 Multi-Tenant Data Isolation Tests

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `SEC-TEN-01` | Cross-tenant camera query attempt | User from Tenant A requesting Tenant B's `camera_id` via DAL receives `None` / `PermissionDenied`. |
| `SEC-TEN-02` | Cross-tenant camera reconfiguration | User from Tenant A attempting to modify Tenant B's camera stream is rejected with security violation. |
| `SEC-TEN-03` | Cross-tenant alert acknowledgment | Operator from Tenant A attempting to acknowledge Tenant B's active alert is blocked; alert remains unacknowledged in Tenant B. |
| `SEC-TEN-04` | Cross-tenant alert resolution | Operator from Tenant A attempting to resolve Tenant B's alert is blocked; history remains untampered. |
| `SEC-TEN-05` | Cross-tenant analytics isolation | Analytics query for Tenant A calculates density/risk metrics exclusively from Tenant A's cameras. |
| `SEC-TEN-06` | Cross-tenant file upload path traversal | Filename with `../../tenant_b/video.mp4` is caught by path validator and rejected; cannot write or read across tenant directories. |
| `SEC-TEN-07` | Cross-tenant notification leakage | Tenant A cannot view Tenant B's email recipient list or trigger test emails on Tenant B's behalf. |

### 2.3 Role-Based Authorization Tests

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `SEC-RBAC-01` | Viewer role starts monitoring pipeline | Action blocked; viewers possess read-only feed observation privileges. |
| `SEC-RBAC-02` | Viewer role acknowledges active emergency | Action blocked; alert acknowledgement requires Operator or Org Admin role. |
| `SEC-RBAC-03` | Operator role invites new user to organization | Action blocked; user provisioning requires Org Admin role. |
| `SEC-RBAC-04` | Org Admin attempts to access another organization | Blocked by server-side membership check unless holding dual membership. |

---

## 3. Audit Logging Specification

All security-sensitive operations are durably recorded in the `audit_logs` table:

```sql
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36),
    user_id VARCHAR(36),
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(50),
    ip_address VARCHAR(45),
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Logged Actions:
- `AUTH_LOGIN_SUCCESS` / `AUTH_LOGIN_FAILURE`
- `AUTH_ACCOUNT_LOCKED`
- `AUTH_PASSWORD_RESET_REQUESTED` / `AUTH_PASSWORD_RESET_SUCCESS`
- `TENANT_WORKSPACE_SWITCHED`
- `CAMERA_ADDED` / `CAMERA_RECONFIGURED` / `CAMERA_DELETED`
- `MONITORING_STARTED` / `MONITORING_STOPPED`
- `ALERT_ACKNOWLEDGED` / `ALERT_RESOLVED`
- `USER_INVITED` / `USER_ROLE_CHANGED`
- `CROSS_TENANT_VIOLATION_ATTEMPT` (Logged at ALERT level with IP and user context)
