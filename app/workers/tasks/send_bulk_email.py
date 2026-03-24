from celery import shared_task


@shared_task(name="send_bulk_email")
def send_bulk_email(task_data: dict) -> None:
    """Send bulk email via MailJet HTTP API v3.1. Stub for now."""
    # Real implementation will call MailJet POST /v3.1/send
    pass
