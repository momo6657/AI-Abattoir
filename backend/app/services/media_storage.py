import uuid
from typing import Optional
from minio import Minio
from app.core.config import settings


class MediaStorage:
    """媒体文件存储管理"""

    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self.client.bucket_exists(settings.MINIO_BUCKET):
            self.client.make_bucket(settings.MINIO_BUCKET)

    async def upload(
        self, data: bytes, content_type: str, prefix: str = "media"
    ) -> str:
        object_name = f"{prefix}/{uuid.uuid4()}"
        from io import BytesIO

        self.client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return object_name

    async def get_url(self, object_name: str) -> str:
        return self.client.presigned_get_object(
            settings.MINIO_BUCKET, object_name
        )


media_storage = MediaStorage()
