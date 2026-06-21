import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from itsdangerous import Signer, BadSignature
import models
from database import get_db

# Crypt context for hashing passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Secret key for cookie signing
SECRET_KEY = os.getenv("SECRET_KEY", "calvary_gospel_prayer_fellowship_secret_key_123456")
signer = Signer(SECRET_KEY)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def create_session_token(user_id: int, role: str) -> str:
    """Creates a signed session token containing user_id and role."""
    data = f"{user_id}:{role}:{int(datetime.utcnow().timestamp())}"
    return signer.sign(data.encode('utf-8')).decode('utf-8')

def verify_session_token(token: str) -> Optional[dict]:
    """Verifies and decodes a session token. Returns dict with user_id and role if valid."""
    try:
        unsigned_bytes = signer.unsign(token.encode('utf-8'))
        data_str = unsigned_bytes.decode('utf-8')
        parts = data_str.split(":")
        if len(parts) != 3:
            return None
        user_id, role, timestamp_str = parts
        # Session valid for 7 days
        timestamp = int(timestamp_str)
        if datetime.utcnow().timestamp() - timestamp > 7 * 86400:
            return None
        return {
            "user_id": int(user_id),
            "role": role
        }
    except (BadSignature, ValueError, Exception):
        return None

# Dependency to check login status, returns None if not logged in
def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    token = request.cookies.get("session_token")
    if not token:
        return None
    session_data = verify_session_token(token)
    if not session_data:
        return None
    
    user = db.query(models.User).filter(models.User.id == session_data["user_id"]).first()
    return user

# Dependency to force authenticated user, redirects to login if not
def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = get_current_user_optional(request, db)
    if not user:
        # Redirect to login page
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user

# Dependency to force admin, redirects to admin login if not admin
def get_current_admin(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = get_current_user_optional(request, db)
    if not user or user.role != "admin":
        # Redirect to admin login page
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"}
        )
    return user
