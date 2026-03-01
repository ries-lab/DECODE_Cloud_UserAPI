import gzip
import sqlite3
import tempfile
import time
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import settings
from api.core.database import Database, SqliteDatabase
from api.core.filesystem import FileSystem, S3Filesystem
from api.dependencies import db_dep
from api.main import app
from api.models import Job
from tests.conftest import S3TestingBucket


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestCronBackupDatabase:
    @pytest.fixture(autouse=True)
    def skip_if_not_sqlite_s3(self, db: Database, base_filesystem: FileSystem) -> None:
        """Skip tests if not using SQLite DB with S3 filesystem."""
        if not isinstance(db, SqliteDatabase) or not isinstance(
            base_filesystem, S3Filesystem
        ):
            pytest.skip("Backup tests only run with SQLite DB and S3 filesystem")

    @pytest.fixture(autouse=True)
    def setup_backup_cron_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set backup cron interval to 1 seconds for faster testing."""
        monkeypatch.setattr(settings, "cron_backup_interval", 1)

    def get_backup_nrows(self, s3_testing_bucket: S3TestingBucket) -> int:
        """Helper to get number of rows in backup database."""
        response = s3_testing_bucket.s3_client.get_object(
            Bucket=s3_testing_bucket.bucket_name,
            Key=SqliteDatabase.BACKUP_KEY,
        )
        backup_data_gzip = response["Body"].read()
        backup_data = gzip.decompress(backup_data_gzip)
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp_file:
            tmp_file.write(backup_data)
            tmp_path = tmp_file.name
            conn = sqlite3.connect(tmp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            n_rows = cursor.fetchone()[0]
            conn.close()
        return cast(int, n_rows)

    def test_sqlite_backup(
        self,
        db: SqliteDatabase,
        jobs: list[Job],
        client: TestClient,
        s3_testing_bucket: S3TestingBucket,
        tmpdir_factory: pytest.TempdirFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test the backup and restore functionality of the SQLiteRDSJobQueue."""
        # Startup: no backup present
        with pytest.raises(s3_testing_bucket.s3_client.exceptions.NoSuchKey):
            self.get_backup_nrows(s3_testing_bucket)

        with client:
            # First start-up: no jobs
            time.sleep(2)  # wait for backup to run
            assert self.get_backup_nrows(s3_testing_bucket) == 0

            # Enqueue a job and verify it's backed up
            with Session(db.engine) as session:
                session.add(jobs[0])
                session.commit()
            time.sleep(2)  # wait for backup to run
            assert self.get_backup_nrows(s3_testing_bucket) == 1

            # Enqueue a second job and shutdown before backup runs
            with Session(db.engine) as session:
                session.add(jobs[1])
                session.commit()

        # On shutdown, final backup should run with both jobs
        assert self.get_backup_nrows(s3_testing_bucket) == 2

        # New queue (e.g., application started again) should restore from backup
        new_db_url = f"sqlite:///{tmpdir_factory.mktemp('integration') / 'restored.db'}"
        new_db = SqliteDatabase(
            new_db_url,
            s3_client=s3_testing_bucket.s3_client,
            s3_bucket=s3_testing_bucket.bucket_name,
        )
        monkeypatch.setitem(
            app.dependency_overrides,  # type: ignore
            db_dep,
            lambda: new_db,
        )
        with client:
            assert len(client.get("/jobs").json()) == 2
            assert self.get_backup_nrows(s3_testing_bucket) == 2
