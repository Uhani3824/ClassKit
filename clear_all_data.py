import sys
import os

# Add the project root to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.core.database import engine
from app.models.postgresql import Base
from app.core.redis_db import redis_client
from app.core.cassandra_db import get_cassandra_session, cassandra_client
from app.core.minio_client import minio_client
from app.core.config import settings

from sqlalchemy import text

def clear_postgres():
    print("Clearing PostgreSQL...")
    with engine.connect() as conn:
        # Get all table names in the public schema
        result = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"))
        tables = [row[0] for row in result]
        if tables:
            print(f"Dropping tables: {', '.join(tables)}")
            conn.execute(text(f"DROP TABLE {', '.join(tables)} CASCADE"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    print("PostgreSQL cleared and tables recreated.")

def clear_redis():
    print("Clearing Redis...")
    try:
        redis_client.flushall()
        print("Redis cleared.")
    except Exception as e:
        print(f"Error clearing Redis: {e}")

def clear_cassandra():
    print("Clearing Cassandra...")
    try:
        session = get_cassandra_session()
        # Drop keyspace and recreate it (simplest way to clear all tables)
        session.execute(f"DROP KEYSPACE IF EXISTS {settings.CASSANDRA_KEYSPACE}")
        # Re-initialization
        cassandra_client.create_keyspace()
        cassandra_client.session.set_keyspace(settings.CASSANDRA_KEYSPACE)
        cassandra_client.create_tables()
        print("Cassandra cleared and keyspace recreated.")
    except Exception as e:
        print(f"Error clearing Cassandra: {e}")

def clear_minio():
    print("Clearing MinIO...")
    try:
        buckets = [settings.MINIO_BUCKET_ATTACHMENTS, settings.MINIO_BUCKET_SUBMISSIONS]
        for bucket in buckets:
            if minio_client.bucket_exists(bucket):
                # List all objects and delete them
                objects = minio_client.list_objects(bucket, recursive=True)
                for obj in objects:
                    minio_client.remove_object(bucket, obj.object_name)
        print("MinIO buckets cleared.")
    except Exception as e:
        print(f"Error clearing MinIO: {e}")

if __name__ == "__main__":
    clear_postgres()
    clear_redis()
    clear_cassandra()
    clear_minio()
    print("All backend data has been cleared.")
