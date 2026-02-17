"""Database connection and helper functions."""
from supabase import create_client, Client
from typing import Optional
from .config import settings
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database client wrapper."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.client: Optional[Client] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client."""
        try:
            self.client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    def get_client(self) -> Client:
        """Get Supabase client."""
        if self.client is None:
            self._initialize_client()
        return self.client
    
    def get_service_client(self) -> Client:
        """Get Supabase client with service role key (for admin operations)."""
        if not settings.supabase_service_key:
            raise ValueError("Service key not configured")
        return create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )


# Global database instance
db = Database()


def get_db() -> Client:
    """Get database client (dependency injection)."""
    return db.get_client()

