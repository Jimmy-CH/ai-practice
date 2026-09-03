from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    email: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    username_or_phone: str
    password: str


class SMSLoginRequest(BaseModel):
    phone: str
    code: str


class SMSSendRequest(BaseModel):
    phone: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
