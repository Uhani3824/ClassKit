from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import secrets
import string
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.models import postgresql as models
from app.schemas import course as schemas

router = APIRouter()

def generate_course_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(7))

@router.post("/", response_model=schemas.Course)
def create_course(
    course_in: schemas.CourseCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can create courses")
    
    code = generate_course_code()
    # Ensure code is unique
    while db.query(models.Course).filter(models.Course.code == code).first():
        code = generate_course_code()
        
    db_course = models.Course(
        **course_in.dict(),
        code=code,
        teacher_id=current_user.id
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

@router.get("/", response_model=List[schemas.Course])
def list_courses(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role == "teacher":
        return db.query(models.Course).filter(models.Course.teacher_id == current_user.id).all()
    else:
        return [enrollment.course for enrollment in current_user.enrollments]

@router.post("/join/{code}", response_model=schemas.Course)
def join_course(
    code: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can join courses via code")
    
    course = db.query(models.Course).filter(models.Course.code == code, models.Course.status == "active").first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or inactive")
    
    # Check if already enrolled
    enrolled = db.query(models.CourseEnrollment).filter(
        models.CourseEnrollment.course_id == course.id,
        models.CourseEnrollment.user_id == current_user.id
    ).first()
    if enrolled:
        raise HTTPException(status_code=400, detail="Already enrolled in this course")
    
    enrollment = models.CourseEnrollment(course_id=course.id, user_id=current_user.id)
    db.add(enrollment)
    db.commit()
    return course

@router.get("/{course_id}", response_model=schemas.Course)
def get_course(
    course_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check if authorized to view
    if current_user.role == "teacher" and course.teacher_id == current_user.id:
        return course
    
    enrolled = db.query(models.CourseEnrollment).filter(
        models.CourseEnrollment.course_id == course.id,
        models.CourseEnrollment.user_id == current_user.id
    ).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="Not authorized to view this course")
    
    return course
