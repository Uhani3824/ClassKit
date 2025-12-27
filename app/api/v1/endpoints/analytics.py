from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.models import postgresql as models
from app.services.analytics_service import AnalyticsService

router = APIRouter()

@router.get("/course/{course_id}/dashboard-full")
def get_full_dashboard_analytics(
    course_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns comprehensive analytics for the course dashboard.
    Authorized for Teachers only.
    """
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    if current_user.role != "teacher" and course.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the course teacher can view analytics")
        
    service = AnalyticsService(db)
    
    # Aggregating all data
    kpis = service.get_quick_kpis(course_id)
    timeline = service.get_engagement_timeline(course_id, days=7)
    assignment_stats = service.get_assignment_analytics(course_id)
    difficulty = service.get_assignment_difficulty(course_id)
    completion = service.get_course_completion(course_id)
    
    return {
        "kpis": kpis,
        "engagement_timeline": timeline,
        "assignment_stats": assignment_stats,
        "difficulty_indicators": difficulty,
        "course_completion": completion
    }
