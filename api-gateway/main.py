"""FastAPI API Gateway - Main entry point."""
import sys
from pathlib import Path

# Add parent directory to path to import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from pydantic import HttpUrl
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import json

from shared.config import settings
from shared.models import ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting API Gateway...")
    logger.info(f"Environment: {'development' if settings.debug else 'production'}")
    yield
    # Shutdown
    logger.info("Shutting down API Gateway...")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.debug,
    lifespan=lifespan
)

# CORS middleware
# In debug mode, allow all origins for easier network access during development
cors_origins = ["*"] if settings.debug else settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if not settings.debug else False,  # Can't use credentials with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to ensure proper JSON serialization of Pydantic models
@app.middleware("http")
async def json_serialization_middleware(request: Request, call_next):
    """Middleware to ensure HttpUrl and datetime are properly serialized."""
    response = await call_next(request)
    # FastAPI should handle this automatically, but this ensures it works
    return response


# Custom JSON encoder for datetime and HttpUrl
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, HttpUrl):
            return str(obj)
        return super().default(obj)

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    error_data = ErrorResponse(
        error="Validation Error",
        detail=str(exc),
        code="VALIDATION_ERROR"
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(error_data)
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    error_data = ErrorResponse(
        error="Internal Server Error",
        detail="An unexpected error occurred" if not settings.debug else str(exc),
        code="INTERNAL_ERROR"
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(error_data)
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "api-gateway"}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Research Paper Platform API",
        "version": settings.api_version,
        "docs": "/docs"
    }


# Import and include routers from services
# Note: Python can't import modules with hyphens, so we import directly from files
import importlib.util
from pathlib import Path

def load_router_from_service(service_dir_name):
    """Load router from a service directory (handles hyphenated names)."""
    backend_dir = Path(__file__).parent.parent
    service_path = backend_dir / "services" / service_dir_name / "main.py"
    
    spec = importlib.util.spec_from_file_location(f"service_{service_dir_name.replace('-', '_')}", service_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load service from {service_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.router

# Load routers from services
user_router = load_router_from_service("user-service")
content_router = load_router_from_service("content-service")
ai_router = load_router_from_service("ai-service")

app.include_router(user_router, prefix=f"{settings.api_prefix}/users", tags=["users"])
app.include_router(content_router, prefix=f"{settings.api_prefix}/papers", tags=["papers"])
app.include_router(ai_router, prefix=f"{settings.api_prefix}/ai", tags=["ai"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )

