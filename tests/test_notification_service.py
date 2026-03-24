from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.domains.notifications.models import EmailRecipient, EmailTemplate
from app.services.notification_service import NotificationService


@pytest.fixture
def service() -> NotificationService:
    return NotificationService()


@pytest.fixture
def recipient() -> EmailRecipient:
    return EmailRecipient(email="test@example.com", name="Test User")


class TestSendBulkEmail:
    def test_enqueues_on_notifications_bulk_queue(self, service: NotificationService, recipient: EmailRecipient) -> None:
        mock_task = MagicMock()
        with patch("app.workers.tasks.send_bulk_email.send_bulk_email", mock_task):
            service.send_bulk_email(
                template=EmailTemplate.SD81_REMINDER,
                recipients=[recipient],
                context={"key": "value"},
            )

        mock_task.apply_async.assert_called_once()
        _, kwargs = mock_task.apply_async.call_args
        assert kwargs["queue"] == "notifications_bulk"

    def test_task_data_contains_correct_template(self, service: NotificationService, recipient: EmailRecipient) -> None:
        mock_task = MagicMock()
        with patch("app.workers.tasks.send_bulk_email.send_bulk_email", mock_task):
            service.send_bulk_email(
                template=EmailTemplate.REGISTRATION_VERIFICATION,
                recipients=[recipient],
                context={},
            )

        kwargs = mock_task.apply_async.call_args.kwargs
        task_data = kwargs["args"][0]
        assert task_data["template"] == EmailTemplate.REGISTRATION_VERIFICATION

    def test_task_data_contains_recipients(self, service: NotificationService, recipient: EmailRecipient) -> None:
        mock_task = MagicMock()
        with patch("app.workers.tasks.send_bulk_email.send_bulk_email", mock_task):
            service.send_bulk_email(
                template=EmailTemplate.SD81_REMINDER,
                recipients=[recipient],
                context={},
            )

        kwargs = mock_task.apply_async.call_args.kwargs
        task_data = kwargs["args"][0]
        assert len(task_data["recipients"]) == 1
        assert task_data["recipients"][0]["email"] == "test@example.com"
        assert task_data["recipients"][0]["name"] == "Test User"


class TestSendTransactionalEmail:
    def test_enqueues_on_notifications_transactional_queue(self, service: NotificationService, recipient: EmailRecipient) -> None:
        mock_task = MagicMock()
        with patch("app.workers.tasks.send_transactional_email.send_transactional_email", mock_task):
            service.send_transactional_email(
                template=EmailTemplate.PIN_RESET,
                recipient=recipient,
                context={"token": "abc123"},
            )

        mock_task.apply_async.assert_called_once()
        _, kwargs = mock_task.apply_async.call_args
        assert kwargs["queue"] == "notifications_transactional"

    def test_task_data_contains_correct_template(self, service: NotificationService, recipient: EmailRecipient) -> None:
        mock_task = MagicMock()
        with patch("app.workers.tasks.send_transactional_email.send_transactional_email", mock_task):
            service.send_transactional_email(
                template=EmailTemplate.REGISTRATION_CONFIRMATION,
                recipient=recipient,
                context={},
            )

        kwargs = mock_task.apply_async.call_args.kwargs
        task_data = kwargs["args"][0]
        assert task_data["template"] == EmailTemplate.REGISTRATION_CONFIRMATION

    def test_task_data_wraps_recipient_in_list(self, service: NotificationService, recipient: EmailRecipient) -> None:
        mock_task = MagicMock()
        with patch("app.workers.tasks.send_transactional_email.send_transactional_email", mock_task):
            service.send_transactional_email(
                template=EmailTemplate.PIN_RESET,
                recipient=recipient,
                context={},
            )

        kwargs = mock_task.apply_async.call_args.kwargs
        task_data = kwargs["args"][0]
        assert len(task_data["recipients"]) == 1
        assert task_data["recipients"][0]["email"] == recipient.email


class TestEmailTemplateValidation:
    def test_unknown_template_raises_validation_error(self) -> None:
        from app.domains.notifications.models import BulkEmailTask, NotificationType

        with pytest.raises(ValidationError):
            BulkEmailTask(
                template="not_a_real_template",
                recipients=[],
                context={},
                notification_type=NotificationType.BULK,
            )
