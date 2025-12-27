from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from .config import settings
import logging

class CassandraClient:
    def __init__(self):
        self.cluster = None
        self.session = None

    def connect(self):
        self.cluster = Cluster([settings.CASSANDRA_HOST], port=settings.CASSANDRA_PORT)
        self.session = self.cluster.connect()
        self.create_keyspace()
        self.session.set_keyspace(settings.CASSANDRA_KEYSPACE)
        self.create_tables()

    def create_keyspace(self):
        self.session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {settings.CASSANDRA_KEYSPACE}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': '1'}}
        """)

    def create_tables(self):
        # Event logs for analytics
        self.session.execute(f"""
            CREATE TABLE IF NOT EXISTS event_logs (
                event_id uuid,
                event_type text,
                user_id int,
                course_id int,
                details text,
                event_time timestamp,
                PRIMARY KEY (course_id, event_time, event_id)
            ) WITH CLUSTERING ORDER BY (event_time DESC, event_id ASC);
        """)

        # Notification history
        self.session.execute(f"""
            CREATE TABLE IF NOT EXISTS notification_history (
                user_id int,
                notification_id uuid,
                type text,
                reference_id int,
                message text,
                is_read boolean,
                created_at timestamp,
                PRIMARY KEY (user_id, created_at, notification_id)
            ) WITH CLUSTERING ORDER BY (created_at DESC, notification_id ASC);
        """)

    def close(self):
        if self.cluster:
            self.cluster.shutdown()

cassandra_client = CassandraClient()

def get_cassandra_session():
    if not cassandra_client.session:
        cassandra_client.connect()
    return cassandra_client.session
