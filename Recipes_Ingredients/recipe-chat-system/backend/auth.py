from sqlalchemy.orm import Session
from database import User, get_db
import bcrypt
from fastapi import HTTPException, Depends, Request
import uuid
from typing import Dict, Optional

# Simple in-memory session store for development
# In production, use Redis or database sessions
active_sessions: Dict[str, Dict[str, str]] = {}

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(db: Session, email: str, password: str) -> User:
    """Create a new user."""
    # Check if user exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_pw = hash_password(password)
    user = User(email=email, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create session
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "user_id": str(user.id), 
        "email": user.email,
        "session_id": session_id
    }
    
    return user

def authenticate_user(db: Session, email: str, password: str) -> Optional[Dict[str, str]]:
    """Authenticate user and return session info."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    
    # Create session
    session_id = str(uuid.uuid4())
    session_info = {
        "user_id": str(user.id), 
        "email": user.email,
        "session_id": session_id
    }
    active_sessions[session_id] = session_info
    
    return session_info

def get_current_user(request: Request) -> Dict[str, str]:
    """Get current user from session."""
    # Simple session check (in production, use proper session management)
    session_id = request.headers.get("X-Session-ID")
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return active_sessions[session_id]