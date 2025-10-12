import os
import shutil
from io import BytesIO
from typing import Any, Generator, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from fastapi_cloudauth.cognito import CognitoClaims  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api import settings
from api.core import notifications
from api.core.filesystem import (
    FileSystem,
    LocalFilesystem,
    S3Filesystem,
    get_user_filesystem,
)
from api.database import Base, get_db
from api.dependencies import (
    APIKeyDependency,
    current_user_dep,
    email_sender_dep,
    filesystem_dep,
    workerfacing_api_auth_dep,
)
from api.main import app
from api.models import Job
from tests.conftest import REGION_NAME, RDSTestingInstance, S3TestingBucket


@pytest.fixture(scope="session")
def username() -> str:
    return "test_user"


@pytest.fixture(scope="session")
def user_email() -> str:
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
    params=["local", pytest.param("aws", marks=pytest.mark.aws)],
)
def env(
    request: pytest.FixtureRequest,
    rds_testing_instance: RDSTestingInstance,
    s3_testing_bucket: S3TestingBucket,
) -> Generator[str, Any, None]:
    env = cast(str, request.param)
    if env == "aws":
        rds_testing_instance.create()
        s3_testing_bucket.create()
    yield env
    if env == "aws":
        rds_testing_instance.delete()
        s3_testing_bucket.delete()


@pytest.fixture
def db_session(
    env: str, rds_testing_instance: RDSTestingInstance
) -> Generator[Session, Any, None]:
    if env == "local":
        rel_test_db_path = "./test_app.db"
        shutil.rmtree(rel_test_db_path, ignore_errors=True)
        engine = create_engine(
            f"sqlite:///{rel_test_db_path}", connect_args={"check_same_thread": False}
        )
    elif env == "aws":
        engine = rds_testing_instance.engine
    else:
        raise NotImplementedError

    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session

    if env == "local":
        os.remove(rel_test_db_path)
    elif env == "aws":
        rds_testing_instance.cleanup()


@pytest.fixture
def base_filesystem(
    env: str,
    base_user_dir: str,
    monkeypatch_module: pytest.MonkeyPatch,
    s3_testing_bucket: S3TestingBucket,
) -> Generator[FileSystem, Any, None]:
    if env == "local":
        base_user_dir = f"./{base_user_dir}"

    monkeypatch_module.setattr(
        settings,
        "user_data_root_path",
        base_user_dir,
    )
    monkeypatch_module.setattr(
        settings,
        "s3_region",
        REGION_NAME,
    )
    monkeypatch_module.setattr(
        settings,
        "filesystem",
        "local" if env == "local" else "s3",
    )

    if env == "local":
        shutil.rmtree(base_user_dir, ignore_errors=True)
        yield LocalFilesystem(base_user_dir)
        shutil.rmtree(base_user_dir, ignore_errors=True)

    elif env == "aws":
        # Update settings to use the actual unique bucket name created by S3TestingBucket
        monkeypatch_module.setattr(
            settings,
            "s3_bucket",
            s3_testing_bucket.bucket_name,
        )
        yield S3Filesystem(
            base_user_dir, s3_testing_bucket.s3_client, s3_testing_bucket.bucket_name
        )
        s3_testing_bucket.cleanup()

    else:
        raise NotImplementedError


@pytest.fixture
def user_filesystem(base_filesystem: FileSystem, username: str) -> FileSystem:
    return get_user_filesystem(username)


@pytest.fixture(autouse=True)
def override_db_dep(
    db_session: Session, monkeypatch_module: pytest.MonkeyPatch
) -> None:
    monkeypatch_module.setitem(
        app.dependency_overrides,  # type: ignore
        get_db,
        lambda: db_session,
    )


@pytest.fixture(autouse=True)
def override_filesystem_dep(
    user_filesystem: FileSystem, monkeypatch_module: pytest.MonkeyPatch
) -> None:
    monkeypatch_module.setitem(
        app.dependency_overrides,  # type: ignore
        filesystem_dep,
        lambda: user_filesystem,
    )


@pytest.fixture(autouse=True, scope="session")
def override_auth(
    monkeypatch_module: pytest.MonkeyPatch, username: str, user_email: str
) -> None:
    monkeypatch_module.setitem(
        app.dependency_overrides,  # type: ignore
        current_user_dep,
        lambda: CognitoClaims(**{"cognito:username": username, "email": user_email}),
    )


@pytest.fixture(scope="session", autouse=True)
def override_internal_api_key_secret(
    monkeypatch_module: pytest.MonkeyPatch, internal_api_key_secret: str
) -> None:
    monkeypatch_module.setitem(
        app.dependency_overrides,  # type: ignore
        workerfacing_api_auth_dep,
        APIKeyDependency(internal_api_key_secret),
    )


@pytest.fixture(scope="session", autouse=True)
def override_email_sender(monkeypatch_module: pytest.MonkeyPatch) -> None:
    monkeypatch_module.setitem(
        app.dependency_overrides,  # type: ignore
        email_sender_dep,
        lambda: notifications.DummyEmailSender(),
    )


@pytest.fixture(scope="session", autouse=True)
def override_application_config(
    monkeypatch_module: pytest.MonkeyPatch, application: dict[str, str]
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
    monkeypatch_module.setattr(settings, "application_config", application_config)


@pytest.fixture
def require_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(app.dependency_overrides, current_user_dep)  # type: ignore


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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
    username: str,
    user_email: str,
    application: dict[str, str],
    job_attrs: dict[str, Any],
    db_session: Session,
) -> list[Job]:
    job1 = Job(
        id=42,
        user_id=username,
        user_email=user_email,
        job_name="job_test_1",
        environment="cloud",
        application=application,
        attributes=job_attrs,
        hardware={},
        paths_out={"output": "out", "log": "log", "artifact": "model"},
    )
    job2 = Job(
        id=50,
        user_id=username,
        user_email=user_email,
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
