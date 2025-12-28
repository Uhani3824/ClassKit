from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core import auth, database
from app.core.config import settings
from app.models import postgresql as models
from app.schemas import user as schemas
from app.core.redis_db import redis_client

import uuid
import json
from fastapi.responses import HTMLResponse
from app.services.email_service import EmailService

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_current_user(db: Session = Depends(database.get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = schemas.TokenPayload(sub=int(user_id))
    except (JWTError, ValueError):
        raise credentials_exception
    
    # Check if session exists in Redis
    if not redis_client.get(f"session:{token}"):
        raise HTTPException(status_code=401, detail="Session expired or logged out")
        
    user = db.query(models.User).filter(models.User.id == token_data.sub).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register")
def register(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # 1. Check if user already exists
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    
    # 2. Generate Verification Token
    verification_token = str(uuid.uuid4())
    
    # 3. Store in Redis (Pending) (TTL: 24h)
    user_data = user_in.dict()
    redis_client.setex(
        f"pending_user:{verification_token}",
        86400, # 24 hours
        json.dumps(user_data)
    )
    
    # 4. Send Verification Email
    email_sent = EmailService.send_verification_email(user_in.email, verification_token)
    if not email_sent:
        # Rollback (delete pending user from redis) if email fails - strictly speaking optional but good practice
        redis_client.delete(f"pending_user:{verification_token}")
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please check your email configuration.")
        
    return {"message": "Verification email sent. Please check your inbox to activate your account."}

@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(database.get_db)):
    # 1. Retrieve data from Redis
    raw_data = redis_client.get(f"pending_user:{token}")
    if not raw_data:
        return """
        <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
                <style>
                    body { font-family: 'Plus Jakarta Sans', sans-serif; background: #f0f7ff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                    .card { background: white; padding: 3rem; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center; max-width: 400px; width: 90%; }
                    h1 { color: #d93025; font-size: 1.75rem; font-weight: 800; margin-bottom: 1rem; }
                    p { color: #5f6368; line-height: 1.6; margin-bottom: 2rem; }
                    .btn { background: #4285f4; color: white; padding: 0.85rem 1.75rem; text-decoration: none; border-radius: 12px; font-weight: 700; display: inline-block; transition: all 0.2s; }
                    .btn:hover { background: #1a73e8; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(66, 133, 244, 0.3); }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Link Expired</h1>
                    <p>The verification link is invalid or has expired. Please try registering again to get a new link.</p>
                    <a href="/register" class="btn">Go to Registration</a>
                </div>
            </body>
        </html>
        """
    
    user_data = json.loads(raw_data)
    
    # 2. Check overlap again (race condition safety)
    if db.query(models.User).filter(models.User.email == user_data['email']).first():
         redis_client.delete(f"pending_user:{token}")
         return """
         <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
                <style>
                    body { font-family: 'Plus Jakarta Sans', sans-serif; background: #f0f7ff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                    .card { background: white; padding: 3rem; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center; max-width: 400px; width: 90%; }
                    h1 { color: #1e8e3e; font-size: 1.75rem; font-weight: 800; margin-bottom: 1rem; }
                    p { color: #5f6368; line-height: 1.6; margin-bottom: 2rem; }
                    .btn { background: #0c1524; color: white; padding: 0.85rem 1.75rem; text-decoration: none; border-radius: 12px; font-weight: 700; display: inline-block; transition: all 0.2s; }
                    .btn:hover { background: #1a2a44; transform: translateY(-2px); }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Already Verified!</h1>
                    <p>Your account is already active and ready to use.</p>
                    <a href="/login" class="btn">Go to Login</a>
                </div>
            </body>
        </html>
         """

    # 3. Create active user
    password = user_data.pop("password")
    hashed_password = auth.get_password_hash(password)
    db_user = models.User(**user_data, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # 4. Clean up Redis
    redis_client.delete(f"pending_user:{token}")
    
    return """
    <html>
        <head>
            <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
            <style>
                body { font-family: 'Plus Jakarta Sans', sans-serif; background: #f0f7ff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { background: white; padding: 3.5rem 3rem; border-radius: 32px; box-shadow: 0 20px 50px rgba(0,0,0,0.04); text-align: center; max-width: 450px; width: 90%; }
                .success-img { width: 180px; height: auto; margin-bottom: 2.5rem; }
                h1 { color: #1e8e3e; font-size: 1.85rem; font-weight: 800; margin-bottom: 0.75rem; line-height: 1.2; }
                p { color: #5f6368; font-size: 1.05rem; line-height: 1.6; margin-bottom: 2.5rem; }
                .btn { background: #0c1524; color: white; padding: 1rem 2.5rem; text-decoration: none; border-radius: 14px; font-weight: 700; font-size: 1.1rem; display: inline-block; transition: all 0.2s; }
                .btn:hover { background: #1a2a44; transform: translateY(-2px); box-shadow: 0 8px 16px rgba(12, 21, 36, 0.15); }
            </style>
        </head>
        <body>
            <div class="card">
                <img src="/static/images/email-verification-img.png" alt="Email Verified" class="success-img">
                <h1>Email Verified Successfully!</h1>
                <p>Your account has been activated.</p>
                <a href="/login" class="btn">Go to Login</a>
            </div>
        </body>
    </html>
    """

@router.post("/login", response_model=schemas.Token)
def login(db: Session = Depends(database.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = auth.create_access_token(subject=user.id)
    
    # Store session in Redis
    redis_client.setex(
        f"session:{access_token}",
        settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        str(user.id)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    redis_client.delete(f"session:{token}")
    return {"message": "Successfully logged out"}
