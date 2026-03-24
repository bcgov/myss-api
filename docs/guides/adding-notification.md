# Adding a New Notification Type

## When to use this guide

Use this guide when a new notification or message type needs to surface to users — for example, a new banner alert, a new ICM inbox message category, or a new transactional email.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)

---

## Steps

### 1. Define the domain model

All notification models are in `myss-api/app/domains/notifications/models.py`. Decide which model category applies:

**Banner notifications** — time-bounded portal alerts retrieved from Siebel and cached in Redis:

```python
class BannerNotification(BaseModel):
    notification_id: str
    body: str  # max 150 chars
    start_date: datetime
    end_date: datetime
```

**ICM inbox messages** — messages from workers, categorized by type:

```python
class ICMMessageType(str, Enum):
    SD81_STANDARD = "HR0081"
    SD81_RESTART = "HR0081Restart"
    SD81_STREAMLINED_RESTART = "HR0081StreamlinedRestart"
    SD81_PENDING_DOCUMENTS = "HR0081 Pending Documents"
    FORM_SUBMISSION = "FormSubmission"
    GENERAL = "General"
```

**Transactional emails** — outbound emails sent via Celery/MailJet:

```python
class EmailTemplate(str, Enum):
    REGISTRATION_VERIFICATION = "registration_verification"
    PIN_RESET = "pin_reset"
    SD81_REMINDER = "sd81_reminder"
    REGISTRATION_CONFIRMATION = "registration_confirmation"
    APPLICATION_SURVEY = "application_survey"
```

For a new banner type, no model change is needed — `BannerNotification` is generic.

For a new inbox message category, add the new `ICMMessageType` enum value.

For a new transactional email, add a new `EmailTemplate` enum value.

---

### 2. Add a DB model if the notification is persistent

Banner notifications and inbox messages are sourced from Siebel and are not stored in the portal database. If the new notification type is portal-owned (e.g. a locally generated alert), add a SQLModel to `myss-api/app/models/` and generate a migration:

```bash
cd myss-api
alembic revision --autogenerate -m "add_portal_alerts_table"
alembic upgrade head
```

For Siebel-sourced notifications, no DB model is needed.

---

### 3. Configure Redis caching for banners

Banner notifications are cached in Redis to avoid hitting Siebel on every page load. The cache key and TTL are defined in `myss-api/app/cache/keys.py`:

```python
ICM_BANNERS_TTL: int = 300       # 5 minutes — banner notification cache

def icm_banners_key(case_number: str) -> str:
    """Redis key for banner notification cache (TTL: 5 minutes)."""
    return f"icm_cache:banners:{case_number}"
```

The TTL is 300 seconds (5 minutes). If the new notification type needs a different TTL, add a new constant:

```python
ICM_ALERTS_TTL: int = 60    # 1 minute for urgent alerts

def icm_alerts_key(case_number: str) -> str:
    return f"icm_cache:alerts:{case_number}"
```

Then cache the result in the service layer using `redis.setex(key, ttl, value)`.

---

### 4. Add or extend an API endpoint

Notification endpoints are in `myss-api/app/routers/notifications.py`. The file defines two routers:

- `notifications_router` — prefix `/notifications` (banners)
- `messages_router` — prefix `/messages` (inbox messages)

To add a new banner variant, extend the existing `get_banners` endpoint or add a new route to `notifications_router`:

```python
@notifications_router.get("/alerts", response_model=MyAlertListResponse)
async def get_alerts(
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
) -> MyAlertListResponse:
    return await svc.get_alerts(user.user_id)
```

To add a new message action (e.g. forwarding a message), add a route to `messages_router` following the existing pattern:

```python
@messages_router.post("/{msg_id}/forward", response_model=ReplyResponse)
async def forward_message(
    msg_id: str,
    request: ForwardRequest,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
    svc: NotificationMessageService = Depends(_get_notification_service),
) -> ReplyResponse:
    return await svc.forward(msg_id, request)
```

Both routers are already registered in `myss-api/app/main.py`. No changes to the main app are needed for new routes on existing routers.

---

### 5. Create or update the SvelteKit display component

Frontend notification pages are under `myss-web/src/routes/messages/`. The API client for notifications is in `myss-web/src/lib/api/messages.ts`.

Add the new notification surface to the appropriate route. If it is a new page, create a new `+page.svelte` under the messages route directory. Follow the existing pattern: fetch data in `onMount`, handle loading and error states, render items from the API response.

