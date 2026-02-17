"""Pydantic models for API requests and responses."""
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


# User Models
class UserProfile(BaseModel):
    """User profile model."""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserProfileUpdate(BaseModel):
    """User profile update request."""
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


# Paper Models
class PaperAuthor(BaseModel):
    """Paper author model."""
    name: str
    affiliation: Optional[str] = None


class PaperCategory(BaseModel):
    """Paper category model."""
    primary: str
    secondary: Optional[List[str]] = None


class Paper(BaseModel):
    """Paper model."""
    arxiv_id: str = Field(..., alias="id")
    title: str
    abstract: str
    authors: List[PaperAuthor]
    categories: PaperCategory
    published: datetime
    updated: datetime
    pdf_url: HttpUrl
    arxiv_url: HttpUrl
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    primary_category: str
    comment: Optional[str] = None
    upvotes: int = 0  # Computed field, not stored in DB - excluded when saving
    downvotes: int = 0  # Computed field, not stored in DB - excluded when saving
    user_vote: Optional[str] = None  # Computed field, not stored in DB - excluded when saving
    
    model_config = ConfigDict(
        populate_by_name=True,
        # Pydantic v2 handles datetime and HttpUrl serialization automatically
        # HttpUrl is serialized as string in JSON mode
        json_schema_extra={
            "example": {
                "id": "2301.00001",
                "title": "Example Paper",
                "abstract": "This is an example abstract",
                "authors": [{"name": "John Doe"}],
                "categories": {"primary": "cs.AI"},
                "published": "2023-01-01T00:00:00",
                "updated": "2023-01-01T00:00:00",
                "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
                "arxiv_url": "https://arxiv.org/abs/2301.00001",
                "primary_category": "cs.AI"
            }
        }
    )


class PaperListItem(BaseModel):
    """Simplified paper model for listing."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published: datetime
    primary_category: str
    pdf_url: HttpUrl
    upvotes: int = 0
    downvotes: int = 0
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaperSearchParams(BaseModel):
    """Paper search parameters."""
    query: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="relevance", pattern="^(relevance|submittedDate|lastUpdatedDate)$")
    sort_order: str = Field(default="descending", pattern="^(ascending|descending)$")


# AI Chat Models
class ChatMessage(BaseModel):
    """Chat message model."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatRequest(BaseModel):
    """AI chat request."""
    paper_id: str
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """AI chat response."""
    message: str
    conversation_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Conversation(BaseModel):
    """Conversation model."""
    id: str
    user_id: str
    paper_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# User Paper Interaction Models
class UserPaperInteraction(BaseModel):
    """User interaction with a paper."""
    user_id: str
    paper_id: str
    bookmarked: bool = False
    read_at: Optional[datetime] = None
    last_viewed: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class BookmarkRequest(BaseModel):
    """Bookmark request."""
    paper_id: str
    bookmarked: bool


# Subscription Models
class SubscriptionType(str, Enum):
    """Subscription type enum."""
    AUTHOR = "author"
    CATEGORY = "category"
    KEYWORD = "keyword"


class Subscription(BaseModel):
    """Subscription model."""
    id: str
    user_id: str
    type: SubscriptionType
    target: str  # author name, category, or keyword
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SubscriptionRequest(BaseModel):
    """Subscription request."""
    type: SubscriptionType
    target: str


# Error Models
class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

