# ICM / Siebel REST API — Deep Reference

Siebel CRM (branded internally as ICM — Integrated Case Management) is the system of record for all income assistance client data. MySS 2.0 communicates with Siebel exclusively through a REST API layer. This document covers the data model, ownership boundaries, resilience patterns, error codes, authentication, and the mapping from legacy WCF operations to new REST calls.

For the day-to-day guide on *changing* the Siebel integration, see [`docs/guides/updating-siebel-integration.md`](../guides/updating-siebel-integration.md).

---

## Siebel Data Model

MySS 2.0 works with five core Siebel object types. Each has a distinct role and a defined data flow direction.

| Siebel Object | Description | MySS Usage | Data Flow |
|---|---|---|---|
| **Contact** | A person record in ICM, identified by `bceid_guid`. Holds tombstone data: name, address, phone, SIN, PHN, date of birth. | Read on every authenticated session to populate the profile header. Written when the client updates account info. | Read-heavy; writes via `PUT /contacts/{bceid_guid}/tombstone` |
| **Case** | An income assistance case linked to a Contact. Has status (Open, Closed, Suspended) and a `case_number`. | Case number is the key for payment, banners, and monthly reports. | Read-only from MySS; status changes happen via SRs in Siebel |
| **Service Request (SR)** | A structured request attached to a Case — e.g., change of address, declaration, rapid reinstatement. Has type, status, and associated Activities. | Created, listed, and cancelled by clients. Form answers submitted via `finalize`. | Full CRUD: create, read, cancel |
| **Activity** | A task or note attached to an SR or Case. Tracks worker actions and client submissions. | Surfaced in SR detail views; not directly created by MySS. | Read-only from MySS |
| **Asset** | A benefit entitlement record (e.g., bus pass, health supplement). Linked to a Case. | Read to determine eligibility for specific service request types. | Read-only from MySS |

---

## Data Ownership Boundaries

Not all data lives in Siebel. Knowing who owns what prevents accidental duplication and stale-read bugs.

| Data | Owner | Notes |
|---|---|---|
| BCeID GUID | Keycloak / BCeID | Primary identifier passed through; never stored in either DB |
| Session state (JWT claims, CSRF) | Redis | 900-second TTL; sourced from `REDIS_SESSION_TTL_SECONDS` ConfigMap |
| Banner / notification cache | Redis | 300-second TTL (`REDIS_CACHE_BANNERS_TTL_SECONDS`); invalidated on session login |
| Payment info cache | Redis | 3600-second TTL (`REDIS_CACHE_PAYMENT_TTL_SECONDS`); read-heavy, rarely changes |
| Registration workflow state | PostgreSQL (`RegistrationSession`) | Tracks multi-step registration before ICM record exists |
| Uploaded file blobs (pre-scan) | OpenShift PVC | Temporary; moved to Siebel attachment store on AV clearance |
| Client tombstone (name, address, SIN, PHN, DOB) | Siebel (Contact) | Source of truth; fetched on login and cached in JWT claims |
| Case status, SR list, payment history | Siebel (Case / SR) | Never duplicated in PostgreSQL |
| Audit / worker access log | PostgreSQL | Compliance requirement; append-only |
| Application feature flags | PostgreSQL | Managed by ops team; not sourced from Siebel |

**Rule:** If a piece of data has a Siebel owner listed above, do not write it to PostgreSQL. The one exception is the audit log — it records *that* a worker accessed data, not the data itself.

---

## Circuit Breaker

All HTTP calls from `ICMClient` to Siebel pass through an async circuit breaker (`_AsyncCircuitBreaker` in `client.py`). The breaker protects the application from cascading failures when Siebel is slow or down.

**Configuration (from `openshift/configmap.yaml`):**

- Failure threshold: **5 consecutive failures**
- Recovery timeout: **30 seconds**

**State diagram:**

```
                  5 consecutive failures
  CLOSED ─────────────────────────────────► OPEN
    ▲                                         │
    │                                         │ 30 seconds elapse
    │                                         ▼
    │                                      HALF_OPEN
    │         probe succeeds                  │
    └─────────────────────────────────────────┘
                                              │
                        probe fails           │
                              ┌───────────────┘
                              ▼
                            OPEN  (reset_timeout restarts)
```

**State semantics:**

| State | Behaviour |
|---|---|
| **CLOSED** | Normal operation. Failures increment a counter. Success resets the counter to 0. |
| **OPEN** | All calls immediately raise `ICMServiceUnavailableError` — no network attempt made. |
| **HALF_OPEN** | One probe call is allowed through. Only one probe at a time (`_probe_in_flight` flag). If the probe succeeds: transition to CLOSED. If the probe fails: transition back to OPEN immediately. |

