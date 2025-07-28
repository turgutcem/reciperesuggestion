from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "recipes_db"
    db_user: str = "postgres"
    db_password: str = "turgutcem"
    
    # Ollama Configuration  
    ollama_host: str = "localhost"
    ollama_port: int = 11434
    
    # App Configuration
    secret_key: str = "change-this-secret-key-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # Model Configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    llama_model: str = "llama3.2:3b"
    
    class Config:
        # Look for .env file in project root (parent directory)
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        print(env_file)
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def ollama_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"

settings = Settings()