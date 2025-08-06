from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging

from config import settings

logger = logging.getLogger(__name__)

# Create engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    # Connection pool settings
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.DEBUG,  # Log SQL in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI
def get_db() -> Session:
    """
    Get database session.
    Use as FastAPI dependency:
    
    @app.get("/")
    def read_root(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Direct connection for recipe queries (from notebook)
def get_recipe_connection():
    """
    Get raw psycopg2 connection for recipe queries.
    Used for compatibility with notebook code.
    """
    import psycopg2
    
    # Parse connection string
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "")
    
    # Extract components
    auth, host_db = db_url.split("@")
    user, password = auth.split(":")
    host_port, db_name = host_db.split("/")
    
    if ":" in host_port:
        host, port = host_port.split(":")
    else:
        host = host_port
        port = "5432"
    
    conn = psycopg2.connect(
        dbname=db_name,
        user=user,
        password=password,
        host=host,
        port=port,
        options='-c client_encoding=utf8'
    )
    conn.set_client_encoding('UTF8')
    return conn

def init_db():
    """
    Verify database tables exist.
    Tables are created by SQL scripts, not by SQLAlchemy.
    """
    try:
        # Just verify connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection verified")
        
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def check_db_connection():
    """Check if database is accessible."""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False