import gzip
import os
import sqlite3
import tempfile
import time
from typing import Any, cast

from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3Client
from sqlalchemy import Engine, create_engine

from api.models import Base


class Database:
    """Database wrapper."""

    def __init__(
        self,
        db_url: str,
        connect_kwargs: dict[str, Any] | None = None,
    ):
        self.db_url = db_url
        self.connect_kwargs = connect_kwargs or {}

    @property
    def engine(self) -> Engine:
        if hasattr(self, "_engine"):
            return cast(Engine, self._engine)  # type: ignore[has-type]
        retries = 0
        while True:
            try:
                engine = create_engine(self.db_url, connect_args=self.connect_kwargs)
                # Attempt to create a connection or perform any necessary operations
                engine.connect()
                self._engine = engine
                return engine  # Connection successful
            except Exception as e:
                if retries >= 10:
                    raise RuntimeError(f"Could not create engine: {str(e)}")
                retries += 1
                time.sleep(60)

    def create(self) -> None:
        """Create database tables."""
        Base.metadata.create_all(bind=self.engine)

    def backup(self) -> bool:
        """Backup the database. To be implemented by subclasses if supported."""
        return False

    def empty(self) -> None:
        """Empty the database by dropping and recreating all tables."""
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)


class SqliteDatabase(Database):
    """SQLite database wrapper with optional S3 backup support."""

    BACKUP_KEY = "userapi_sqlite_backup/backup.db.gz"

    def __init__(
        self,
        db_url: str,
        s3_client: S3Client | None = None,
        s3_bucket: str | None = None,
    ):
        if not db_url.startswith("sqlite:///"):
            raise ValueError(f"SQLiteRDSJobQueue requires SQLite DB URL, got: {db_url}")
        if not ((s3_client is None) == (s3_bucket is None)):
            raise ValueError(
                "Both s3_client and s3_bucket must be provided for S3 backup/restore, or both must be None."
            )
        self.s3_client = s3_client
        self.s3_bucket = s3_bucket
        super().__init__(db_url, connect_kwargs={"check_same_thread": False})

    def create(self) -> None:
        self._restore_database()
        super().create()

    @property
    def db_path(self) -> str:
        return self.db_url[len("sqlite:///") :]

    def backup(self) -> bool:
        """Backup the SQLite database to S3."""
        if not self.s3_bucket or not self.s3_client:
            return False

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_backup_path = os.path.join(temp_dir, "backup.db")
            tmp_gzip_path = os.path.join(temp_dir, "backup.db.gz")
            with sqlite3.connect(self.db_path) as source_conn:
                with sqlite3.connect(tmp_backup_path) as backup_conn:
                    source_conn.backup(backup_conn)

            with open(tmp_backup_path, "rb") as f_in:
                with gzip.open(tmp_gzip_path, "wb") as f_out:
                    f_out.writelines(f_in)
            self.s3_client.upload_file(tmp_gzip_path, self.s3_bucket, self.BACKUP_KEY)
            return True

    def _restore_database(self) -> bool:
        """Restore the SQLite database from S3."""
        if not self.s3_bucket or not self.s3_client:
            return False

        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=self.BACKUP_KEY)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_gzip_path = os.path.join(temp_dir, "backup.db.gz")
            tmp_backup_path = os.path.join(temp_dir, "backup.db")
            self.s3_client.download_file(self.s3_bucket, self.BACKUP_KEY, tmp_gzip_path)
            with gzip.open(tmp_gzip_path, "rb") as f_in:
                with open(tmp_backup_path, "wb") as f_out:
                    f_out.write(f_in.read())
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            os.rename(tmp_backup_path, self.db_path)
            return True
