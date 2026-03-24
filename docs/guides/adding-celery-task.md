# Adding a Celery Task

## When to use this guide

Use this guide when work should not block the API response — sending emails, scanning uploaded files, generating PDFs, or any operation that is slow or can be retried independently.

## Prerequisites

- [Local development setup](../onboarding/local-dev-setup.md)
- [Codebase overview](../onboarding/architecture.md)
- Redis is running locally (Celery uses it as broker and result backend)

---

## Steps

### 1. Create the task file in `app/workers/tasks/`

Each task type lives in its own file. The existing tasks in `myss-api/app/workers/tasks/` show the minimal pattern:

```python
# app/workers/tasks/send_transactional_email.py
from celery import shared_task


@shared_task(name="send_transactional_email")
def send_transactional_email(task_data: dict) -> None:
    """Send transactional email via MailJet. Stub for now."""
    pass
```

```python
# app/workers/tasks/send_bulk_email.py
from celery import shared_task


@shared_task(name="send_bulk_email")
def send_bulk_email(task_data: dict) -> None:
    """Send bulk email via MailJet HTTP API v3.1."""
    pass
```

Key points:
- `@shared_task` binds to the Celery app configured in `app.celery_app` without importing it directly, avoiding circular imports. Note that `app/celery_app.py` (the Celery application module) is a planned addition that must be created before tasks can be dispatched.
- `name=` gives the task a stable string identifier independent of the module path. Always set it explicitly.
- Accept a `dict` rather than individual arguments. This makes the task payload serialisable to JSON and makes it easy to evolve the schema without changing the function signature.

### 2. Add retry logic with `bind=True`

For tasks that call external services (email providers, file scanners, ICM), add retry behaviour:

```python
# app/workers/tasks/your_task.py
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import structlog

logger = structlog.get_logger()


@shared_task(
    name="your_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # seconds before first retry
)
def your_task(self, task_data: dict) -> None:
    """Do the work. Retries up to 3 times with exponential backoff."""
    try:
        # Do the actual work here
        _perform_work(task_data)
    except SomeTransientError as exc:
        # Exponential backoff: 60s, 120s, 240s
        delay = self.default_retry_delay * (2 ** self.request.retries)
        logger.warning("task_retry", task=self.name, attempt=self.request.retries, exc=str(exc))
        raise self.retry(exc=exc, countdown=delay)
    except MaxRetriesExceededError:
        logger.error("task_failed_permanently", task=self.name, task_data=task_data)
        raise
```

`bind=True` passes `self` (the task instance) as the first argument, giving access to `self.retry()`, `self.request.retries`, and `self.name`.

### 3. Trigger the task from an API endpoint using `.apply_async()`

The existing pattern from `NotificationService` in `app/services/notification_service.py`:

```python
from app.workers.tasks.send_bulk_email import send_bulk_email

send_bulk_email.apply_async(
    args=[task_data.model_dump()],
    queue="notifications_bulk",
)
```

Use `.apply_async()` with `queue=` rather than `.delay()` when you need to target a specific Celery queue. The Celery worker in OpenShift (`openshift/celery-deployment.yaml`) subscribes to these queues:

```
pdf_generation, notifications_bulk, notifications_transactional
```

For a new task type, decide which queue it belongs to, or add a new queue and update the Celery worker deployment command:

> **Note:** `app.celery_app` is a placeholder — the Celery application module
> (`myss-api/app/celery_app.py`) has not been created yet. This deployment
> command is the target state once that module exists. Create it as a
> prerequisite before deploying the Celery worker.

```yaml
command:
  - celery
  - -A
  - app.celery_app
  - worker
  - --loglevel=info
  - -Q
  - pdf_generation,notifications_bulk,notifications_transactional,your_new_queue
```

To dispatch from a router endpoint:

```python
# app/routers/your_resource.py
from app.workers.tasks.your_task import your_task

@router.post("/{resource_id}/process", status_code=202)
async def trigger_processing(
    resource_id: str,
    user: UserContext = Depends(require_role(UserRole.CLIENT)),
):
    your_task.apply_async(
        args=[{"resource_id": resource_id, "user_id": user.user_id}],
        queue="your_queue",
    )
    return {"status": "accepted"}
```

Return 202 (Accepted) when the work has been queued but not yet completed.

### 4. Optionally expose task status

If the caller needs to poll for completion, store the task ID and expose a status endpoint:

