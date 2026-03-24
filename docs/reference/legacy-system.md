# Legacy MySelfServe — Overview for New Developers

**Purpose:** This document gives you enough context to understand legacy terminology when it appears in requirements documents, Siebel field names, stakeholder conversations, or code comments that reference the old system. It is not a maintenance guide — the legacy application is being replaced, not maintained.

---

## What It Was

MySelfServe (legacy) was an **ASP.NET MVC 5** web application targeting **.NET Framework 4.7.2**, hosted on **IIS on Windows Server**. It served as BC Government's income assistance self-service portal.

Key technology choices:

| Concern | Legacy Technology |
|---|---|
| Web framework | ASP.NET MVC 5 (.NET Framework 4.7.2) |
| Frontend | AngularJS 1.5.9 (bundled with jQuery + Bootstrap) |
| Backend services | WCF clients (`MCP_MC_Services`, `MCP_Attachment_Services`) |
| Authentication | SiteMinder (client) + BCeID (identity) + IDIR (workers) |
| Session state | SQL Server (15-minute timeout) |
| Logging | Microsoft Enterprise Library, daily-rotating log file |
| Configuration | `Web.config` + per-environment transform files |
| Infrastructure | IIS, Windows Server, on-premises |

The application had no direct database access from the web tier — all data operations went through WCF service proxies that called Siebel (ICM) on the backend.

---

## Functional Domains — Legacy Code Mapping

The 10 functional domains carried forward into MySS 2.0 map to the following legacy components:

| Domain | Legacy Controllers | Legacy Helpers |
|---|---|---|
| Registration | `RegistrationController` | `RegistrationHelper` |
| Service Requests | `ServiceRequestsController`, `DynamicFormController` | `ServiceRequestHelper`, `DynamicFormHelper` |
| Monthly Reports | `MonthlyReportsController` | (via `DynamicFormHelper`) |
| Notifications | `NotificationsController`, `MessagesController` | `MessageListHelper` |
| Payment Info | `ChequeInfoController` | (via WCF) |
| Employment Plans | `EmploymentPlansController` | (via WCF) |
| Account Info | `AccountInfoController`, `PINController`, `PhoneController` | `ProfileHelper` |
| Attachments | `AttachmentsController` | `AttachmentHelper` |
| Eligibility | `EligibilityEstimatorController` | (standalone) |
| Admin / Support | `AOLoginController`, `SupportViewController` | `AORegistrationHelper`, `AOServiceRequestHelper` |

### Dynamic Form System

Several domains (Service Requests, Monthly Reports, Application for Assistance) used a shared **Dynamic Form** system:

- **Backend:** `DynamicFormHelper.cs` loaded JSON form templates and application data from the database via WCF. Template types: `ApplicationForAssistance`, `RapidReinstatement`, `MonthlyReport`.
- **Frontend:** An AngularJS 1.5.9 micro-application under `Scripts/DynamicForms/`, with module-based form rendering, validation, and navigation directives.
- **Controllers:** `DynamicFormController` (client-facing), `AODynamicFormController` (admin override).

In MySS 2.0 this is replaced by Svelte form components driven by typed FastAPI endpoints.

### Authentication Flows

Two distinct flows existed:

1. **Client flow:** SiteMinder intercept → BCeID identity assertion → `ProfileHelper.GetProfileIdentifierNoTombstone()` → `ProfileHelper.LoadUserTombstoneData()` (ICM call) → ICM error routing.
2. **Worker/Admin flow:** IDIR authentication → `AOLoginController` → `SupportViewMode` session variable → audit record via `BaseController.SaveWorkerAuditRecord()`. Admin routes (`/AOLogin`) were IP-restricted to government ranges.

---

## Legacy to New Stack Mapping

| Legacy | New (MySS 2.0) |
|---|---|
| ASP.NET MVC Controllers | FastAPI Routers |
| Helpers (static classes) | Domain Services |
| ViewModels | Pydantic Models |
| Razor Views | SvelteKit Components |
| AngularJS Dynamic Forms | Svelte Form Components |
| WCF (`MCP_MC_Services`) | `ICMClient` (Siebel REST) |
| WCF (`MCP_Attachment_Services`) | `SiebelAttachmentClient` (Siebel REST) |
| Session State (SQL Server) | Redis (900s TTL) |
| SiteMinder | Auth.js + Keycloak |
| Web.config transforms | OpenShift ConfigMaps + Secrets |
| Enterprise Library Logging | structlog + OpenTelemetry |
| IIS on Windows Server | OpenShift / Kubernetes on Linux |

---

## ICM Error Codes — Legacy Names

The legacy codebase used string constants to identify ICM error conditions. These same codes appear in the new stack's `error_mapping.py` and `exceptions.py`. When you encounter them in requirements or comments:

| Code | What It Meant |
|---|---|
| `ICM_ERR_REVOKED` | User's access had been revoked in ICM |
| `ICM_ERR_NO_CASE` | No active income assistance case found — new applicant path |
| `ICM_ERR_NO_CONTACT` | BCeID not yet linked to an ICM contact record |
| `ICM_ERR_MULTI_CONTACTS` | Multiple ICM contact records matched — requires manual resolution |
| `ICM_ERR_CLOSED_CASE` | Case exists but is closed — limited read-only access permitted |

---

## Deep Dive: Analysis Reports

The three-step analysis that informed this reimplementation is preserved in the **legacy MySelfServe repository** under `docs/reports/` (not in this MySS 2.0 repo):

- **Step 1 — Functional Analysis:** `docs/reports/step-1-functional-analysis.docx` — all 10 functional domains, user flows, form types, and business rules extracted from the legacy code.
- **Step 2 — Code Analysis:** `docs/reports/step-2-code-analysis.docx` — controller inventory, helper responsibilities, WCF coupling points, and technical debt catalogue.
- **Step 3 — Architecture Opportunities:** `docs/reports/step-3-architecture-opportunities.docx` — proposed new architecture, data model, service boundaries, and the Celery adoption decision.

These documents are the authoritative source if you need to understand *why* a particular design decision was made in MySS 2.0.
