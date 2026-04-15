from datetime import date, datetime

from pydantic import BaseModel


class ChequeScheduleWindow(BaseModel):
    benefit_month: date
    income_date: date
    cheque_issue_date: date
    period_close_date: datetime  # Friday 4PM
