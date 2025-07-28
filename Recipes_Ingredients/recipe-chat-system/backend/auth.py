from sqlalchemy.orm import Session
from database import User
import bcrypt
from fastapi import HTTPException, Depends, Request
from database import get_db
import uuid

# Simple in-memory session store
active_sessions = {}

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(db: Session, email: str, password: str):
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
    active_sessions[session_id] = {"user_id": str(user.id), "email": user.email}
    
    return user

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    
    # Create session
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {"user_id": str(user.id), "email": user.email}
    
    return user

def get_current_user(request: Request):
    # Simple session check (in production, we'll use proper session management)
    session_id = request.headers.get("X-Session-ID")
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return active_sessions[session_id]