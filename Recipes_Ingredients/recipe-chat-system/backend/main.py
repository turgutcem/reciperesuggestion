# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from config import settings
from database import init_db, check_db_connection
from routers import auth_router, chat_router
from services import get_langfuse_service

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from Langfuse debug logs
logging.getLogger("langfuse").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Recipe Chat API...")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[1]}")  # Log without password
    logger.info(f"Ollama Base URL: {settings.OLLAMA_BASE_URL}")
    
    # Verify database connection
    try:
        init_db()
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
    
    # Test connections
    db_status = check_db_connection()
    logger.info(f"Database connection: {'✓' if db_status else '✗'}")
    
    # Test Ollama connection
    ollama_healthy = False
    try:
        import requests
        response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        ollama_healthy = response.status_code == 200
        logger.info(f"Ollama connection: {'✓' if ollama_healthy else '✗'}")
    except Exception as e:
        logger.warning(f"Ollama not available: {e}")
    
    # Initialize Langfuse (optional)
    if settings.LANGFUSE_ENABLED:
        try:
            langfuse = get_langfuse_service()
            if langfuse.enabled:
                logger.info("Langfuse observability: ✓")
            else:
                logger.info("Langfuse observability: ✗ (missing API keys)")
        except Exception as e:
            logger.info(f"Langfuse observability: ✗ ({e})")
    else:
        logger.info("Langfuse observability: disabled (enable with LANGFUSE_ENABLED=true)")
    
    # Initialize services (lazy loading - they'll load on first use)
    logger.info("Services initialized - ready to serve requests")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Recipe Chat API...")
    
    # Shutdown Langfuse if it was enabled
    try:
        langfuse = get_langfuse_service()
        if langfuse.enabled:
            langfuse.shutdown()
    except:
        pass  # Ignore errors during shutdown


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

# Include routers
app.include_router(auth_router)
app.include_router(chat_router)

# Root endpoint
@app.get("/")
async def root():
    langfuse_status = "disabled"
    if settings.LANGFUSE_ENABLED:
        try:
            langfuse = get_langfuse_service()
            langfuse_status = "enabled" if langfuse.enabled else "configured but no keys"
        except:
            langfuse_status = "error"
    
    return {
        "message": "Recipe Chat API",
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "auth": "/auth",
            "chat": "/chat",
            "health": "/health",
            "docs": "/docs"
        },
        "observability": {
            "langfuse": langfuse_status,
            "langfuse_ui": f"{settings.LANGFUSE_HOST}" if settings.LANGFUSE_ENABLED else None
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    # Check database
    db_healthy = check_db_connection()
    
    # Check Ollama
    ollama_healthy = False
    try:
        import requests
        response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        ollama_healthy = response.status_code == 200
    except:
        pass
    
    # Check Langfuse (optional)
    langfuse_status = "disabled"
    if settings.LANGFUSE_ENABLED:
        try:
            langfuse = get_langfuse_service()
            if langfuse.enabled:
                langfuse_status = "healthy" if langfuse.test_connection() else "unreachable"
            else:
                langfuse_status = "no_keys"
        except:
            langfuse_status = "error"
    
    # Check if embedding model can be loaded
    embedding_healthy = False
    try:
        from services import get_embedding_service
        service = get_embedding_service()
        embedding_healthy = service is not None
    except:
        pass
    
    # System is healthy if core services work (Langfuse is optional)
    all_healthy = db_healthy and ollama_healthy and embedding_healthy
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": {
            "api": "running",
            "database": "healthy" if db_healthy else "unhealthy",
            "ollama": "healthy" if ollama_healthy else "unhealthy",
            "embeddings": "healthy" if embedding_healthy else "unhealthy",
            "langfuse": langfuse_status  # Optional service
        }
    }


# Test endpoint for development
@app.post("/test/extract")
async def test_extraction(message: str):
    """Test endpoint to see extraction results."""
    if not settings.DEBUG:
        return {"error": "Only available in debug mode"}
    
    from services import get_llm_service, get_langfuse_service
    
    # Start a test trace if Langfuse is enabled
    langfuse = get_langfuse_service()
    trace = None
    if langfuse.enabled:
        trace = langfuse.start_trace(
            name="test_extraction",
            metadata={"test": True, "message": message[:100]}
        )
    
    llm = get_llm_service()
    
    query = llm.extract_recipe_query(message)
    tags = llm.extract_tags(message)
    
    # Update trace if it exists
    if trace:
        trace.update(
            output={
                "query": query.model_dump(),
                "tags": tags.model_dump()
            }
        )
        langfuse.flush()
    
    response = {
        "message": message,
        "extracted_query": query.model_dump(),
        "extracted_tags": tags.model_dump()
    }
    
    if trace:
        response["langfuse_trace_url"] = f"{settings.LANGFUSE_HOST}/trace/{trace.id}"
    
    return response