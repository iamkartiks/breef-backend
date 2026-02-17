"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    api_title: str = "Research Paper Platform API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api"
    debug: bool = False
    
    # Supabase Configuration
    supabase_url: str
    supabase_key: str
    supabase_service_key: Optional[str] = None
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_enabled: bool = True
    
    # arXiv Configuration
    arxiv_api_base: str = "https://export.arxiv.org/api/query"
    arxiv_oai_base: str = "https://export.arxiv.org/oai2"
    arxiv_rate_limit_delay: float = 3.0  # seconds between requests
    
    # AI Service Configuration
    openai_api_key: Optional[str] = None
    grok_api_key: Optional[str] = None
    ai_provider: str = "openai"  # "openai" or "grok"
    ai_model: str = "gpt-4-turbo-preview"
    ai_rate_limit_per_user: int = 50  # requests per hour
    
    # CORS Configuration
    # For development, allow all origins. For production, specify exact origins.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app"
    ]
    # Allow all origins in debug mode for easier network access during development
    cors_allow_all: bool = False
    
    # Security
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

