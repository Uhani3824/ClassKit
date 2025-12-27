from sqlalchemy.orm import Session
from app.models import postgresql as models
from app.core.redis_db import redis_client
from app.core.cassandra_db import get_cassandra_session
import uuid
import json
from datetime import datetime

class NotificationService:
    @staticmethod
    def create_notification(db: Session, user_id: int, type: str, reference_id: int, message: str, metadata: dict = None):
        # 1. Store in PostgreSQL
        db_notif = models.Notification(
            user_id=user_id,
            type=type,
            reference_id=reference_id,
            is_read=False
        )
        db.add(db_notif)
        db.commit()
        db.refresh(db_notif)
        
        # 2. Store in Redis (List for unread)
        notif_data = {
            "id": db_notif.id,
            "type": type,
            "reference_id": reference_id,
            "message": message,
            "timestamp": str(db_notif.timestamp),
            "metadata": metadata or {}
        }
        redis_client.lpush(f"user:{user_id}:notifications", json.dumps(notif_data))
        # Optional: trim list
        redis_client.ltrim(f"user:{user_id}:notifications", 0, 49)
        
        # 3. Store in Cassandra (History)
        try:
            cassandra_session = get_cassandra_session()
            if cassandra_session:
                query = """
                    INSERT INTO notification_history (user_id, notification_id, type, reference_id, message, is_read, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cassandra_session.execute(query, (
                    user_id, uuid.uuid4(), type, reference_id, message, False, datetime.utcnow()
                ))
        except Exception as e:
            print(f"Failed to store notification history in Cassandra: {e}")
        
        return db_notif

    @staticmethod
    def get_unread_notifications(user_id: int):
        notifs = redis_client.lrange(f"user:{user_id}:notifications", 0, -1)
        return [json.loads(n) for n in notifs]

    @staticmethod
    def mark_as_read(db: Session, user_id: int, notification_id: int):
        # 1. Update DB
        db_notif = db.query(models.Notification).filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id
        ).first()
        
        if db_notif:
            db_notif.is_read = True
            db.commit()
            
            # 2. Update Redis: Filter out the read notification
            redis_key = f"user:{user_id}:notifications"
            current_notifs = redis_client.lrange(redis_key, 0, -1)
            redis_client.delete(redis_key)
            
            for n_str in current_notifs:
                try:
                    n_json = json.loads(n_str)
                    if n_json.get("id") != notification_id:
                        redis_client.rpush(redis_key, n_str)
                except:
                    continue
                    
        return True