**Retry layer (separate from circuit breaker):**

Before the circuit breaker records a failure, the retry layer (`tenacity`) attempts the call up to **3 times** with exponential backoff (1s, 2s, 4s maximum). Retries only occur on:
- HTTP 5xx responses
- `httpx.ConnectError`
- `httpx.TimeoutException`

4xx responses and typed `ICMError` exceptions are **not retried** — they are passed through immediately.

**Combined flow for a single logical call:**

```
Client code calls _get() / _post() / etc.
  → _call_with_breaker()
    → circuit breaker checks state
      → if OPEN: raise ICMServiceUnavailableError immediately
      → if HALF_OPEN and probe in flight: raise ICMServiceUnavailableError
    → _call() with tenacity retry wrapper (up to 3 attempts)
      → _ensure_token() — refresh if within 60s of expiry
      → HTTP request to Siebel with Bearer token
      → on 5xx or connection error: tenacity retries
      → on 4xx: map_icm_error() → typed exception, no retry
      → on success: return response.json()
    → circuit breaker records success or failure
```

---

## ICM Error Codes

Siebel returns structured error responses with an `errorCode` field. `error_mapping.py` maps these to typed Python exceptions. FastAPI router code catches these exceptions and returns appropriate HTTP status codes to the frontend.

| Error Code | Python Exception | Meaning | Default HTTP Response |
|---|---|---|---|
| `ICM_ERR_REVOKED` | `ICMAccessRevokedError` | The client's access to the portal has been revoked in ICM | 403 Forbidden |
| `ICM_ERR_NO_CASE` | `ICMCaseNotFoundError` | No active income assistance case for this contact — new applicant | 404 → redirect to registration |
| `ICM_ERR_NO_CONTACT` | `ICMContactNotFoundError` | BCeID GUID not yet linked to an ICM contact record | 404 → account pending setup |
| `ICM_ERR_MULTI_CONTACTS` | `ICMMultipleContactsError` | Multiple ICM contact records matched this BCeID — manual resolution needed | 409 Conflict → show error page |
| `ICM_ERR_CLOSED_CASE` | `ICMClosedCaseError` | Case is closed; limited read-only access is permitted | 200 with restricted view |
| `ICM_ERR_ACTIVE_SR_CONFLICT` | `ICMActiveSRConflictError` | An active SR of the same type already exists — duplicate prevention | 409 Conflict |
| `ICM_ERR_SR_ALREADY_WITHDRAWN` | `ICMSRAlreadyWithdrawnError` | The SR was already withdrawn; the cancel operation is a no-op | 409 Conflict |
| *(unknown code)* | `ICMError` (base) | Unrecognised error code from Siebel | 502 Bad Gateway |
| *(circuit open)* | `ICMServiceUnavailableError` | Circuit breaker is open or all retries exhausted | 503 Service Unavailable |

**Error response shape from Siebel (expected):**

```json
{
  "errorCode": "ICM_ERR_NO_CASE",
  "message": "No active case found for the given profile identifier"
}
```

If the response body cannot be parsed as JSON or does not contain `errorCode`, `map_icm_error()` falls back to raising an `httpx.HTTPStatusError` which the retry layer handles.

---

## Authentication with Siebel

`ICMClient` uses **OAuth2 client credentials flow** to authenticate with Siebel. There is no user-level delegation — the application authenticates as a service principal.

**Flow:**

```
1. POST {ICM_TOKEN_URL}
   Content-Type: application/x-www-form-urlencoded
   Body: grant_type=client_credentials
         &client_id={ICM_CLIENT_ID}
         &client_secret={ICM_CLIENT_SECRET}

2. Siebel returns:
   {
     "access_token": "eyJ...",
     "expires_in": 3600,
     "token_type": "Bearer"
   }

3. Token cached in memory (_token, _token_expiry).
   Expiry = now + expires_in - 60  (refresh 60 seconds before actual expiry)

4. Every subsequent request:
   Authorization: Bearer {access_token}
```

**Token refresh:** `_ensure_token()` checks `time.monotonic() >= self._token_expiry` before every call. If true, it calls `_fetch_token()` under an `asyncio.Lock` to prevent thundering herd on concurrent requests.

**Secret handling:** The `client_secret` is wrapped in `_SecretStr` to prevent accidental exposure in logs or exception tracebacks. The value is only accessible via `.get()`.

**Credentials source:** Injected at application startup from OpenShift Secrets (see `openshift/secrets-template.yaml`). Never in ConfigMaps or environment variables checked into source control.

**Base URL:** `https://icm.gov.bc.ca/siebel/v1.0` (from `openshift/configmap.yaml`, key `ICM_BASE_URL`).

---

## Legacy WCF to New REST Mapping

