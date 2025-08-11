# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5433/recipes_db"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    
    # Application
    APP_NAME: str = "Recipe Chat API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Security and Session
    SESSION_SECRET: str = "your-secret-key-change-this-in-production"
    SESSION_TTL_HOURS: int = 24
    ALGORITHM: str = "HS256"
    
    # CORS - Updated for production with static IP
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """Get allowed origins, including static IP if set."""
        origins = [
            "http://localhost:8501",
            "http://frontend:8501",
            "http://localhost:3000",
            "http://localhost:8001"
        ]
        
        # Add static IP origins if configured
        external_ip = os.getenv("EXTERNAL_IP", "")
        if external_ip:
            origins.extend([
                f"http://{external_ip}:8501",
                f"http://{external_ip}:8001", 
                f"http://{external_ip}:3000"
            ])
        
        return origins
    
    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Langfuse Configuration (Properly configured for production)
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_ENVIRONMENT: str = "development"
    LANGFUSE_NEXTAUTH_URL: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file="../.env",
        case_sensitive=True,
        extra="ignore"
    )
    
    def __init__(self, **data):
        """Custom initialization to handle environment variables."""
        super().__init__(**data)
        
        # Parse LANGFUSE_ENABLED as boolean
        langfuse_enabled_str = os.getenv("LANGFUSE_ENABLED", "false").lower()
        self.LANGFUSE_ENABLED = langfuse_enabled_str in ("true", "1", "yes", "on")
        
        # Set Langfuse keys from environment if available
        if os.getenv("LANGFUSE_PUBLIC_KEY"):
            self.LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
        if os.getenv("LANGFUSE_SECRET_KEY"):
            self.LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
        
        # Set Langfuse environment
        if os.getenv("LANGFUSE_ENVIRONMENT"):
            self.LANGFUSE_ENVIRONMENT = os.getenv("LANGFUSE_ENVIRONMENT")
        
        # Set debug mode from environment
        debug_str = os.getenv("DEBUG", "false").lower()
        self.DEBUG = debug_str in ("true", "1", "yes", "on")
        
        # Set log level
        if os.getenv("LOG_LEVEL"):
            self.LOG_LEVEL = os.getenv("LOG_LEVEL")
        
        # Update Langfuse host for Docker networking
        if os.getenv("LANGFUSE_HOST"):
            self.LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")
        elif os.getenv("EXTERNAL_IP"):
            # Use external IP if configured
            self.LANGFUSE_HOST = f"http://{os.getenv('EXTERNAL_IP')}:3000"
        
        # Set NextAuth URL for Langfuse
        if os.getenv("LANGFUSE_NEXTAUTH_URL"):
            self.LANGFUSE_NEXTAUTH_URL = os.getenv("LANGFUSE_NEXTAUTH_URL")
        elif os.getenv("EXTERNAL_IP"):
            self.LANGFUSE_NEXTAUTH_URL = f"http://{os.getenv('EXTERNAL_IP')}:3000"

# Create singleton instance
settings = Settings()

# Log configuration on startup (without sensitive data)
import logging
logger = logging.getLogger(__name__)

def log_config():
    """Log non-sensitive configuration for debugging."""
    logger.info(f"App: {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")
    logger.info(f"Langfuse Enabled: {settings.LANGFUSE_ENABLED}")
    if settings.LANGFUSE_ENABLED:
        logger.info(f"Langfuse Environment: {settings.LANGFUSE_ENVIRONMENT}")
        logger.info(f"Langfuse Host: {settings.LANGFUSE_HOST}")
        has_keys = bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)
        logger.info(f"Langfuse Keys Configured: {has_keys}")
    logger.info(f"CORS Origins: {settings.ALLOWED_ORIGINS}")