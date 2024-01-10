import boto3
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from api.core.aws import calculate_secret_hash
from api.schemas.token import TokenResponse
from api.settings import cognito_client_id, cognito_secret

router = APIRouter()


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
