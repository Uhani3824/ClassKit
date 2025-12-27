from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    section: Optional[str] = None

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    section: Optional[str] = None
    status: Optional[str] = None

class Course(CourseBase):
    id: int
    code: str
    teacher_id: Optional[int]
    status: str

    class Config:
        from_attributes = True

class CourseEnrollmentBase(BaseModel):
    course_id: int
    user_id: int

class CourseEnrollment(CourseEnrollmentBase):
    enrolled_at: datetime

    class Config:
        from_attributes = True
