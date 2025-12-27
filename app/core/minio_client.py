from minio import Minio
from .config import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False
)

def init_minio():
    buckets = [settings.MINIO_BUCKET_ATTACHMENTS, settings.MINIO_BUCKET_SUBMISSIONS]
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)

def get_minio_client():
    return minio_client
