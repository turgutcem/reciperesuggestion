from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from config import settings
from database import init_db, check_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Recipe Chat API...")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[1]}")  # Log without password
    logger.info(f"Ollama Base URL: {settings.OLLAMA_BASE_URL}")
    
    # Verify database connection (tables created by SQL scripts)
    try:
        init_db()
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
    
    # Test connections
    db_status = check_db_connection()
    logger.info(f"Database connection: {'✓' if db_status else '✗'}")
    
    # TODO: Test Ollama connection
    # TODO: Load embedding model
    
    yield
    
    # Shutdown
    logger.info("Shutting down Recipe Chat API...")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Recipe Chat API",
        "version": settings.APP_VERSION,
        "status": "running"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    # Check database
    db_healthy = check_db_connection()
    
    # TODO: Check Ollama
    ollama_healthy = False
    try:
        import requests
        response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        ollama_healthy = response.status_code == 200
    except:
        pass
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "services": {
            "api": "running",
            "database": "healthy" if db_healthy else "unhealthy",
            "ollama": "healthy" if ollama_healthy else "unhealthy",
            "embeddings": "pending"
        }
    }

# API routes will be added here
# TODO: Include auth router
# TODO: Include conversations router
# TODO: Include chat router