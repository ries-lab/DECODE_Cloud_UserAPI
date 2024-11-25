import typing

import requests
from fastapi import Depends, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi_cloudauth.cognito import CognitoClaims, CognitoCurrentUser
from pydantic import Field

from api import settings
from api.core import notifications
from api.core.filesystem import get_user_filesystem
from api.schemas.job import QueueJob


class GroupClaims(CognitoClaims):
    """CognitoClaims with added groups claim."""

    cognito_groups: list[str] | None = Field(alias="cognito:groups")


class UserGroupCognitoCurrentUser(CognitoCurrentUser):
    """
    Check membership in the 'users' group and add group membership information.
    """

    user_info = GroupClaims

    async def call(self, http_auth):
        user_info = await super().call(http_auth)
        if "users" not in (getattr(user_info, "cognito_groups") or []):
            raise HTTPException(
                status_code=403, detail="Not a member of the 'users' group"
            )
        return user_info


current_user_dep = UserGroupCognitoCurrentUser(
    region=settings.cognito_region,
    userPoolId=settings.cognito_user_pool_id,
    client_id=settings.cognito_client_id,
)


async def current_user_global_dep(
    request: Request, current_user: CognitoClaims = Depends(current_user_dep)
):
    """Check authentication and add user information."""
    request.state.current_user = current_user
    return current_user


async def filesystem_dep(current_user: CognitoClaims = Depends(current_user_dep)):
    """Get the user's filesystem."""
    return get_user_filesystem(current_user.username)


class APIKeyDependency:
    def __init__(self, key: str):
        """Check API-internal key."""
        self.key = key

    def __call__(self, x_api_key: typing.Optional[str] = Header(...)):
        if x_api_key != self.key:
            raise HTTPException(status_code=401, detail="unauthorized")
        return x_api_key


workerfacing_api_auth_dep = APIKeyDependency(settings.internal_api_key_secret)


async def email_sender_dep():
    """Get the email sender."""
    service = settings.email_sender_service
    match service:
        case None:
            return notifications.DummyEmailSender()
        case "mailjet":
            return notifications.MailjetEmailSender(
                api_key=settings.email_sender_api_key,
                secret_key=settings.email_sender_secret_key,
                sender_address=settings.email_sender_address,
            )
        case _:
            raise ValueError(
                f"Unknown email sender service {service}. Only mailjet is supported."
            )


async def enqueueing_function_dep() -> callable:
    def enqueue(queue_item: QueueJob) -> None:
        resp = requests.post(
            url=f"{settings.workerfacing_api_url}/_jobs",
            json=jsonable_encoder(queue_item),
            headers={"x-api-key": settings.internal_api_key_secret},
        )
        if not str(resp.status_code).startswith("2"):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Error while enqueueing job {queue_item.job.job_id}. Traceback: \n{resp.text}.",
            )

    return enqueue
