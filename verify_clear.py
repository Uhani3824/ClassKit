from app.core.database import SessionLocal
from app.models.postgresql import User

db = SessionLocal()
user_count = db.query(User).count()
print(f"User count: {user_count}")
db.close()
