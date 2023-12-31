import boto3
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_cloudauth.cognito import CognitoClaims

from api.core.filesystem import get_user_filesystem
from api.dependencies import current_user_dep
from api.schemas.user import User, UserGroups
from api.settings import cognito_user_pool_id

router = APIRouter()


@router.get("/user", response_model=User)
def describe_current_user(current_user: CognitoClaims = Depends(current_user_dep)):
    return {"email": current_user.email, "groups": current_user.cognito_groups}


@router.post("/user", status_code=status.HTTP_201_CREATED, response_model=User)
def register_user(
    user: OAuth2PasswordRequestForm = Depends(), groups: list[UserGroups] | None = None
):
    client = boto3.client("cognito-idp")

    try:
        # Perform the signup using the email and password
        response = client.admin_create_user(
            UserPoolId=cognito_user_pool_id,
            Username=user.username,
            TemporaryPassword=user.password,
            MessageAction="SUPPRESS",
        )
        if not groups:
            groups = [UserGroups.users]
        for group in groups:
            client.admin_add_user_to_group(
                Username=user.username,
                GroupName=group.value,
                UserPoolId=cognito_user_pool_id,
            )

        # Reset password to change state
        client.admin_set_user_password(
            UserPoolId=cognito_user_pool_id,
            Username=user.username,
            Password=user.password,
            Permanent=True,
        )
        filesystem = get_user_filesystem(response["User"]["Username"])
        filesystem.init()
    except client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "UsernameExistsException":
            raise HTTPException(status_code=409, detail="User already exists")
        elif e.response["Error"]["Code"] == "InvalidPasswordException":
            raise HTTPException(
                status_code=400, detail="Password does not meet requirements"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Boto3 error: {e.response['Error']['Code']}. {e.response['Error']['Message']}",
            )

    return {"email": user.username, "groups": groups}
