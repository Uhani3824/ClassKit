from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import io
from app.api.v1.endpoints.auth import get_current_user
from app.core.auth import get_password_hash
from app.core import database, minio_client, config
from app.models import postgresql as models
from app.schemas import user as schemas

router = APIRouter()

@router.put("/me", response_model=schemas.User)
def update_profile(
    name: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if name:
        current_user.name = name
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password")
def update_password(
    password_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    current_password = password_data.get("current_password")
    new_password = password_data.get("new_password")
    
    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Both current and new password are required")
    
    if not pwd_context.verify(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.put("/me/profile-picture", response_model=schemas.User)
async def update_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    content = await file.read()
    file_name = f"profile_pictures/{current_user.id}/{uuid.uuid4()}_{file.filename}"
    bucket = config.settings.MINIO_BUCKET_ATTACHMENTS
    client = minio_client.get_minio_client()
    
    client.put_object(
        bucket, file_name,
        data=io.BytesIO(content),
        length=len(content),
        content_type=file.content_type
    )
    
    current_user.profile_picture_url = f"/api/v1/stream/attachments/{file_name}"
    db.commit()
    db.refresh(current_user)
    
    return current_user
