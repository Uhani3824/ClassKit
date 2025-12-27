from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.models import postgresql as models
from app.services.notification_service import NotificationService

router = APIRouter()

@router.get("/unread")
def get_unread(current_user: models.User = Depends(get_current_user)):
    return NotificationService.get_unread_notifications(current_user.id)

@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    NotificationService.mark_as_read(db, current_user.id, notification_id)
    return {"message": "Marked as read"}

@router.post("/clear-all")
def clear_all(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Mark all unread notifications as read
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications cleared"}
