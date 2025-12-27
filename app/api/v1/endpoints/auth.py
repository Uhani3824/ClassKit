from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core import auth, database
from app.core.config import settings
from app.models import postgresql as models
from app.schemas import user as schemas
from app.core.redis_db import redis_client

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

@router.post("/register", response_model=schemas.User)
def register(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    obj_in_data = user_in.dict()
    password = obj_in_data.pop("password")
    hashed_password = auth.get_password_hash(password)
    db_user = models.User(**obj_in_data, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

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
