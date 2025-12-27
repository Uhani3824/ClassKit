from fastapi import APIRouter, Request, Depends, Cookie, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from app.core import database
from app.models import postgresql as models
from app.api.v1.endpoints.auth import get_current_user
from jose import jwt
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def get_user_from_cookie(db: Session, access_token: Optional[str] = None):
    if not access_token:
        return None
    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id:
            return db.query(models.User).filter(models.User.id == int(user_id)).first()
    except:
        return None
    return None

@router.get("/")
async def index_page(request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if user:
        courses = []
        if user.role == "teacher":
            courses = db.query(models.Course).filter(models.Course.teacher_id == user.id).all()
        else:
            courses = [en.course for en in user.enrollments]
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "courses": courses})
    return templates.TemplateResponse("index.html", {"request": request, "user": None})

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/dashboard")
async def dashboard_page(request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    
    courses = []
    if user.role == "teacher":
        courses = db.query(models.Course).filter(models.Course.teacher_id == user.id).all()
    else:
        courses = [en.course for en in user.enrollments]
        
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "courses": courses})

@router.get("/courses/{course_id}")
async def course_stream_page(course_id: int, request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
        
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    posts = db.query(models.Post).filter(models.Post.course_id == course_id).order_by(models.Post.timestamp.desc()).all()
    
    # Get upcoming assignments (due in the future)
    upcoming_assignments = db.query(models.Assignment).filter(
        models.Assignment.course_id == course_id,
        models.Assignment.due_date > datetime.utcnow()
    ).order_by(models.Assignment.due_date).limit(5).all()
    
    return templates.TemplateResponse("stream.html", {
        "request": request, 
        "user": user, 
        "course": course, 
        "posts": posts,
        "upcoming_assignments": upcoming_assignments
    })

@router.get("/courses/{course_id}/classwork")
async def classwork_page(course_id: int, request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
        
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    assignments = db.query(models.Assignment).filter(models.Assignment.course_id == course_id).all()
    return templates.TemplateResponse("classwork.html", {"request": request, "user": user, "course": course, "assignments": assignments})

@router.get("/courses/{course_id}/assignments/{assignment_id}")
async def assignment_view_page(course_id: int, assignment_id: int, request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
        
    assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    submission = db.query(models.Submission).filter(
        models.Submission.assignment_id == assignment_id,
        models.Submission.student_id == user.id
    ).first()
    return templates.TemplateResponse("assignment_view.html", {
        "request": request, 
        "user": user, 
        "assignment": assignment, 
        "submission": submission,
        "now": datetime.utcnow()
    })

@router.get("/courses/{course_id}/people")
async def people_page(course_id: int, request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get teacher
    teacher = db.query(models.User).filter(models.User.id == course.teacher_id).first()
    
    # Get enrolled students
    enrollments = db.query(models.CourseEnrollment).filter(models.CourseEnrollment.course_id == course_id).all()
    students = [enrollment.user for enrollment in enrollments]
    
    return templates.TemplateResponse("people.html", {
        "request": request,
        "user": user,
        "course": course,
        "teacher": teacher,
        "students": students
    })

@router.get("/courses/{course_id}/assignments/{assignment_id}/submissions")
async def submissions_page(course_id: int, assignment_id: int, request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user or user.role != "teacher":
        return templates.TemplateResponse("login.html", {"request": request})
        
    assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    submissions = db.query(models.Submission).filter(models.Submission.assignment_id == assignment_id).all()
    return templates.TemplateResponse("submissions.html", {"request": request, "user": user, "assignment": assignment, "submissions": submissions})

@router.get("/courses/{course_id}/analytics")
async def course_analytics_page(course_id: int, request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user or user.role != "teacher":
        return templates.TemplateResponse("login.html", {"request": request})
        
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    return templates.TemplateResponse("analytics.html", {"request": request, "user": user, "course": course})

@router.get("/profile")
async def profile_page(request: Request, db: Session = Depends(database.get_db), access_token: Optional[str] = Cookie(None)):
    user = get_user_from_cookie(db, access_token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@router.get("/logout")
async def logout_page(request: Request):
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie("access_token")
    return response
