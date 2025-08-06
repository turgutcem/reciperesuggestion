# backend/routers/auth.py
"""
Authentication router for user management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from database import get_db
from schemas import UserCreate, UserLogin, User
from utils.auth import create_user, authenticate_user, get_user_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Simple session storage (in production use Redis or JWT)
# This is just for MVP
user_sessions = {}
session_counter = 1000


@router.post("/register", response_model=User)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        user = create_user(db, user_data)
        logger.info(f"New user registered: {user.email}")
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login")
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login and create session."""
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create simple session
    global session_counter
    session_token = f"session_{session_counter}"
    session_counter += 1
    user_sessions[session_token] = user.id
    
    logger.info(f"User logged in: {user.email}")
    
    return {
        "access_token": session_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }


@router.get("/me", response_model=User)
async def get_current_user_info(
    user_id: int = Depends(lambda: 1),  # TODO: Implement proper auth dependency
    db: Session = Depends(get_db)
):
    """Get current user information."""
    # For MVP, we'll use a hardcoded user_id
    # In production, extract from token
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.post("/logout")
async def logout(session_token: str):
    """Logout and invalidate session."""
    if session_token in user_sessions:
        del user_sessions[session_token]
        return {"message": "Logged out successfully"}
    return {"message": "Session not found"}


# Helper function to get current user from session
def get_current_user(authorization: str = None) -> int:
    """Extract user ID from session token."""
    if not authorization:
        # For MVP/testing, return test user ID
        return 1
    
    # Extract token from "Bearer <token>"
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        if token in user_sessions:
            return user_sessions[token]
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session"
    )