from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class AssignmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: datetime
    allow_late: bool = True
    max_points: int = 100

class AssignmentCreate(AssignmentBase):
    course_id: int

class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    allow_late: Optional[bool] = None

class AssignmentAttachmentBase(BaseModel):
    file_url: str
    filename: str

class AssignmentAttachment(AssignmentAttachmentBase):
    id: int
    assignment_id: int

    class Config:
        from_attributes = True

class Assignment(AssignmentBase):
    id: int
    course_id: int
    attachments: List[AssignmentAttachment] = []

    class Config:
        from_attributes = True

class SubmissionBase(BaseModel):
    submission_text: Optional[str] = None

class SubmissionAttachmentBase(BaseModel):
    file_url: str
    filename: str

class SubmissionAttachment(SubmissionAttachmentBase):
    id: int
    submission_id: int

    class Config:
        from_attributes = True

class SubmissionCreate(SubmissionBase):
    assignment_id: int

from app.schemas import user as user_schema

class Submission(SubmissionBase):
    id: int
    assignment_id: int
    student_id: int
    timestamp: datetime
    grade: Optional[int] = None
    is_late: bool
    attachments: List[SubmissionAttachment] = []
    student: Optional[user_schema.User] = None

    class Config:
        from_attributes = True
