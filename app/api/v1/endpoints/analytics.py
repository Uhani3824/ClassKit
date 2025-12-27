from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from app.api.v1.endpoints.auth import get_current_user
from app.core import database, cassandra_db
from app.models import postgresql as models
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/teacher/dashboard")
def get_teacher_dashboard_analytics(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can access this dashboard")
        
    course_ids = [c.id for c in current_user.courses_created]
    
    # 1. Total number of students
    total_students = db.query(models.CourseEnrollment).filter(models.CourseEnrollment.course_id.in_(course_ids)).distinct(models.CourseEnrollment.user_id).count()
    
    # 2. Number of assignments created
    total_assignments = db.query(models.Assignment).filter(models.Assignment.course_id.in_(course_ids)).count()
    
    # 3. Average submission rate
    # submission_rate = submitted_count / enrolled_students
    # We'll calculate this per assignment and average it
    avg_submission_rate = 0
    if total_assignments > 0:
        rates = []
        assignments = db.query(models.Assignment).filter(models.Assignment.course_id.in_(course_ids)).all()
        for assignment in assignments:
            enrolled_count = db.query(models.CourseEnrollment).filter(models.CourseEnrollment.course_id == assignment.course_id).count()
            if enrolled_count > 0:
                submitted_count = db.query(models.Submission).filter(models.Submission.assignment_id == assignment.id).count()
                rates.append(submitted_count / enrolled_count)
        if rates:
            avg_submission_rate = sum(rates) / len(rates)

    # 4. Recent activity (from Cassandra)
    recent_activity = []
    cassandra_session = cassandra_db.get_cassandra_session()
    # Query Cassandra for last 48 hours for each course
    forty_eight_hours_ago = datetime.utcnow() - timedelta(hours=48)
    for cid in course_ids:
        query = "SELECT event_type, details, event_time FROM event_logs WHERE course_id = %s AND event_time >= %s"
        rows = cassandra_session.execute(query, (cid, forty_eight_hours_ago))
        for row in rows:
            recent_activity.append({
                "type": row.event_type,
                "details": row.details,
                "time": str(row.event_time)
            })
            
    # Sort activity by time descending
    recent_activity.sort(key=lambda x: x['time'], reverse=True)

    return {
        "total_students": total_students,
        "total_assignments": total_assignments,
        "avg_submission_rate": round(avg_submission_rate * 100, 2),
        "recent_activity": recent_activity[:20] # Top 20 activities
    }

@router.get("/course/{course_id}/analytics")
def get_course_analytics(
    course_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course or (course.teacher_id != current_user.id and current_user.role != "teacher"):
         raise HTTPException(status_code=403, detail="Access denied")

    enrolled_count = db.query(models.CourseEnrollment).filter(models.CourseEnrollment.course_id == course_id).count()
    
    # Activity counts in last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    cassandra_session = cassandra_db.get_cassandra_session()
    
    activity_summary = {
        "post_count": 0,
        "comment_count": 0,
        "announcement_count": 0
    }
    
    query = "SELECT event_type FROM event_logs WHERE course_id = %s AND event_time >= %s"
    rows = cassandra_session.execute(query, (course_id, seven_days_ago))
    for row in rows:
        if row.event_type == "post_created": activity_summary["post_count"] += 1
        elif row.event_type == "comment_added": activity_summary["comment_count"] += 1
        elif row.event_type == "announcement_created": activity_summary["announcement_count"] += 1
        
    return {
        "enrolled_students": enrolled_count,
        "activity_summary": activity_summary
    }
