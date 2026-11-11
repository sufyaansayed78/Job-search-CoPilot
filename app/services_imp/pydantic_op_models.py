from datetime import datetime
from typing import List, Literal, Optional

from uuid import UUID
from app.models import ApplicationStatus
from pydantic import BaseModel, Field


class EmailClassification(BaseModel):
    email_category: bool = Field(description="True if the email is related to a job posting or application, False otherwise")
    job_category: Optional[Literal["job_posting", "job_application"]] = Field(default=None, description="The specific category of the email if it is related to a job posting or application. Return null if not applicable.")
class UpdateApplicationFromEmail(BaseModel):
    status : ApplicationStatus = Field(description="The new status of the application, if applicable")
    follow_up_date: Optional[datetime] = Field(default=None,description="The follow-up date and time mentioned in the email, in ISO 8601 format. Return null if not mentioned.")
    notes : Optional[str] = Field(default=None,description="Any additional notes or information extracted from the email that may be relevant to the application. Return null if not applicable.")
    company_name : Optional[str] = Field(default=None,description="The company name extracted from the email, if applicable. Return null if not applicable.")
    role : Optional[str] = Field(default=None,description="The role or position extracted from the email, if applicable. Return null if not applicable.")
    application_id: UUID = Field(
        description="The UUID of the matching job application")

class AddJobPostingFromEmail(BaseModel):
    company_name : Optional[str] = Field(default=None,description=".")
    role : Optional[str] = Field(default=None,description="")
    title : Optional[str] = Field(default=None,description="")
    url : Optional[str] = Field(default=None,description="The URL of the job posting extracted from the email, if applicable. Return null if not applicable.")
    raw_description : Optional[str] = Field(...,description="The raw description of the job posting extracted from the email, if applicable. Return null if not applicable.")

    







