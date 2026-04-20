from typing import Literal

from pydantic import BaseModel, EmailStr


class LoginStartRequest(BaseModel):
    email: EmailStr
    method: Literal["magic_link", "otp"] = "magic_link"


class LoginStartResponse(BaseModel):
    ok: bool
    method: str


class LoginVerifyRequest(BaseModel):
    token: str


class LoginVerifyResponse(BaseModel):
    ok: bool
    session_created: bool
    redirect_to: str
