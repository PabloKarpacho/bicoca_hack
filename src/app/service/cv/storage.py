from pathlib import Path

from app.config import settings
from database.s3.db import S3


class CVStorageService:
    def __init__(self, s3: S3, bucket_name: str | None = None) -> None:
        self.s3 = s3
        self.bucket_name = bucket_name or settings.s3_files_bucket_name

    def build_object_key(self, document_id: str, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return f"cv/originals/{document_id}{suffix}"

    async def upload_original(
        self,
        *,
        document_id: str,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> str:
        object_key = self.build_object_key(document_id=document_id, filename=filename)
        await self.s3.upload_bytes(
            data=data,
            key=object_key,
            bucket_name=self.bucket_name,
            content_type=content_type,
            metadata={"document_id": document_id},
        )
        return object_key

    async def get_download_url(
        self,
        *,
        key: str,
        bucket_name: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        """Return a presigned download URL for a stored CV object."""
        return await self.s3.generate_presigned_download_url(
            key=key,
            bucket_name=bucket_name or self.bucket_name,
            url_expiry=expires_in,
        )
