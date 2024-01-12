import enum
from fastapi import APIRouter
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
