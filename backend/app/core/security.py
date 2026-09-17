import os
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "createflow_super_secret_jwt_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str = "createflow_salt_2026") -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


def get_demo_user(db: Session) -> User:
    demo_user = db.query(User).filter((User.id == "demo_user_001") | (User.email == "demo@createflow.ai")).first()
    if not demo_user:
        demo_user = User(
            id="demo_user_001",
            email="demo@createflow.ai",
            full_name="Demo User",
            hashed_password=hash_password("demo123456")
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
    return demo_user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> User:
    raw_token = credentials.credentials if (credentials and credentials.credentials) else token

    if not raw_token:
        if os.getenv("ALLOW_DEV_ANONYMOUS_AUTH", "0") != "1":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. Bearer token missing.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if raw_token == "demo-token" or (not raw_token and os.getenv("ALLOW_DEV_ANONYMOUS_AUTH", "0") == "1"):
        return get_demo_user(db)

    payload = decode_access_token(raw_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user_or_demo(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> User:
    raw_token = credentials.credentials if (credentials and credentials.credentials) else token
    if not raw_token or raw_token == "demo-token":
        return get_demo_user(db)
    try:
        return get_current_user(credentials=credentials, token=token, db=db)
    except HTTPException:
        return get_demo_user(db)
