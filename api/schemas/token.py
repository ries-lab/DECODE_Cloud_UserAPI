from pydantic import BaseModel


class TokenResponse(BaseModel):
    id_token: str
    expires_in: int

    class Config:
        schema_extra = {
            "example": {
                "id_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 3600
            }
        }
