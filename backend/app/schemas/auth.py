from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # Client-side minLength is trivially bypassed by calling the API directly
    # — this is the enforcement that actually matters. max_length guards
    # against a huge payload being fed to bcrypt (it also just silently
    # ignores anything past 72 bytes, so there's no point accepting more).
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
