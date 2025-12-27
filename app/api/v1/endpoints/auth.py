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
        <html><body>
            <h1 style="color: red;">Invalid or Expired Link</h1>
            <p>The verification link is invalid or has expired. Please register again.</p>
            <a href="/register">Go to Registration</a>
        </body></html>
        """
    
    user_data = json.loads(raw_data)
    
    # 2. Check overlap again (race condition safety)
    if db.query(models.User).filter(models.User.email == user_data['email']).first():
         redis_client.delete(f"pending_user:{token}")
         return "<html><body><h1>Account already verified!</h1><a href='/login'>Login</a></body></html>"

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
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1 style="color: green;">Email Verified Successfully!</h1>
            <p>Your account has been activated.</p>
            <a href="/login" style="background: #4285f4; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Login</a>
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
