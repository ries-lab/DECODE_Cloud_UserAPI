import typing
from fastapi import Request, Depends, Header, HTTPException
from fastapi_cloudauth.cognito import CognitoCurrentUser, CognitoClaims
from pydantic import Field

from api.core.filesystem import get_user_filesystem
from api.settings import cognito_client_id, cognito_region, cognito_user_pool_id
from api.settings import internal_api_key_secret


class GroupClaims(CognitoClaims):
    cognito_groups: list[str] | None = Field(alias="cognito:groups")


class UserGroupCognitoCurrentUser(CognitoCurrentUser):
    user_info = GroupClaims

    async def call(self, http_auth):
        user_info = await super().call(http_auth)
        if "users" not in (getattr(user_info, "cognito_groups") or []):
            raise HTTPException(
                status_code=403, detail="Not a member of the 'users' group"
            )
        return user_info


current_user_dep = UserGroupCognitoCurrentUser(
    region=cognito_region, userPoolId=cognito_user_pool_id, client_id=cognito_client_id
)


async def current_user_global_dep(
    request: Request, current_user: CognitoClaims = Depends(current_user_dep)
):
    request.state.current_user = current_user
    return current_user


async def filesystem_dep(current_user: CognitoClaims = Depends(current_user_dep)):
    return get_user_filesystem(current_user.username)


class APIKeyDependency:
    def __init__(self, key: str):
        self.key = key

    def __call__(self, x_api_key: typing.Optional[str] = Header(...)):
        if x_api_key != self.key:
            raise HTTPException(status_code=401, detail="unauthorized")
        return x_api_key


workerfacing_api_auth_dep = APIKeyDependency(internal_api_key_secret)
