import enum

from fastapi import APIRouter, Depends

from api.dependencies import GroupClaims, current_user_dep
from api.schemas.user import User
from api.settings import cognito_client_id, cognito_region, cognito_user_pool_id

router = APIRouter()


class AccessType(enum.Enum):
    COGNITO = "cognito"


@router.get(
    "/access_info",
    response_model=dict[AccessType, dict[str, str]],
    description="Get information about where API users should authenticate",
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
    description="Get information about the authenticated user",
)
def describe_current_user(
    current_user: GroupClaims = Depends(current_user_dep),
) -> dict[str, str | list[str] | None]:
    return {"email": current_user.email, "groups": current_user.cognito_groups}
