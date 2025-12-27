from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import json
import io
from datetime import datetime
from app.api.v1.endpoints.auth import get_current_user
from app.core import database, cassandra_db, minio_client, config
from app.models import postgresql as models
from app.schemas import stream as schemas

router = APIRouter()

@router.get("/attachments/{path:path}")
async def get_attachment(path: str, download: bool = False):
    try:
        client = minio_client.get_minio_client()
        response = client.get_object(config.settings.MINIO_BUCKET_ATTACHMENTS, path)
        
        # Extract filename (it's after the uuid_)
        filename = path.split("/")[-1]
        if "_" in filename:
            filename = filename.split("_", 1)[1]
            
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": f'{disposition}; filename="{filename}"'
        }
        return StreamingResponse(
            response, 
            media_type=response.headers.get('content-type'),
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail="Attachment not found")

def log_event(event_type: str, user_id: int, course_id: int, details: dict):
    try:
        session = cassandra_db.get_cassandra_session()
        if not session:
            return
        event_id = uuid.uuid4()
        details_str = json.dumps(details)
        query = """
            INSERT INTO event_logs (event_id, event_type, user_id, course_id, details, event_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        session.execute(query, (event_id, event_type, user_id, course_id, details_str, datetime.utcnow()))
    except Exception as e:
        print(f"Failed to log event to Cassandra: {e}")

@router.post("/posts", response_model=schemas.Post)
async def create_post(
    course_id: int = Form(...),
    text: Optional[str] = Form(None),
    type: str = Form(...), # 'announcement' or 'post'
    files: List[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not text and not files:
        raise HTTPException(status_code=400, detail="Post must have either text or attachments")

    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check if authorized
    is_teacher = (course.teacher_id == current_user.id)
    is_student = db.query(models.CourseEnrollment).filter(
        models.CourseEnrollment.course_id == course_id,
        models.CourseEnrollment.user_id == current_user.id
    ).first() is not None
    
    if not is_teacher and not is_student:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if type == "announcement" and not is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can create announcements")

    db_post = models.Post(
        course_id=course_id,
        user_id=current_user.id,
        text=text,
        type=type
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    if files:
        for file in files:
            if not file.filename: continue
            content = await file.read()
            file_name = f"posts/{db_post.id}/{uuid.uuid4()}_{file.filename}"
            bucket = config.settings.MINIO_BUCKET_ATTACHMENTS
            client = minio_client.get_minio_client()
            
            client.put_object(
                bucket, file_name,
                data=io.BytesIO(content),
                length=len(content),
                content_type=file.content_type
            )
            
            db_attachment = models.PostAttachment(
                post_id=db_post.id,
                file_url=f"/api/v1/stream/attachments/{file_name}",
                filename=file.filename
            )
            db.add(db_attachment)
        
        db.commit()
        db.refresh(db_post)

    # Log to Cassandra
    log_event(f"{type}_created", current_user.id, course_id, {"post_id": db_post.id})
    
    # Notify all students in the course
    from app.services.notification_service import NotificationService
    enrollments = db.query(models.CourseEnrollment).filter(models.CourseEnrollment.course_id == course_id).all()
    for enrollment in enrollments:
        post_type_label = "announcement" if type == "announcement" else "post"
        NotificationService.create_notification(
            db,
            enrollment.user_id,
            f"{type}_created",
            db_post.id,
            f"New {post_type_label} in {course.title}: {text[:50]}..." if text else f"New {post_type_label} in {course.title}",
            {"course_id": course_id, "post_id": db_post.id}
        )
    
    return db_post

@router.get("/courses/{course_id}/stream", response_model=List[schemas.Post])
def get_stream(
    course_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check authorization (shared with create_post)
    posts = db.query(models.Post).filter(models.Post.course_id == course_id).order_by(models.Post.timestamp.desc()).all()
    return posts

@router.post("/posts/{post_id}/comments", response_model=schemas.Comment)
def create_comment(
    post_id: int,
    comment_in: schemas.CommentBase,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    db_comment = models.Comment(
        post_id=post_id,
        user_id=current_user.id,
        text=comment_in.text
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    # Log to Cassandra
    log_event("comment_added", current_user.id, post.course_id, {"comment_id": db_comment.id, "post_id": post_id})
    
    return db_comment

@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    course = post.course
    is_author = (post.user_id == current_user.id)
    
    if not is_author:
        raise HTTPException(status_code=403, detail="Only the author can delete this post")
        
    # Delete attachments from MinIO
    client = minio_client.get_minio_client()
    bucket = config.settings.MINIO_BUCKET_ATTACHMENTS
    for attachment in post.attachments:
        # file_url is like /api/v1/stream/attachments/posts/58/uuid_filename
        # path is posts/58/uuid_filename
        path = attachment.file_url.split("/attachments/")[-1]
        try:
            client.remove_object(bucket, path)
        except Exception as e:
            print(f"Failed to delete MinIO object {path}: {e}")
            
    db.delete(post)
    db.commit()
    
    log_event("post_deleted", current_user.id, course.id, {"post_id": post_id})
    return {"message": "Post deleted successfully"}
