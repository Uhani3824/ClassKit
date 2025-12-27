from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models import postgresql as models
from app.core import cassandra_db
from datetime import datetime, timedelta

class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.cassandra_session = cassandra_db.get_cassandra_session()

    def get_quick_kpis(self, course_id: int):
        """Returns summarized KPIs for the course."""
        total_students = self.db.query(models.CourseEnrollment).filter_by(course_id=course_id).count()
        total_assignments = self.db.query(models.Assignment).filter_by(course_id=course_id).count()
        
        upcoming_deadlines = self.db.query(models.Assignment).filter(
            models.Assignment.course_id == course_id,
            models.Assignment.due_date >= datetime.utcnow()
        ).count()

        return {
            "total_students": total_students,
            "total_assignments": total_assignments,
            "upcoming_deadlines": upcoming_deadlines
        }

    def get_engagement_timeline(self, course_id: int, days: int = 7):
        """Returns daily activity counts from PostgreSQL to ensure consistency with status charts."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 1. Posts
        posts = self.db.query(models.Post.timestamp).filter(
            models.Post.course_id == course_id, 
            models.Post.timestamp >= start_date
        ).all()

        # 2. Submissions (Join Assignment to filter by course)
        submissions = self.db.query(models.Submission.timestamp).join(models.Assignment).filter(
            models.Assignment.course_id == course_id,
            models.Submission.timestamp >= start_date
        ).all()
        
        # Initialize days
        daily_stats = {}
        for i in range(days):
            date_key = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_stats[date_key] = {"posts": 0, "submissions": 0}

        # Aggregate Posts
        for p in posts:
            if p.timestamp:
                 k = p.timestamp.strftime('%Y-%m-%d')
                 if k in daily_stats: daily_stats[k]["posts"] += 1
        
        # Aggregate Submissions
        for s in submissions:
             if s.timestamp:
                 k = s.timestamp.strftime('%Y-%m-%d')
                 if k in daily_stats: daily_stats[k]["submissions"] += 1
        
        # Convert to sorted list
        timeline = []
        for date_key in sorted(daily_stats.keys()):
            stats = daily_stats[date_key]
            timeline.append({
                "date": date_key,
                "posts": stats["posts"],
                "submissions": stats["submissions"]
            })
        return timeline

    def get_assignment_analytics(self, course_id: int):
        """Returns submission status and grade distributions."""
        assignments = self.db.query(models.Assignment).filter_by(course_id=course_id).all()
        enrolled_count = self.db.query(models.CourseEnrollment).filter_by(course_id=course_id).count()
        
        if not assignments:
            return {}

        total_submissions = 0
        late_submissions = 0
        missing_submissions = 0
        
        grades_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        
        for assignment in assignments:
            submissions = self.db.query(models.Submission).filter_by(assignment_id=assignment.id).all()
            
            submitted_user_ids = {sub.student_id for sub in submissions}
            missing = max(0, enrolled_count - len(submitted_user_ids))
            
            total_submissions += len(submissions)
            missing_submissions += missing
            
            for sub in submissions:
                if sub.timestamp and assignment.due_date and sub.timestamp > assignment.due_date:
                    late_submissions += 1
                
                # Grade is Integer
                if sub.grade is not None:
                    g = sub.grade
                    if g >= 90: grades_dist["A"] += 1
                    elif g >= 80: grades_dist["B"] += 1
                    elif g >= 70: grades_dist["C"] += 1
                    elif g >= 60: grades_dist["D"] += 1
                    else: grades_dist["F"] += 1

        status_breakdown = {
            "submitted": total_submissions - late_submissions,
            "late": late_submissions,
            "missing": missing_submissions
        }

        return {
            "status_breakdown": status_breakdown,
            "grades_distribution": grades_dist
        }

    def get_assignment_difficulty(self, course_id: int):
        """Calculates difficulty indicators per assignment."""
        assignments = self.db.query(models.Assignment).filter_by(course_id=course_id).all()
        data = []
        
        for a in assignments:
            subs = self.db.query(models.Submission).filter_by(assignment_id=a.id).all()
            count = len(subs)
            if count == 0:
                avg_grade = 0
            else:
                # Grade is Integer
                valid_grades = [s.grade for s in subs if s.grade is not None]
                if valid_grades:
                    avg_grade = sum(valid_grades) / len(valid_grades)
                else:
                    avg_grade = 0
            
            data.append({
                "title": a.title,
                "submission_count": count,
                "avg_grade": round(avg_grade, 2)
            })
            
        return data

    def get_course_completion(self, course_id: int):
        """Estimates course completion status."""
        enrolled = self.db.query(models.CourseEnrollment).filter_by(course_id=course_id).count()
        assignments = self.db.query(models.Assignment).filter_by(course_id=course_id).count()
        
        if enrolled == 0 or assignments == 0:
            return 0
            
        total_possible_subs = enrolled * assignments
        actual_subs = self.db.query(models.Submission).join(models.Assignment).filter(models.Assignment.course_id == course_id).count()
        
        return round((actual_subs / total_possible_subs) * 100, 1)
