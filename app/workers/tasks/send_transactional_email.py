from celery import shared_task


@shared_task(name="send_transactional_email")
def send_transactional_email(task_data: dict) -> None:
    """Send transactional email via MailJet. Stub for now."""
    pass
