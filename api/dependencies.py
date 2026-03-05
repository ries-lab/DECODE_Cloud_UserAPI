from typing import Any, Callable, Generator

import boto3
import requests
from botocore.config import Config
from botocore.utils import fix_s3_host
from fastapi import Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi_cloudauth.cognito import CognitoClaims  # type: ignore
from sqlalchemy.orm import Session, sessionmaker

from api import settings
from api.core import notifications
from api.core.auth import APIKeyDependency, UserGroupCognitoCurrentUser
from api.core.database import Database, SqliteDatabase
from api.core.filesystem import FileSystem, user_filesystem_getter
from api.schemas.job import QueueJob

# S3 client setup
s3_client = None
if settings.s3_bucket:
    s3_client = boto3.client(
        "s3",
        region_name=settings.s3_region,
        endpoint_url=f"https://s3.{settings.s3_region}.amazonaws.com",
        config=Config(signature_version="v4", s3={"addressing_style": "path"}),
    )
    # this and config=... required to avoid DNS problems with new buckets
    s3_client.meta.events.unregister("before-sign.s3", fix_s3_host)


# Database
if settings.database_url.startswith("sqlite"):
    db: Database = SqliteDatabase(
        db_url=settings.database_url,
        s3_client=s3_client,
        s3_bucket=settings.s3_bucket,
    )
else:
    db = Database(db_url=settings.database_url)


async def db_dep() -> Database:
    return db


def session_dep(db_dep: Database = Depends(db_dep)) -> Generator[Session, Any, None]:
    """Get database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_dep.engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# User authentication
current_user_dep = UserGroupCognitoCurrentUser(
    region=settings.cognito_region,
    userPoolId=settings.cognito_user_pool_id,
    client_id=settings.cognito_client_id,
)


async def current_user_global_dep(
    request: Request, current_user: CognitoClaims = Depends(current_user_dep)
) -> CognitoClaims:
    """Check authentication and add user information."""
    request.state.current_user = current_user
    return current_user


# Filesystem
async def filesystem_getter_dep() -> Callable[[str], FileSystem]:
    """Get the user's filesystem getter."""
    return user_filesystem_getter(
        user_data_root_path=settings.user_data_root_path,
        filesystem=settings.filesystem,
        s3_client=s3_client,
        s3_bucket=settings.s3_bucket,
    )


async def user_filesystem_dep(
    filesystem_getter: Callable[[str], FileSystem] = Depends(filesystem_getter_dep),
    current_user: CognitoClaims = Depends(current_user_dep),
) -> FileSystem:
    """Get the user's filesystem."""
    return filesystem_getter(current_user.username)


# App-internal authentication (i.e. user-facing API <-> worker-facing API)
workerfacing_api_auth_dep = APIKeyDependency(settings.internal_api_key_secret)


# Notifications
async def email_sender_dep() -> notifications.EmailSender:
    """Get the email sender."""
    service = settings.email_sender_service
    match service:
        case None:
            return notifications.DummyEmailSender()
        case "mailjet":
            if (
                settings.email_sender_api_key is None
                or settings.email_sender_secret_key is None
                or settings.email_sender_address is None
            ):
                raise ValueError(
                    "Email sender service is set to mailjet, but the required configuration is missing."
                )
            return notifications.MailjetEmailSender(
                api_key=settings.email_sender_api_key,
                secret_key=settings.email_sender_secret_key,
                sender_address=settings.email_sender_address,
            )
        case _:
            raise ValueError(
                f"Unknown email sender service {service}. Only mailjet is supported."
            )


# Job enqueueing to worker-facing API
async def enqueueing_function_dep() -> Callable[[QueueJob], None]:
    def enqueue(queue_item: QueueJob) -> None:
        resp = requests.post(
            url=f"{settings.workerfacing_api_url}/_jobs",
            json=jsonable_encoder(queue_item),
            headers={"x-api-key": settings.internal_api_key_secret},
        )
        if not str(resp.status_code).startswith("2"):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Error while enqueueing job {queue_item.job.meta.job_id}. Traceback: \n{resp.text}.",
            )

    return enqueue