The legacy application called Siebel via two WCF services: `MCP_MC_Services` (everything except files) and `MCP_Attachment_Services` (file operations). The new stack calls Siebel directly over REST using typed client classes that all extend `ICMClient`.

| Legacy WCF Operation | Legacy Service | New REST Call | New Client Class |
|---|---|---|---|
| `GetTombstone(bceid_guid)` | `MCP_MC_Services` | `GET /contacts/{bceid_guid}/tombstone` | `SiebelProfileClient` |
| `ValidatePIN(bceid_guid, pin)` | `MCP_MC_Services` | `POST /contacts/{bceid_guid}/validate-pin` | `SiebelProfileClient` |
| `UpdateTombstone(bceid_guid, data)` | `MCP_MC_Services` | `PUT /contacts/{bceid_guid}/tombstone` | `SiebelProfileClient` |
| `GetProfile(bceid_guid)` | `MCP_MC_Services` | `GET /contacts/{bceid_guid}/profile` | `SiebelProfileClient` |
| `LinkProfile(bceid_guid, data)` | `MCP_MC_Services` | `POST /contacts/{bceid_guid}/link` | `SiebelProfileClient` |
| `RegisterNewApplicant(data)` | `MCP_MC_Services` | `POST /registrations/new` | `SiebelRegistrationClient` |
| `RegisterExistingClient(data)` | `MCP_MC_Services` | `POST /registrations/existing` | `SiebelRegistrationClient` |
| `GetServiceRequests(profile_id)` | `MCP_MC_Services` | `GET /service-requests?profile_id={id}` | `SiebelSRClient` |
| `GetServiceRequestDetail(sr_id)` | `MCP_MC_Services` | `GET /service-requests/{sr_id}` | `SiebelSRClient` |
| `CreateServiceRequest(type, profile_id)` | `MCP_MC_Services` | `POST /service-requests` | `SiebelSRClient` |
| `CancelServiceRequest(sr_id, reason)` | `MCP_MC_Services` | `POST /service-requests/{sr_id}/cancel` | `SiebelSRClient` |
| `SubmitFormAnswers(sr_id, answers)` | `MCP_MC_Services` | `POST /service-requests/{sr_id}/finalize` | `SiebelSRClient` |
| `GetPaymentInfo(case_number)` | `MCP_MC_Services` | `GET /cases/{case_number}/payment` | `SiebelPaymentClient` |
| `GetChequeSchedule(case_number)` | `MCP_MC_Services` | `GET /cases/{case_number}/cheque-schedule` | `SiebelPaymentClient` |
| `GetT5007Slips(profile_id)` | `MCP_MC_Services` | `GET /profiles/{profile_id}/t5007-slips` | `SiebelPaymentClient` |
| `GetBanners(case_number)` | `MCP_MC_Services` | `GET /cases/{case_number}/banners` | `SiebelNotificationClient` |
| `GetMessages(profile_id)` | `MCP_MC_Services` | `GET /messages?profile_id={id}` | `SiebelNotificationClient` |
| `GetMessageDetail(msg_id)` | `MCP_MC_Services` | `GET /messages/{msg_id}` | `SiebelNotificationClient` |
| `MarkMessageRead(msg_id)` | `MCP_MC_Services` | `POST /messages/{msg_id}/mark-read` | `SiebelNotificationClient` |
| `SignAndSendMessage(msg_id, pin)` | `MCP_MC_Services` | `POST /messages/{msg_id}/sign` | `SiebelNotificationClient` |
| `UploadAttachment(sr_id, file)` | `MCP_Attachment_Services` | `POST /service-requests/{sr_id}/attachments` | `SiebelAttachmentClient` |
| `GetAttachment(attachment_id)` | `MCP_Attachment_Services` | `GET /attachments/{attachment_id}` | `SiebelAttachmentClient` |
| `DeleteAttachment(sr_id, attach_id)` | `MCP_Attachment_Services` | `DELETE /service-requests/{sr_id}/attachments/{attachment_id}` | `SiebelAttachmentClient` |

**Key differences from WCF:**

- **No service proxy factory:** Legacy code instantiated WCF client proxies inside `Utility.WCFWS_using()` lambdas, managing credential injection per-call. `ICMClient` is a long-lived async HTTP client; credentials are injected once at construction and tokens are refreshed automatically.
- **Typed exceptions instead of fault codes:** Legacy code checked string error codes in WCF fault exceptions. New code catches typed `ICMError` subclasses.
- **Async throughout:** All ICM calls are `async def`; there is no sync wrapper.
- **Circuit breaker built in:** Legacy code had no circuit breaker — Siebel outages caused thread-pool exhaustion under load. The new circuit breaker makes outage behaviour explicit and fast.
