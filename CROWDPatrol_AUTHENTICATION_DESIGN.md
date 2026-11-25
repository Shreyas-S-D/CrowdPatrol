# CROWDPatrol 2.0 — Authentication & Session Security Specification

**Product:** CROWDPatrol  
**Security Standard:** OWASP ASVS v4.0 Level 2 Compliant Specification  
**Version:** 2.0.0-PROPOSED  
**Date:** November 23, 2026  

---

## 1. Threat Model & Security Objectives

In an AI surveillance and crowd safety monitoring platform, authentication controls access to physical cameras, incident ledgers, and emergency alert dispatches. 

### Core Threats Mitigated:
1. **Credential Stuffing & Brute Force:** Mitigated by memory-hard password hashing (Scrypt) and IP/username-level progressive lockout throttling.
2. **Account Enumeration:** Mitigated by generic error responses ("Invalid credentials") across login and password reset endpoints.
3. **Session Hijacking & Fixation:** Mitigated by high-entropy cryptographic session tokens, session regeneration upon authentication state transition, and strict server-side TTL expiration.
4. **Unauthorized Tenant Snooping:** Mitigated by server-side membership validation on every single request.
5. **Windows Smart App Control Interference:** Mitigated by utilizing standard library `hashlib.scrypt` and `secrets`, avoiding external compiled C/Rust `.pyd` dependencies that trigger Windows Code Integrity blocks.

---

## 2. Password Hashing Architecture

### Algorithm: Scrypt (RFC 7914)
- **Implementation:** Python standard library `hashlib.scrypt`.
- **Parameters:**
  - $N$ (CPU/memory cost factor): `16384` ($2^{14}$)
  - $r$ (block size): `8`
  - $p$ (parallelization factor): `1`
  - Output Key Length: `64` bytes (512 bits)
  - Salt: `16` bytes generated via cryptographically secure random bytes (`os.urandom(16)`).
- **Encoded Storage Format:**
  `$scrypt$N=16384,r=8,p=1$<salt_hex>$<hash_hex>`
- **Verification Protocol:**
  Constant-time string comparison (`hmac.compare_digest`) to prevent timing side-channel attacks.

```python
import os
import hmac
import hashlib

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, maxmem=0)
    return f"$scrypt$N=16384,r=8,p=1${salt.hex()}${key.hex()}"

def verify_password(password: str, hashed_str: str) -> bool:
    try:
        parts = hashed_str.split("$")
        # format: ['', 'scrypt', 'N=16384,r=8,p=1', salt_hex, key_hex]
        salt = bytes.fromhex(parts[3])
        expected_key = bytes.fromhex(parts[4])
        computed_key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, maxmem=0)
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False
```

---

## 3. Session Management & Anti-Fixation

Streamlit's default `st.session_state` is ephemeral to a browser connection. To provide enterprise-grade authentication that survives page reruns and prevents session fixation:

1. **Session Token Generation:**
   - On successful authentication, generate a 256-bit entropy token using `secrets.token_urlsafe(32)`.
   - Store the active session record in the persistent session store:
     ```python
     {
         "session_id": "...",
         "user_id": "usr_...",
         "active_org_id": "org_...",
         "ip_address": "...",
         "created_at": "ISO8601",
         "last_activity_at": "ISO8601",
         "expires_at": "ISO8601"
     }
     ```
2. **Session Regeneration (Anti-Fixation):**
   - The session token is regenerated immediately upon login, organization switch, or password change.
   - Any previous session token associated with that connection is invalidated in the database.
3. **Session Inactivity Timeout:**
   - Sessions expire after **4 hours of inactivity** or **12 hours absolute duration**.
4. **Safe Streamlit Session Sync:**
   - Session state stores the authenticated user ID and verified tenant memberships.
   - Every sensitive data fetch validates that `st.session_state.auth_user` still exists, is active, and possesses authorized membership in `st.session_state.active_organization_id`.

---

## 4. Rate Limiting & Brute-Force Throttling

To protect operator accounts from automated brute-force attacks:
- **Lockout Rule:** 5 consecutive failed login attempts for the same username or IP within a 15-minute window triggers a **10-minute lockout**.
- **Audit Logging:** Every failed attempt records `ip_address`, `attempted_username`, `timestamp`, and `failure_reason`.
- **Response Consistency:** When an account is locked out, the UI displays:
  `"Too many failed login attempts. Account temporarily locked for security. Please try again later."`

---

## 5. Password Reset Flow (Single-Use Token)

```
User Requests Reset -> Generate 256-bit Cryptographic Token -> Store Token (SHA-256 Hashed, 15-min TTL)
                                                                   |
User Submits New Password <- Verify Token Expiration & Single-Use <- User Clicks Secure Link / Submits Token
         |
Invalidate Token -> Update Scrypt Password Hash -> Invalidate All Active User Sessions -> Audit Event
```

---

## 6. Controlled Invitation-Based Registration

Unrestricted public registration is disabled by default to prevent unauthorized access to surveillance resources.

### Provisioning Hierarchy:
1. **Platform Administrator:**
   - Creates new Organization record (`org_amc_campus`, `org_stadium_south`).
   - Generates an Invitation Token for the Organization Administrator (`inv_...`).
2. **Organization Administrator:**
   - Receives invitation link with single-use cryptographic token.
   - Completes account profile and sets secure password.
   - Issues invitation tokens for internal Operators and Viewers within their organization.

---

## 7. Role-Based Access Control (RBAC) Matrix

| Permission / Action | PLATFORM_ADMIN | ORG_ADMIN | OPERATOR | VIEWER |
| :--- | :---: | :---: | :---: | :---: |
| **Manage Organizations** | Full | None | None | None |
| **Invite & Manage Org Users** | None | Full | None | None |
| **View Live Surveillance Feeds** | Org-Scoped | Org-Scoped | Org-Scoped | Org-Scoped |
| **Add / Reconfigure Cameras** | None | Full | View Only | View Only |
| **Start / Stop Monitoring Pipeline**| None | Yes | Yes | No |
| **Acknowledge Alerts** | None | Yes | Yes | No |
| **Resolve Alerts with Note** | None | Yes | Yes | No |
| **Configure SMTP / Notification Rules**| None | Full | View Only | None |
| **Export Incident Reports** | Aggregate Only | Full | Full | View Only |
| **View Organization Audit Logs** | Global | Org-Scoped | None | None |

*Principle of Least Privilege:* Platform Administrators manage infrastructure and organization lifecycle, but do not have casual access to private camera feeds without explicit organization membership.
