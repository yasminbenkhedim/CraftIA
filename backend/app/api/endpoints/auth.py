import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.services.credits import add_one_month
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

logger = logging.getLogger("uvicorn")

router = APIRouter()


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = "User"


class UserLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{req.email}' already exists."
        )

    # plan / credits_remaining / credits_total come from the model defaults (free plan,
    # full allowance). Only the period end has to be computed, so a new account starts a
    # real month here rather than waiting for its first read to backfill it.
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        credits_reset_at=add_one_month(datetime.utcnow()),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(
        f"Registered {user.email} on plan '{user.plan}' with "
        f"{user.credits_remaining}/{user.credits_total} credits, period ends "
        f"{user.credits_reset_at.isoformat()}Z"
    )

    token = create_access_token({"sub": user.id, "email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email
    }


@router.post("/login", response_model=TokenResponse)
def login_user(req: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    token = create_access_token({"sub": user.id, "email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        # Plan only. The balance lives at GET /api/me/credits, which the shell polls on
        # its own schedule -- duplicating it here would give the UI two copies that drift
        # apart the moment a render finishes.
        "plan": current_user.plan,
    }
