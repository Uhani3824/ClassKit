from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine
from app.models.postgresql import Base
from app.core import cassandra_db
from app.core.minio_client import init_minio
from app.api.v1.endpoints import auth, courses, stream, assignments, analytics, pages, notifications, users
import uvicorn

# Create PostgreSQL tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        cassandra_db.cassandra_client.connect()
    except Exception as e:
        print(f"Error connecting to Cassandra: {e}")
    
    try:
        init_minio()
    except Exception as e:
        print(f"Error initializing MinIO: {e}")
    
    yield
    
    # Shutdown logic
    cassandra_db.cassandra_client.close()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Include Routers
app.include_router(pages.router, tags=["pages"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["courses"])
app.include_router(stream.router, prefix="/api/v1/stream", tags=["stream"])
app.include_router(assignments.router, prefix="/api/v1/assignments", tags=["assignments"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
