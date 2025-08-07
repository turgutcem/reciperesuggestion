from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5433/recipes_db"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    
    # Application
    APP_NAME: str = "Recipe Chat API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:8501", 
        "http://frontend:8501", 
        "http://localhost:3000"
    ]
    
    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Langfuse Configuration (Optional - disabled by default)
    # FIX: Use proper boolean parsing with field validator
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_ENVIRONMENT: str = "development"
    
    model_config = SettingsConfigDict(
        env_file="../.env",
        case_sensitive=True,
        extra="ignore",
        # Add this to properly parse booleans from env
        env_parse_none_str="none"
    )
    
    # Custom validator to handle string "true"/"false" from environment
    @classmethod
    def parse_env_vars(cls, values):
        """Parse environment variables with proper type conversion."""
        if 'LANGFUSE_ENABLED' in values:
            val = values['LANGFUSE_ENABLED']
            if isinstance(val, str):
                values['LANGFUSE_ENABLED'] = val.lower() in ('true', '1', 'yes', 'on')
        return values

settings = Settings()