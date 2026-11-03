import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import LedgerState, Order, OrderPaid, User
from app.security import (
    COOKIE_NAME, check_throttle, current_user, hash_password, record_failure, start_session, verify_password,
)

LOGIN_LIMIT, LOGIN_WINDOW = 10, 15 * 60  # failed attempts per email
SIGNUP_LIMIT, SIGNUP_WINDOW = 20, 60 * 60  # per IP; generous because campus Wi-Fi shares IPs

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
    is_guest: bool = False

    model_config = {"from_attributes": True}


@router.post("/register", status_code=201, response_model=UserOut)
async def register(body: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip_key = f"signup:{request.client.host if request.client else 'unknown'}"
    check_throttle(ip_key, SIGNUP_LIMIT, SIGNUP_WINDOW)
    record_failure(ip_key)  # every signup counts towards the per-IP cap
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
    key = f"login:{body.email.lower()}"
    check_throttle(key, LOGIN_LIMIT, LOGIN_WINDOW)
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(user.password_hash, body.password):
        record_failure(key)
        raise HTTPException(401, "Wrong email or password")
    start_session(response, user.id)
    return user


class PasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@router.post("/set-password", response_model=UserOut)
async def set_password(body: PasswordIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """A guest turns their checkout account into a normal one. Only guests: changing a real password needs the old one."""
    if not user.is_guest:
        raise HTTPException(400, "This account already has a password")
    user.password_hash, user.is_guest = hash_password(body.password), False
    await db.commit()
    return user


class ClaimIn(BaseModel):
    email: EmailStr
    mpesa_receipt: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)


@router.post("/claim", response_model=UserOut)
async def claim_guest_account(body: ClaimIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """A guest whose session ended gets back in by proving payment: the email they used plus the M-Pesa
    confirmation code from their SMS for one of their orders. Sets a password and logs them in."""
    email = body.email.lower()
    keys = [f"claim:{email}", f"claim-ip:{request.client.host if request.client else 'unknown'}"]
    check_throttle(keys[0], 5, 15 * 60)
    check_throttle(keys[1], 30, 15 * 60)
    user = await db.scalar(select(User).where(User.email == email, User.is_guest, User.is_active))
    paid = user and await db.scalar(
        select(OrderPaid.id).join(Order, Order.id == OrderPaid.order_id).where(
            Order.user_id == user.id, OrderPaid.state == LedgerState.confirmed,
            OrderPaid.mpesa_receipt == body.mpesa_receipt.strip().upper()).limit(1))
    if not paid:
        for k in keys:
            record_failure(k)
        raise HTTPException(400, "Those details don't match a guest purchase. Check the email and the M-Pesa code.")
    user.password_hash, user.is_guest = hash_password(body.password), False
    await db.commit()
    start_session(response, user.id)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user
