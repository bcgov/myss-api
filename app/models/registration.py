from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON


class RegistrationSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    # Null until BCeID link step (step 6). Set atomically with User row creation.
    invite_token: str = Field(unique=True)
    step: int  # current registration step (1–6)
    form_state_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    expires_at: datetime
    completed_at: Optional[datetime] = None


# AORegistrationSession is defined in app.models.ao_registration
# and re-exported via app.models.__init__
