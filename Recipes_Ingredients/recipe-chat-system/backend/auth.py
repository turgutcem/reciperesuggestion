import bcrypt
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from models import User
from schemas import UserCreate, UserLogin
from config import settings

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def create_user(db: Session, user_create: UserCreate) -> User:
    """Create a new user."""
    # Check if user exists
    existing = db.query(User).filter(User.email == user_create.email).first()
    if existing:
        raise ValueError("User with this email already exists")
    
    # Create new user
    db_user = User(
        email=user_create.email,
        password_hash=get_password_hash(user_create.password),
        name=user_create.name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()

# Simple session management (for now, just return user_id)
# In production, you'd want proper JWT tokens
def create_session(user: User) -> dict:
    """Create a simple session response."""
    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "message": "Login successful"
    }