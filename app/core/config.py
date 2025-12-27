from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Class-Kit"
    
    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    
    # Cassandra
    CASSANDRA_HOST: str
    CASSANDRA_PORT: int
    CASSANDRA_KEYSPACE: str
    
    # MinIO
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_ENDPOINT: str
    MINIO_BUCKET_ATTACHMENTS: str
    MINIO_BUCKET_SUBMISSIONS: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email (SMTP)
    MAIL_USERNAME: str = "apikey" # Default for SendGrid etc, or blank
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@classkit.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "Class-Kit Support"
    
    class Config:
        env_file = ".env"

settings = Settings()
