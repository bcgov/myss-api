from app.domains.notifications.models import (
    BulkEmailTask,
    EmailRecipient,
    EmailTemplate,
    NotificationType,
)


class NotificationService:
    """Enqueues email tasks onto Celery queues."""

    def send_bulk_email(
        self,
        template: EmailTemplate,
        recipients: list[EmailRecipient],
        context: dict,
    ) -> None:
        """Enqueue a bulk email task on the notifications_bulk queue."""
        from app.workers.tasks.send_bulk_email import send_bulk_email

        task = BulkEmailTask(
            template=template,
            recipients=recipients,
            context=context,
            notification_type=NotificationType.BULK,
        )
        send_bulk_email.apply_async(args=[task.model_dump()], queue="notifications_bulk")

    def send_transactional_email(
        self,
        template: EmailTemplate,
        recipient: EmailRecipient,
        context: dict,
    ) -> None:
        """Enqueue a transactional email task on the notifications_transactional queue."""
        from app.workers.tasks.send_transactional_email import send_transactional_email

        task = BulkEmailTask(
            template=template,
            recipients=[recipient],
            context=context,
            notification_type=NotificationType.TRANSACTIONAL,
        )
        send_transactional_email.apply_async(
            args=[task.model_dump()], queue="notifications_transactional"
        )
