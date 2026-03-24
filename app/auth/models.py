from enum import Enum
from pydantic import BaseModel


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    WORKER = "WORKER"
    ADMIN = "ADMIN"


class UserContext(BaseModel):
    user_id: str
    role: UserRole
    bceid_guid: str | None = None
    idir_username: str | None = None
