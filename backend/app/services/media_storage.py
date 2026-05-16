import asyncio
import uuid
from typing import Optional
from minio import Minio
from app.core.config import settings


class MediaStorage:
    """媒体文件存储管理"""

    def __init__(self):
        self.client = None
        self._initialized = False

    def _initialize(self):
        """Lazily initialize the MinIO client and ensure the bucket exists."""
        if self._initialized:
            return
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        if not self.client.bucket_exists(settings.MINIO_BUCKET):
            self.client.make_bucket(settings.MINIO_BUCKET)
        self._initialized = True

    async def upload(
        self, data: bytes, content_type: str, prefix: str = "media"
    ) -> str:
        await asyncio.to_thread(self._initialize)
        object_name = f"{prefix}/{uuid.uuid4()}"
        from io import BytesIO

        await asyncio.to_thread(
            self.client.put_object,
            settings.MINIO_BUCKET,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return object_name

    async def get_url(self, object_name: str) -> str:
        await asyncio.to_thread(self._initialize)
        return await asyncio.to_thread(
            self.client.presigned_get_object,
            settings.MINIO_BUCKET,
            object_name,
        )


media_storage = MediaStorage()
