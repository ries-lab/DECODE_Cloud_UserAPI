import boto3
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from api.core.aws import calculate_secret_hash
from api.core.filesystem import get_user_filesystem
from api.schemas.token import TokenResponse
from api.schemas.user import User, UserGroups
from api.settings import cognito_client_id, cognito_secret, cognito_user_pool_id

router = APIRouter()


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


@router.post(
    "/token", status_code=status.HTTP_201_CREATED, response_model=TokenResponse
)
async def get_token(login: OAuth2PasswordRequestForm = Depends()):
    client = boto3.client("cognito-idp")
    try:
        # Perform the login using the email and password
        auth_params = {"USERNAME": login.username, "PASSWORD": login.password}
        if cognito_secret:
            auth_params["SECRET_HASH"] = calculate_secret_hash(
                login.username, cognito_client_id, cognito_secret
            )
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
            ClientId=cognito_client_id,
        )
        # Get the ID token from the response
        id_token = response["AuthenticationResult"]["IdToken"]
        expires_in = response["AuthenticationResult"]["ExpiresIn"]
        return {"id_token": id_token, "expires_in": expires_in}
    except client.exceptions.NotAuthorizedException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    except client.exceptions.UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.text
        )


@router.post("/login", status_code=status.HTTP_201_CREATED)
async def get_login(user: OAuth2PasswordRequestForm = Depends()):
    client = boto3.client("cognito-idp")
    try:
        # Perform the login using the email and password
        auth_params = {"USERNAME": user.username, "PASSWORD": user.password}
        if cognito_secret:
            auth_params["SECRET_HASH"] = calculate_secret_hash(
                user.username, cognito_client_id, cognito_secret
            )
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
            ClientId=cognito_client_id,
        )
        # Get the ID token from the response
        token = response["AuthenticationResult"]["IdToken"]
        content = {"message": "You've successfully logged in. Welcome back!"}
        response = JSONResponse(content=content)
        response.set_cookie(
            "Authorization",
            value=f"Bearer {token}",
            httponly=True,
            max_age=1800,
            expires=1800,
            samesite="none",
            secure=True,
        )
        return response
    except client.exceptions.NotAuthorizedException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    except client.exceptions.UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.text
        )
