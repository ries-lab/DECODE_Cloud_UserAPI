import shutil
from io import BytesIO
from typing import Any, Callable, Generator
from unittest.mock import Mock

import pytest
from fastapi_cloudauth.cognito import CognitoClaims  # type: ignore
from mypy_boto3_s3 import S3Client
from sqlalchemy.orm import Session

from api import settings
from api.core import notifications
from api.core.auth import APIKeyDependency
from api.core.database import Database, SqliteDatabase
from api.core.filesystem import (
    FileSystem,
    LocalFilesystem,
    S3Filesystem,
    user_filesystem_getter,
)
from api.dependencies import (
    current_user_dep,
    db_dep,
    email_sender_dep,
    filesystem_getter_dep,
    workerfacing_api_auth_dep,
)
from api.main import app
from api.models import Job
from tests.conftest import RDSTestingInstance, S3TestingBucket


@pytest.fixture(scope="session")
def test_username() -> str:
    return "test_user"


@pytest.fixture(scope="session")
def test_user_email() -> str:
    return "user@example.com"


@pytest.fixture(scope="session")
def base_user_dir() -> str:
    return "test_user_dir"


@pytest.fixture(scope="session")
def internal_api_key_secret() -> str:
    return "test_internal_api_key"


@pytest.fixture(scope="session")
def application() -> dict[str, str]:
    return {"application": "app", "version": "latest", "entrypoint": "test"}


@pytest.fixture(
    scope="session",
    params=["local-fs", pytest.param("aws-fs", marks=pytest.mark.aws)],
)
def base_filesystem(
    base_user_dir: str,
    s3_testing_bucket: S3TestingBucket,
    request: pytest.FixtureRequest,
) -> FileSystem:
    if request.param == "local-fs":
        return LocalFilesystem(base_user_dir)
    elif request.param == "aws-fs":
        s3_testing_bucket.create()
        return S3Filesystem(
            base_user_dir, s3_testing_bucket.s3_client, s3_testing_bucket.bucket_name
        )
    else:
        raise NotImplementedError


@pytest.fixture(
    scope="session",
    params=["local-db", pytest.param("aws-db", marks=pytest.mark.aws)],
)
def db(
    base_filesystem: FileSystem,
    s3_testing_bucket: S3TestingBucket,
    rds_testing_instance: RDSTestingInstance,
    tmpdir_factory: pytest.TempdirFactory,
    request: pytest.FixtureRequest,
) -> Database:
    if request.param == "local-db":
        test_db_path = tmpdir_factory.mktemp("integration") / "test_app.db"
        s3_bucket: str | None = None
        s3_client: S3Client | None = None
        if isinstance(base_filesystem, S3Filesystem):
            s3_bucket = s3_testing_bucket.bucket_name
            s3_client = s3_testing_bucket.s3_client
        return SqliteDatabase(
            db_url=f"sqlite:///{test_db_path}", s3_client=s3_client, s3_bucket=s3_bucket
        )
    elif request.param == "aws-db":
        if isinstance(base_filesystem, LocalFilesystem):
            pytest.skip("Only testing RDS DB in combination with S3 filesystem")
        rds_testing_instance.create()
        return Database(db_url=rds_testing_instance.db_url)
    else:
        raise NotImplementedError


@pytest.fixture
def filesystem_getter(
    base_filesystem: FileSystem,
    base_user_dir: str,
    s3_testing_bucket: S3TestingBucket,
) -> Callable[[str], FileSystem]:
    return user_filesystem_getter(
        user_data_root_path=base_user_dir,
        filesystem="s3" if isinstance(base_filesystem, S3Filesystem) else "local",
        s3_bucket=s3_testing_bucket.bucket_name,
        s3_client=s3_testing_bucket.s3_client,
    )


@pytest.fixture
def user_filesystem(
    filesystem_getter: Callable[[str], FileSystem], test_username: str
) -> FileSystem:
    return filesystem_getter(test_username)


@pytest.fixture(autouse=True)
def override_db_dep(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,  # type: ignore
        db_dep,
        lambda: db,
    )


