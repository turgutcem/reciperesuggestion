# backend/routers/auth.py
"""
Authentication router for user management with proper session handling.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

from database import get_db
from schemas import UserCreate, UserLogin, User
from utils.auth import create_user, authenticate_user, get_user_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class SessionManager:
    """Thread-safe session management."""
    
    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self.session_ttl = timedelta(hours=24)
    
    def create_session(self, user_id: int) -> str:
        """Create a new session token."""
        # Generate secure random token
        token = f"session_{secrets.token_urlsafe(32)}"
        
        # Store session info
        self.sessions[token] = {
            'user_id': user_id,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + self.session_ttl,
            'last_activity': datetime.now()
        }
        
        # Clean up expired sessions
        self._cleanup_expired()
        
        logger.info(f"Created session for user {user_id}")
        return token
    
    def get_user_id(self, token: str) -> Optional[int]:
        """Get user ID from token."""
        if not token:
            return None
            
        session = self.sessions.get(token)
        if not session:
            return None
            
        # Check expiration
        if datetime.now() > session['expires_at']:
            del self.sessions[token]
            return None
        
        # Update last activity
        session['last_activity'] = datetime.now()
        return session['user_id']
    
    def destroy_session(self, token: str) -> bool:
        """Destroy a session."""
        if token in self.sessions:
            user_id = self.sessions[token]['user_id']
            del self.sessions[token]
            logger.info(f"Destroyed session for user {user_id}")
            return True
        return False
    
    def _cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.now()
        expired = [
            token for token, session in self.sessions.items()
            if now > session['expires_at']
        ]
        for token in expired:
            del self.sessions[token]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global session manager instance
session_manager = SessionManager()


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
        logger.warning(f"Failed login attempt for: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create session
    session_token = session_manager.create_session(user.id)
    
    logger.info(f"User logged in: {user.email}")
    
    return {
        "access_token": session_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        },
        "expires_in": 86400  # 24 hours in seconds
    }


@router.get("/me", response_model=User)
async def get_current_user_info(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Get current user information."""
    user_id = get_current_user(authorization)
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.post("/logout")
async def logout(authorization: str = Header(None)):
    """Logout and invalidate session."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session to logout"
        )
    
    # Extract token
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    
    # Destroy session
    if session_manager.destroy_session(token):
        return {"message": "Logged out successfully"}
    
    return {"message": "Session not found or already expired"}


@router.get("/verify")
async def verify_token(authorization: str = Header(None)):
    """Verify if token is valid."""
    try:
        user_id = get_current_user(authorization)
        return {"valid": True, "user_id": user_id}
    except HTTPException:
        return {"valid": False}


# Helper function to get current user from session
def get_current_user(authorization: str = None) -> int:
    """
    Extract user ID from session token.
    FIXED: No longer defaults to user_id=1
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>" format
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    
    # Get user ID from session
    user_id = session_manager.get_user_id(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_id


# Export for use in other routers
__all__ = ['router', 'get_current_user', 'session_manager']