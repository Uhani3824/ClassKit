from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, JSON, Enum as SQLEnum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"

class PostType(str, enum.Enum):
    ANNOUNCEMENT = "announcement"
    POST = "post"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'student' or 'teacher'
    profile_picture_url = Column(String, nullable=True)
    
    courses_created = relationship("Course", back_populates="teacher")
    enrollments = relationship("CourseEnrollment", back_populates="user")
    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    submissions = relationship("Submission", back_populates="student")
    notifications = relationship("Notification", back_populates="user")

    __table_args__ = (
        CheckConstraint(role.in_(['student', 'teacher']), name='role_check'),
    )

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    section = Column(String, nullable=True)
    code = Column(String, unique=True, index=True, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    status = Column(String, default="active") # active/inactive
    
    teacher = relationship("User", back_populates="courses_created")
    enrollments = relationship("CourseEnrollment", back_populates="course", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="course", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan")

class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    
    course = relationship("Course", back_populates="enrollments")
    user = relationship("User", back_populates="enrollments")

class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(String, nullable=True)  # Made optional for attachment-only posts
    type = Column(String, nullable=False) # 'announcement' or 'post'
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON, nullable=True)
    
    course = relationship("Course", back_populates="posts")
    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    attachments = relationship("PostAttachment", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(type.in_(['announcement', 'post']), name='post_type_check'),
    )

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")

class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    due_date = Column(DateTime, nullable=False)
    allow_late = Column(Boolean, default=True)
    max_points = Column(Integer, default=100)
    
    course = relationship("Course", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")
    attachments = relationship("AssignmentAttachment", back_populates="assignment", cascade="all, delete-orphan")

class AssignmentAttachment(Base):
    __tablename__ = "assignment_attachments"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    
    assignment = relationship("Assignment", back_populates="attachments")

class PostAttachment(Base):
    __tablename__ = "post_attachments"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    
    post = relationship("Post", back_populates="attachments")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    submission_text = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    grade = Column(Integer, nullable=True)
    is_late = Column(Boolean, default=False)
    
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User", back_populates="submissions")
    attachments = relationship("SubmissionAttachment", back_populates="submission", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('assignment_id', 'student_id', name='unique_submission_per_student'),
    )

class SubmissionAttachment(Base):
    __tablename__ = "submission_attachments"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    
    submission = relationship("Submission", back_populates="attachments")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    reference_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")
