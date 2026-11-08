"""Registration, sign-in and token checks (FR-1, FR-2)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ADMINS, settings
from .db import get_db
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    if len(pw.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        # bcrypt rejects passwords beyond 72 UTF-8 bytes and malformed hashes.
        # A failed sign-in must stay a normal authentication error.
        return False


def make_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.token_hours)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in")
    try:
        user_id = int(jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError, OverflowError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    if not 0 < user_id <= 2**63 - 1:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session, please sign in again")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return user


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter your name")
        return value

    @field_validator("password")
    @classmethod
    def bcrypt_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    token: str
    name: str
    role: str = "player"


def current_player(user: User = Depends(current_user)) -> User:
    """Analysis, training and coaching are player features; administrators manage the app instead.
    Role rules are listed in README.md (Roles); the front end mirrors them in js/api.js."""
    if user.role != "player":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This is a player feature. Administrator accounts manage the app; sign in with a player account to analyse and train.")
    return user


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access needed")
    return user


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password),
                role="admin" if email in ADMINS else "player")
    db.add(user)
    db.commit()
    return TokenOut(token=make_token(user.id), name=user.name, role=user.role)


def authenticate(body: LoginIn, db: Session) -> User:
    """Check credentials and configured roles before a client-specific token is issued."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    if user.email in ADMINS and user.role != "admin":  # promote accounts added to ADMIN_EMAILS later
        user.role = "admin"
        db.commit()
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = authenticate(body, db)
    return TokenOut(token=make_token(user.id), name=user.name, role=user.role)


@router.post("/player/login", response_model=TokenOut)
def player_login(body: LoginIn, db: Session = Depends(get_db)):
    """The mobile app accepts players only; admin accounts use the website."""
    user = authenticate(body, db)
    if user.role != "player":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This app is for players. Please use the admin website.")
    return TokenOut(token=make_token(user.id), name=user.name, role=user.role)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
