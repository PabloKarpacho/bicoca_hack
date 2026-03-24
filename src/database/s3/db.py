from loguru import logger
import aioboto3

from typing import BinaryIO
from io import BytesIO


class S3:

    def __init__(
        self,
        s3_access_key_id: str,
        s3_secret_access_key: str,
        endpoint_url: str,
        region_name: str = "us-east-1",
    ) -> None:
        """
        Initializes the S3 session.

        Args:
            aws_access_key_id (str): S3 access key ID
            aws_secret_access_key (str): S3 secret access key
            endpoint_url (str): S3 endpoint URL
        """
        self.endpoint_url = endpoint_url

        self._session = aioboto3.Session(
            aws_access_key_id=s3_access_key_id,
            aws_secret_access_key=s3_secret_access_key,
            region_name=region_name,
        )

    async def create_bucket(self, bucket_name: str) -> None:
        """
        Initializes the S3 bucket if it does not exist.
        Args:
            bucket_name (str): Name of the S3 bucket to create.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as s3:
            existing_buckets = await s3.list_buckets()
            bucket_names = [b["Name"] for b in existing_buckets.get("Buckets", [])]

            if bucket_name not in bucket_names:
                await s3.create_bucket(Bucket=bucket_name)
                logger.info(
                    "Created S3 bucket: {bucket_name}".format(bucket_name=bucket_name)
                )
            else:
                logger.info(
                    "S3 bucket already exists: {bucket_name}".format(
                        bucket_name=bucket_name
                    )
                )

    async def put_bucket_lifecycle_configuration(
        self,
        bucket_name: str,
        rules: list[dict],
    ) -> None:
        """
        Sets the bucket lifecycle configuration for the specified S3 bucket.

        Args:
            bucket_name (str): Name of the S3 bucket.
            rules (list[dict]): The bucket lifecycle configuration to set.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as s3:
            existing_buckets = await s3.list_buckets()
            bucket_names = [b["Name"] for b in existing_buckets.get("Buckets", [])]

            if bucket_name not in bucket_names:
                raise ValueError(f"Bucket {bucket_name} does not exist.")

            await s3.put_bucket_lifecycle_configuration(
                Bucket=bucket_name, LifecycleConfiguration={"Rules": rules}
            )

    async def upload_file(
        self,
        fileobj: BinaryIO | str,
        key: str,
        bucket_name: str,
        url_expiry: int = 3600,
        file_id: str | None = None,
    ) -> str:
        """
        Uploads a file to the specified S3 bucket.
        Args:
            fileobj (BinaryIO): File-like object to upload.
            key (str): Key (path) in the S3 bucket where the file will be stored.
            bucket_name (str): Name of the S3 bucket.
            url_expiry (int): Expiry time in seconds for the presigned URL.
            file_id (str): Optional file ID to store as metadata.
        Returns:
            str: Presigned URL of the uploaded file.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as s3:
            logger.info(
                "Uploading file to S3: bucket={bucket_name}, key={key}, file_id={file_id}".format(
                    bucket_name=bucket_name, key=key, file_id=file_id
                )
            )

            extra_args = {}
            if file_id:
                extra_args["Metadata"] = {"file_id": file_id}

            if isinstance(fileobj, str):
                await s3.upload_file(
                    Filename=fileobj,
                    Bucket=bucket_name,
                    Key=key,
                    ExtraArgs=extra_args if extra_args else None,
                )
            elif isinstance(fileobj, BinaryIO):
                await s3.upload_fileobj(
                    Fileobj=fileobj,
                    Bucket=bucket_name,
                    Key=key,
                    ExtraArgs=extra_args if extra_args else None,
                )
            else:
                raise ValueError("fileobj must be a file path or a BinaryIO object")

            logger.info(
                "File uploaded to S3: bucket={bucket_name}, key={key}".format(
                    bucket_name=bucket_name, key=key
                )
            )

            url = await s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket_name, "Key": key},
                ExpiresIn=url_expiry,
            )

        return url

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        bucket_name: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Upload raw bytes to S3-compatible storage."""
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as s3:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            if metadata:
                extra_args["Metadata"] = metadata

            logger.info(
                "Uploading bytes to S3: bucket={bucket_name}, key={key}".format(
                    bucket_name=bucket_name, key=key
                )
            )
            await s3.upload_fileobj(
                Fileobj=BytesIO(data),
                Bucket=bucket_name,
                Key=key,
                ExtraArgs=extra_args if extra_args else None,
            )

    async def delete_file(
        self,
        key: str,
        bucket_name: str,
    ) -> None:
        """
        Deletes a file from the specified S3 bucket.
        Args:
            key (str): Key (path) in the S3 bucket of the file to delete.
            bucket_name (str): Name of the S3 bucket.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as s3:
            logger.info(
                "Deleting file from S3: bucket={bucket_name}, key={key}".format(
                    bucket_name=bucket_name, key=key
                )
            )

            await s3.delete_object(
                Bucket=bucket_name,
                Key=key,
            )

            logger.info(
                "File deleted from S3: bucket={bucket_name}, key={key}".format(
                    bucket_name=bucket_name, key=key
                )
            )

    async def generate_presigned_download_url(
        self,
        *,
        key: str,
        bucket_name: str,
        url_expiry: int = 3600,
    ) -> str:
        """Generate a presigned download URL for an existing S3 object."""
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
        ) as s3:
            return await s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket_name, "Key": key},
                ExpiresIn=url_expiry,
            )
