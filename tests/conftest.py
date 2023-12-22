import os
import pytest
import shutil
import dotenv
from unittest.mock import Mock

from api.core import notifications

# At import the database is directly created, so need to set this first
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
rel_test_db_path = "./test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{rel_test_db_path}"

from io import BytesIO

import api.database
from api import settings
from api.core.filesystem import get_user_filesystem
from api.main import app
from api.models import Job
from api.dependencies import (
    current_user_dep,
    CognitoClaims,
    filesystem_dep,
    APIKeyDependency,
    workerfacing_api_auth_dep,
    email_sender_dep,
)


data_file1_name = "data/test/data_file1.txt"
data_file1_contents = "data file1 contents"
data_file2_name = "data/test/data_file2.txt"
data_file2_contents = "data file2 contents"

config_file1_name = "config/test/config_file1.txt"
config_file1_contents = "config file1 contents"
config_file2_name = "config/test/config_file2.txt"
config_file2_contents = "config file2 contents"

test_username = "test_user"
test_user_email = "test@example.com"

internal_api_key_secret = "test_internal_api_key"

example_app = {"application": "app", "version": "latest", "entrypoint": "test"}
example_attrs = {
    "files_down": {"data_ids": ["test"], "config_id": "test", "artifact_ids": []},
    "env_vars": {},
}


@pytest.fixture(autouse=True, scope="module")
def handle_test_database():
    api.database.Base.metadata.create_all(bind=api.database.engine)
    yield api.database.SessionLocal()
    try:
        os.remove(rel_test_db_path)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="module")
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture(
    scope="module",
    params=["local", "aws_mock", pytest.param("aws", marks=pytest.mark.aws)],
)
def env(request):
    return request.param


@pytest.fixture(scope="module")
def base_filesystem(env, monkeypatch_module):
    bucket_name = "decode-cloud-tests-bucket"
    region_name = "eu-central-1"
    base_user_dir = "test_user_dir"
    if env == "local":
        base_user_dir = f"./{base_user_dir}"

    monkeypatch_module.setattr(
        settings,
        "user_data_root_path",
        base_user_dir,
    )
    monkeypatch_module.setattr(
        settings,
        "s3_bucket",
        bucket_name,
    )
    monkeypatch_module.setattr(
        settings,
        "filesystem",
        "local" if env == "local" else "s3",
    )

    if env == "local":
        from api.core.filesystem import LocalFilesystem

        yield LocalFilesystem(base_user_dir)
        try:
            shutil.rmtree(base_user_dir)
        except FileNotFoundError:
            pass

    elif env == "aws_mock":
        from moto import mock_s3

        with mock_s3():
            from api.core.filesystem import S3Filesystem
            import boto3

            s3_client = boto3.client("s3", region_name=region_name)
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region_name},
            )
            yield S3Filesystem(base_user_dir, s3_client, bucket_name)

    elif env == "aws":
        from api.core.filesystem import S3Filesystem
        import boto3

        s3_client = boto3.client("s3", region_name=region_name)
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region_name},
        )
        yield S3Filesystem(base_user_dir, s3_client, bucket_name)
        s3 = boto3.resource("s3")
        s3_bucket = s3.Bucket(bucket_name)
        bucket_versioning = s3.BucketVersioning(bucket_name)
        if bucket_versioning.status == "Enabled":
            s3_bucket.object_versions.delete()
        else:
            s3_bucket.objects.all().delete()
        s3_bucket.delete()

    else:
        raise NotImplementedError


@pytest.fixture(scope="module")
def user_filesystem(base_filesystem):
    filesystem = get_user_filesystem(test_username)
    yield filesystem


@pytest.fixture(scope="module", autouse=True)
def override_filesystem_dep(user_filesystem, monkeypatch_module):
    monkeypatch_module.setitem(
        app.dependency_overrides, filesystem_dep, lambda: user_filesystem
    )


@pytest.fixture(autouse=True, scope="module")
def override_auth(monkeypatch_module):
    monkeypatch_module.setitem(
        app.dependency_overrides,
        current_user_dep,
        lambda: CognitoClaims(
            **{"cognito:username": test_username, "email": test_user_email}
        ),
    )


@pytest.fixture(scope="module", autouse=True)
def override_internal_api_key_secret(monkeypatch_module):
    monkeypatch_module.setitem(
        app.dependency_overrides,
        workerfacing_api_auth_dep,
        APIKeyDependency(internal_api_key_secret),
    )
    return internal_api_key_secret


@pytest.fixture(scope="module", autouse=True)
def override_email_sender(monkeypatch_module):
    monkeypatch_module.setitem(
        app.dependency_overrides,
        email_sender_dep,
        lambda: notifications.DummyEmailSender(),
    )


@pytest.fixture(scope="module", autouse=True)
def override_application_config(monkeypatch_module):
    application_config = Mock()
    application_config.config = {
        example_app["application"]: {
            example_app["version"]: {
                example_app["entrypoint"]: {
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
def require_auth(monkeypatch):
    monkeypatch.delitem(app.dependency_overrides, current_user_dep)


@pytest.fixture
def data_files(user_filesystem):
    user_filesystem.create_file(
        data_file1_name, BytesIO(bytes(data_file1_contents, "utf-8"))
    )
    user_filesystem.create_file(
        data_file2_name, BytesIO(bytes(data_file2_contents, "utf-8"))
    )
    yield
    user_filesystem.delete(data_file1_name)
    user_filesystem.delete(data_file2_name)


@pytest.fixture
def config_files(user_filesystem):
    user_filesystem.create_file(
        config_file1_name, BytesIO(bytes(config_file1_contents, "utf-8"))
    )
    user_filesystem.create_file(
        config_file2_name, BytesIO(bytes(config_file2_contents, "utf-8"))
    )
    yield
    user_filesystem.delete(config_file1_name)
    user_filesystem.delete(config_file2_name)


@pytest.fixture
def data_file1(user_filesystem):
    user_filesystem.create_file(
        data_file1_name, BytesIO(bytes(data_file1_contents, "utf-8"))
    )
    yield
    user_filesystem.delete(data_file1_name)


@pytest.fixture
def cleanup_files(user_filesystem):
    to_cleanup = []
    yield to_cleanup
    for file in to_cleanup:
        user_filesystem.delete(file)


@pytest.fixture
def jobs(data_files, config_files):
    job1 = Job(
        id=42,
        user_id=test_username,
        user_email=test_user_email,
        job_name="job_test_1",
        environment="cloud",
        application=example_app,
        attributes=example_attrs,
        hardware={},
    )
    job2 = Job(
        id=50,
        user_id=test_username,
        user_email=test_user_email,
        job_name="job_test_2",
        environment=None,
        application=example_app,
        attributes=example_attrs,
        hardware={},
    )
    database = api.database.SessionLocal()
    jobs = [job1, job2]
    [database.add(job) for job in jobs]
    database.commit()
    yield jobs
    [database.delete(job) for job in jobs]
    database.commit()


@pytest.fixture
def foreign_job(data_files, config_files):
    job = Job(
        id=999,
        user_id="foreign_user",
        job_name="job_test_3",
        environment=None,
        application=example_app,
        attributes=example_attrs,
        hardware={},
    )
    database = api.database.SessionLocal()
    database.add(job)
    database.commit()
    yield job
    database.delete(job)
    database.commit()