---

### 6. Configure transactional email via Celery

Transactional emails are sent asynchronously via Celery. The task stub is in `myss-api/app/workers/tasks/send_transactional_email.py`:

```python
from celery import shared_task

@shared_task(name="send_transactional_email")
def send_transactional_email(task_data: dict) -> None:
    """Send transactional email via MailJet. Stub for now."""
    pass
```

To add a new email type:

1. Add the new template to the `EmailTemplate` enum in `myss-api/app/domains/notifications/models.py`:

```python
class EmailTemplate(str, Enum):
    # existing ...
    RENEWAL_REMINDER = "renewal_reminder"
```

2. Implement the MailJet send logic inside `send_transactional_email` (or create a separate task if the email has substantially different behaviour). The task receives `task_data: dict` which should include the template name, recipient, and context variables.

3. Enqueue the task from a service method or router background task:

```python
from app.workers.tasks.send_transactional_email import send_transactional_email

# Fire and forget
send_transactional_email.delay({
    "template": EmailTemplate.RENEWAL_REMINDER.value,
    "recipient": {"email": user_email, "name": user_name},
    "context": {"renewal_date": "2026-03-31"},
})
```

MailJet credentials and template IDs are configured via environment variables. See the [local setup guide](../onboarding/local-dev-setup.md) for required env vars.

---

### 7. Write tests

**Service layer tests** — mock `SiebelNotificationClient` and test that `NotificationMessageService` filters expired banners, handles `can_reply=False`, etc.:

```python
# myss-api/tests/test_notifications.py
from unittest.mock import AsyncMock
from app.domains.notifications.service import NotificationMessageService
from app.services.icm.notifications import SiebelNotificationClient

async def test_expired_banners_are_filtered():
    mock_client = AsyncMock(spec=SiebelNotificationClient)
    mock_client.get_banners = AsyncMock(return_value={
        "banners": [
            {
                "notification_id": "old-1",
                "body": "Expired banner",
                "start_date": "2020-01-01T00:00:00+00:00",
                "end_date": "2020-01-02T00:00:00+00:00",   # past
            }
        ]
    })
    svc = NotificationMessageService(client=mock_client)
    result = await svc.get_banners("CASE-001")
    assert len(result.banners) == 0   # expired banner filtered out
```

**Router tests** — use the `AsyncClient` pattern from `conftest.py` and override the dependency:

```python
from app.routers.notifications import _get_notification_service

app.dependency_overrides[_get_notification_service] = lambda: mock_svc
```

**Celery task tests** — test that `send_transactional_email.delay()` is called with the correct payload. Mock the Celery task with `@patch("app.workers.tasks.send_transactional_email.send_transactional_email.delay")`.

---

## Verification

1. `cd myss-api && pytest tests/test_notifications.py tests/test_notification_service.py -x`
2. `GET /notifications/banners` returns banner list (may be empty if no banners in Siebel mock)
3. `GET /messages` returns the inbox list
4. Confirm expired banners are excluded from the response
5. For email: confirm `send_transactional_email.delay()` is called during the relevant workflow

---

## Common pitfalls

**`BannerNotification.body` has an implicit 150-char limit.** The model docstring notes `# max 150 chars`. This is not enforced by Pydantic — it is a Siebel contract. If Siebel sends longer bodies in the future, the frontend will display them without truncation unless a `max_length` validator is added.

**Cache TTL not invalidated on demand.** Banner cache (`ICM_BANNERS_TTL = 300`) is time-based. If a banner is removed in Siebel mid-TTL, the portal will continue showing it for up to 5 minutes. This is by design. If immediate invalidation is required for a new notification type, implement explicit cache deletion via `redis.delete(icm_banners_key(case_number))` in the relevant service method.

**`can_reply` gating is enforced only in the service.** The `NotificationMessageService.reply()` method checks `can_reply` before calling Siebel. The router also checks it (`if not message.can_reply: raise HTTPException(403, ...)`). When adding new message action types, apply the same pattern — guard the action in both the service and the router.

**New `ICMMessageType` values must match Siebel strings exactly.** The enum values (e.g. `"HR0081"`, `"FormSubmission"`) are the literal strings Siebel returns in the message type field. If the casing or format differs from what Siebel sends, the enum parse will fail and the message will appear malformed.
