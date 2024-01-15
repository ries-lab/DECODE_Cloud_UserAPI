import enum
from fastapi import APIRouter, Depends
from fastapi_cloudauth.cognito import CognitoClaims

from api.dependencies import current_user_dep
from api.schemas.user import User
from api.settings import cognito_user_pool_id, cognito_region, cognito_client_id

router = APIRouter()


class AccessType(enum.Enum):
    COGNITO = "cognito"


@router.get("/access_info", response_model=dict[AccessType, dict])
def get_access_info():
    return {
        AccessType.COGNITO: {
            "user_pool_id": cognito_user_pool_id,
            "client_id": cognito_client_id,
            "region": cognito_region,
        },
    }


@router.get("/user", response_model=User)
def describe_current_user(current_user: CognitoClaims = Depends(current_user_dep)):
    return {"email": current_user.email, "groups": current_user.cognito_groups}
