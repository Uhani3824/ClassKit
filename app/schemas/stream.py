from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.models.postgresql import PostType

class CommentBase(BaseModel):
    text: str

class CommentCreate(CommentBase):
    post_id: int

class Comment(CommentBase):
    id: int
    post_id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class PostAttachmentBase(BaseModel):
    file_url: str
    filename: str

class PostAttachment(PostAttachmentBase):
    id: int
    post_id: int

    class Config:
        from_attributes = True

class PostBase(BaseModel):
    text: Optional[str] = None
    type: PostType

class PostCreate(PostBase):
    course_id: int

class Post(PostBase):
    id: int
    course_id: int
    user_id: int
    timestamp: datetime
    metadata_json: Optional[Any] = None
    comments: List[Comment] = []
    attachments: List[PostAttachment] = []

    class Config:
        from_attributes = True
