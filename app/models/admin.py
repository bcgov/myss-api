from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class WorkerRole(str, Enum):
    SSBC_WORKER = "SSBC_WORKER"
    SUPER_ADMIN = "SUPER_ADMIN"


class IDIRGroup(str, Enum):
    MYSS_WORKERS = "MYSS_Workers"
    MYSS_ADMINS = "MYSS_Admins"


class WorkerJWT(BaseModel):
    idir_guid: str
    idir_username: str
    worker_role: WorkerRole
    idir_groups: list[str]
    exp: datetime


class SupportViewSessionData(BaseModel):
    worker_idir: str
    client_portal_id: str
    client_bceid_guid: str
    activated_at: datetime
    expires_at: datetime


class AdminClientSummary(BaseModel):
    portal_id: str
    bceid_guid: str
    case_number: str | None = None
    case_status: str | None = None
    full_name: str


class AdminClientProfile(AdminClientSummary):
    contact_id: str
    link_code: str
    last_login: datetime | None = None
    active_srs: list[str] = []
