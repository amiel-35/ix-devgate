from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints


class LoginStartRequest(BaseModel):
    email: EmailStr
    method: Literal["magic_link", "otp"] = "magic_link"


class LoginStartResponse(BaseModel):
    ok: bool
    method: str


class LoginVerifyRequest(BaseModel):
    token: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class LoginVerifyResponse(BaseModel):
    ok: bool
    session_created: bool
    redirect_to: str
