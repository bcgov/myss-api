from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ICMMessageType(str, Enum):
    SD81_STANDARD = "HR0081"
    SD81_RESTART = "HR0081Restart"
    SD81_STREAMLINED_RESTART = "HR0081StreamlinedRestart"
    SD81_PENDING_DOCUMENTS = "HR0081 Pending Documents"
    FORM_SUBMISSION = "FormSubmission"
    GENERAL = "General"


class BannerNotification(BaseModel):
    notification_id: str
    body: str  # max 150 chars
    start_date: datetime
    end_date: datetime


class MessageSummary(BaseModel):
    message_id: str
    subject: str
    sent_date: datetime
    is_read: bool
    can_reply: bool
    message_type: ICMMessageType


class InboxListResponse(BaseModel):
    messages: list[MessageSummary]
    total: int


class MessageDetail(MessageSummary):
    body: str
    attachments: list[str]


class ReplyRequest(BaseModel):
    body: str = Field(max_length=4000)
    attachment_ids: list[str] = Field(default_factory=list)


class ReplyResponse(BaseModel):
    status: str
    sent_at: datetime


class BannerListResponse(BaseModel):
    banners: list[BannerNotification]


class SignRequest(BaseModel):
    pin: str = Field(min_length=1)


class NotificationType(str, Enum):
    BULK = "BULK"
    TRANSACTIONAL = "TRANSACTIONAL"


class EmailTemplate(str, Enum):
    REGISTRATION_VERIFICATION = "registration_verification"
    PIN_RESET = "pin_reset"
    SD81_REMINDER = "sd81_reminder"
    REGISTRATION_CONFIRMATION = "registration_confirmation"
    APPLICATION_SURVEY = "application_survey"


class EmailRecipient(BaseModel):
    email: str  # EmailStr requires email-validator, use str for now
    name: str


class BulkEmailTask(BaseModel):
    template: EmailTemplate
    recipients: list[EmailRecipient]
    context: dict
    notification_type: NotificationType
