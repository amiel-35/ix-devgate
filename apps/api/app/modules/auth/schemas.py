from pydantic import BaseModel, EmailStr


class LoginStartRequest(BaseModel):
    email: EmailStr


class LoginStartResponse(BaseModel):
    ok: bool
    method: str  # magic_link | otp


class LoginVerifyRequest(BaseModel):
    token: str


class LoginVerifyResponse(BaseModel):
    ok: bool
    session_created: bool
    redirect_to: str
