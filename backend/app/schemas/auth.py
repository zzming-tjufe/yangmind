from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=64)
    invite_code: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    # 支持邮箱、昵称，或管理员别名 admin
    email: str = Field(min_length=1, max_length=254)
    password: str


class UserOut(BaseModel):
    id: int
    public_id: str
    email: EmailStr
    nickname: str
    role: str
    status: str
    is_debug: bool = False
    is_sudo: bool = False

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
