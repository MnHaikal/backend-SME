from pydantic import BaseModel, EmailStr, ConfigDict, Field, AliasChoices, field_validator
from typing import Optional
import re
from fastapi import HTTPException

class UserRegisterSchema(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    otp_code: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # Minimal 8 karakter
        if len(v) < 8:
            raise HTTPException(status_code=400, detail="Password terlalu lemah: minimal 8 karakter.")
        # Minimal 1 huruf besar
        if not re.search(r"[A-Z]", v):
            raise HTTPException(status_code=400, detail="Password terlalu lemah: harus mengandung minimal 1 huruf besar.")
        # Minimal 1 huruf kecil
        if not re.search(r"[a-z]", v):
            raise HTTPException(status_code=400, detail="Password terlalu lemah: harus mengandung minimal 1 huruf kecil.")
        # Minimal 1 angka
        if not re.search(r"\d", v):
            raise HTTPException(status_code=400, detail="Password terlalu lemah: harus mengandung minimal 1 angka.")
        # Minimal 1 karakter spesial/simbol
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]/\\~`]", v):
            raise HTTPException(status_code=400, detail="Password terlalu lemah: harus mengandung minimal 1 karakter spesial/simbol.")
        return v

class UserLogin(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr
    password: str

class OTPRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr
    otp_code: str

class GoogleLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr
    id_token: Optional[str] = None

class UserUpdateSchema(BaseModel):
    name: str

class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr
    otp_code: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    email: str
    old_password: str
    new_password: str