```python
result = your_task.apply_async(
    args=[{"resource_id": resource_id}],
    queue="your_queue",
)
task_id = result.id  # store this in the DB alongside the resource

# Status endpoint:
from celery.result import AsyncResult

@router.get("/{resource_id}/status")
async def get_task_status(resource_id: str, ...):
    task_id = await svc.get_task_id(resource_id)
    result = AsyncResult(task_id)
    return {"state": result.state}  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
```

### 5. Write tests

Test the task function directly — do not start a real Celery worker. Call the function synchronously:

```python
# tests/test_your_task.py
from unittest.mock import patch, MagicMock
from app.workers.tasks.your_task import your_task


def test_your_task_calls_external_service():
    task_data = {"resource_id": "abc123", "user_id": "user-1"}

    with patch("app.workers.tasks.your_task._perform_work") as mock_work:
        your_task(task_data)  # call directly, no Celery broker needed

    mock_work.assert_called_once_with(task_data)


def test_your_task_retries_on_transient_error():
    task_data = {"resource_id": "abc123"}
    mock_self = MagicMock()
    mock_self.request.retries = 0
    mock_self.default_retry_delay = 60

    with patch("app.workers.tasks.your_task._perform_work", side_effect=SomeTransientError("timeout")):
        with patch.object(your_task, "retry") as mock_retry:
            your_task(mock_self, task_data)
            mock_retry.assert_called_once()
```

The test pattern from `tests/test_notification_service.py` shows how to test that tasks are dispatched with the right queue and arguments — by patching the task object and asserting on `apply_async`:

```python
from unittest.mock import MagicMock, patch
from app.services.notification_service import NotificationService


def test_enqueues_on_correct_queue():
    mock_task = MagicMock()
    with patch("app.workers.tasks.your_task.your_task", mock_task):
        service = YourService()
        service.trigger_something(resource_id="abc123")

    mock_task.apply_async.assert_called_once()
    _, kwargs = mock_task.apply_async.call_args
    assert kwargs["queue"] == "your_queue"

def test_task_data_contains_resource_id():
    mock_task = MagicMock()
    with patch("app.workers.tasks.your_task.your_task", mock_task):
        service = YourService()
        service.trigger_something(resource_id="abc123")

    kwargs = mock_task.apply_async.call_args.kwargs
    task_data = kwargs["args"][0]
    assert task_data["resource_id"] == "abc123"
```

---

## Verification

```bash
cd myss-api

# Run the test suite (no Celery broker needed)
make test

# Start Redis and the Celery worker locally
# PREREQUISITE: app/celery_app.py (the Celery application module) must be created
# before the worker command below will work. This module does not exist yet — it is
# a planned addition. Once created, the worker is started with:
redis-server &
celery -A app.celery_app worker --loglevel=info -Q your_queue

# Trigger the task via the API endpoint
curl -X POST http://localhost:8000/your-resource/abc123/process \
  -H "Authorization: Bearer TOKEN"

# Watch the Celery worker terminal for task logs
```

---

## Common pitfalls

**JSON serialization of UUIDs and datetime objects**
Celery serializes task arguments to JSON by default. Python `UUID` and `datetime` objects are not JSON-serializable. Convert them to strings before passing to `.apply_async()`:

```python
# Wrong — will raise TypeError at dispatch time
your_task.apply_async(args=[{"id": some_uuid, "at": some_datetime}])

# Correct
your_task.apply_async(args=[{"id": str(some_uuid), "at": some_datetime.isoformat()}])
```

If your task accepts a Pydantic model, use `.model_dump()` (which produces a dict of JSON-compatible primitives for simple types) and handle UUID/datetime fields explicitly.

**Missing retry configuration**
A task that calls an external service without retry logic will silently drop work when the service is temporarily unavailable. Always add `bind=True, max_retries=3` for tasks that call MailJet, ICM, or any other external system.

**Not testing independently of Celery**
Tasks should be tested by calling the function directly (`your_task(task_data)`) without a running broker. If a test requires a real broker, it is testing Celery's internals rather than your business logic.

**Dispatching tasks inside database transactions**
If you call `.apply_async()` inside an open `AsyncSession` transaction and the transaction is later rolled back, the task has already been dispatched. The task will run against data that no longer exists. Always dispatch tasks after the DB commit:

```python
await session.commit()           # commit first
your_task.apply_async(args=[...])  # then dispatch
```

**Queue name mismatch**
The Celery worker in OpenShift only subscribes to the queues listed in `celery-deployment.yaml`. If you dispatch to a queue that the worker does not subscribe to, the task sits in Redis forever. Verify the queue name and update the deployment if needed.
