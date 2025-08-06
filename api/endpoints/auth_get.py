import enum

from fastapi import APIRouter, Depends, status

from api.dependencies import GroupClaims, current_user_dep
from api.schemas.user import User
from api.schemas.common import ErrorResponse
from api.settings import cognito_client_id, cognito_region, cognito_user_pool_id

router = APIRouter()


class AccessType(enum.Enum):
    COGNITO = "cognito"


@router.get(
    "/access_info",
    response_model=dict[AccessType, dict[str, str]],
    status_code=status.HTTP_200_OK,
    description="Get information about where API users should authenticate",
    responses={
        200: {"description": "Successfully retrieved access information", "model": dict[AccessType, dict[str, str]]}
    }
)
def get_access_info() -> dict[AccessType, dict[str, str]]:
    return {
        AccessType.COGNITO: {
            "user_pool_id": cognito_user_pool_id,
            "client_id": cognito_client_id,
            "region": cognito_region,
        },
    }


@router.get(
    "/user",
    response_model=User,
    status_code=status.HTTP_200_OK,
    description="Get information about the currently authenticated user",
    responses={
        200: {"description": "Successfully retrieved user information", "model": User},
        401: {"description": "Authentication required", "model": ErrorResponse}
    }
)
def describe_current_user(
    current_user: GroupClaims = Depends(current_user_dep),
) -> dict[str, str | list[str] | None]:
    return {"email": current_user.email, "groups": current_user.cognito_groups}
