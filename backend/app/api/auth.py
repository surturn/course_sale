import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User
from app.security import COOKIE_NAME, create_access_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def normalise_phone(value: str) -> str:
    """Accept 07XXXXXXXX / 01XXXXXXXX / +2547... / 2547...; return Daraja's 2547XXXXXXXX form."""
    digits = re.sub(r"[\s+-]", "", value)
    if re.fullmatch(r"0[17]\d{8}", digits):
        digits = "254" + digits[1:]
    if not re.fullmatch(r"254[17]\d{8}", digits):
        raise ValueError("Enter a Safaricom number like 0712345678")
    return digits


class RegisterIn(BaseModel):
    email: EmailStr
    phone: str
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    _phone = field_validator("phone")(normalise_phone)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    phone: str
    full_name: str
    is_admin: bool

    model_config = {"from_attributes": True}


@router.post("/register", status_code=201, response_model=UserOut)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    taken = await db.scalar(select(User).where(or_(User.email == email, User.phone == body.phone)))
    if taken:
        raise HTTPException(409, "An account with that email or phone already exists")
    user = User(email=email, phone=body.phone, full_name=body.full_name, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    return user


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "Wrong email or password")
    response.set_cookie(
        COOKIE_NAME, create_access_token(user.id),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True, secure=settings.COOKIE_SECURE, samesite="strict", path="/",
    )
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user