@pytest.fixture(autouse=True)
def override_user_filesystem_getter(
    filesystem_getter: Callable[[str], FileSystem],
    base_filesystem: FileSystem,
    s3_testing_bucket: S3TestingBucket,
    base_user_dir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    monkeypatch.setitem(
        app.dependency_overrides,  # type: ignore
        filesystem_getter_dep,
        lambda: filesystem_getter,
    )
    yield
    # cleanup after every test
    if isinstance(base_filesystem, S3Filesystem):
        s3_testing_bucket.cleanup()
    else:
        shutil.rmtree(base_user_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def override_auth(
    monkeypatch: pytest.MonkeyPatch, test_username: str, test_user_email: str
) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,  # type: ignore
        current_user_dep,
        lambda: CognitoClaims(
            **{"cognito:username": test_username, "email": test_user_email}
        ),
    )


@pytest.fixture(autouse=True)
def override_internal_api_key_secret(
    monkeypatch: pytest.MonkeyPatch, internal_api_key_secret: str
) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,  # type: ignore
        workerfacing_api_auth_dep,
        APIKeyDependency(internal_api_key_secret),
    )


@pytest.fixture(autouse=True)
def override_email_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,  # type: ignore
        email_sender_dep,
        lambda: notifications.DummyEmailSender(),
    )


@pytest.fixture(autouse=True)
def override_application_config(
    monkeypatch: pytest.MonkeyPatch, application: dict[str, str]
) -> None:
    application_config = Mock()
    application_config.config = {
        application["application"]: {
            application["version"]: {
                application["entrypoint"]: {
                    "app": {
                        "cmd": ["python", "test.py"],
                        "env": ["TEST_ENV"],
                    },
                    "handler": {
                        "image_url": "url_test",
                        "image_name": "name_test",
                        "image_version": "version_test",
                        "files_down": {
                            "data_ids": ["data"],
                            "config_id": ["config"],
                        },
                        "files_up": {
                            "output": "output",
                            "log": "log",
                            "artifact": "artifact",
                        },
                    },
                },
            },
        },
    }
    monkeypatch.setattr(settings, "application_config", application_config)


@pytest.fixture
def require_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(app.dependency_overrides, current_user_dep)  # type: ignore


@pytest.fixture
def data_files(user_filesystem: FileSystem) -> dict[str, str]:
    data_file1_name = "data/test/data_file1.txt"
    data_file1_contents = "data file1 contents"
    data_file2_name = "data/test/data_file2.txt"
    data_file2_contents = "data file2 contents"
    user_filesystem.create_file(
        data_file1_name, BytesIO(bytes(data_file1_contents, "utf-8"))
    )
    user_filesystem.create_file(
        data_file2_name, BytesIO(bytes(data_file2_contents, "utf-8"))
    )
    return {data_file1_name: data_file1_contents, data_file2_name: data_file2_contents}


@pytest.fixture
def config_files(user_filesystem: FileSystem) -> dict[str, str]:
    config_file1_name = "config/test/config_file1.txt"
    config_file1_contents = "config file1 contents"
    config_file2_name = "config/test/config_file2.txt"
    config_file2_contents = "config file2 contents"
    user_filesystem.create_file(
        config_file1_name, BytesIO(bytes(config_file1_contents, "utf-8"))
    )
    user_filesystem.create_file(
        config_file2_name, BytesIO(bytes(config_file2_contents, "utf-8"))
    )
    return {
        config_file1_name: config_file1_contents,
        config_file2_name: config_file2_contents,
    }


@pytest.fixture(scope="session")
def job_attrs() -> dict[str, Any]:
    return {
        "files_down": {"data_ids": ["test"], "config_id": "test", "artifact_ids": []},
        "env_vars": {},
    }


@pytest.fixture
def jobs(
    test_username: str,
    test_user_email: str,
    application: dict[str, str],
    job_attrs: dict[str, Any],
    db_session: Session,
) -> list[Job]:
    job1 = Job(
        id=42,
        user_id=test_username,
        user_email=test_user_email,
        job_name="job_test_1",
        environment="cloud",
        application=application,
        attributes=job_attrs,
        hardware={},
        paths_out={"output": "out", "log": "log", "artifact": "model"},
    )
    job2 = Job(
        id=50,
        user_id=test_username,
        user_email=test_user_email,
        job_name="job_test_2",
        environment=None,
        application=application,
        attributes=job_attrs,
        hardware={},
        paths_out={"output": "out", "log": "log", "artifact": "model"},
    )
    for job in [job1, job2]:
        db_session.add(job)
    db_session.commit()
    return [job1, job2]


@pytest.fixture
def foreign_job(
    application: dict[str, str], job_attrs: dict[str, Any], db_session: Session
) -> Job:
    job = Job(
        id=999,
        user_id="foreign_user",
        job_name="job_test_3",
        environment=None,
        application=application,
        attributes=job_attrs,
        hardware={},
        paths_out={"output": "out", "log": "log", "artifact": "model"},
    )
    db_session.add(job)
    db_session.commit()
    return job
