"""Tests for Pydantic models."""
import pytest
from datetime import datetime
from shared.models import Paper, PaperAuthor, PaperCategory, ChatRequest, ChatResponse


def test_paper_model():
    """Test Paper model creation."""
    paper = Paper(
        arxiv_id="2401.12345",
        title="Test Paper",
        abstract="This is a test abstract",
        authors=[PaperAuthor(name="John Doe")],
        categories=PaperCategory(primary="cs.AI"),
        published=datetime.utcnow(),
        updated=datetime.utcnow(),
        pdf_url="https://arxiv.org/pdf/2401.12345.pdf",
        arxiv_url="https://arxiv.org/abs/2401.12345",
        primary_category="cs.AI"
    )
    
    assert paper.arxiv_id == "2401.12345"
    assert paper.title == "Test Paper"
    assert len(paper.authors) == 1


def test_chat_request_model():
    """Test ChatRequest model."""
    request = ChatRequest(
        paper_id="2401.12345",
        message="What is this paper about?"
    )
    
    assert request.paper_id == "2401.12345"
    assert request.message == "What is this paper about?"
    assert request.conversation_id is None


def test_chat_response_model():
    """Test ChatResponse model."""
    response = ChatResponse(
        message="This paper is about...",
        conversation_id="conv-123"
    )
    
    assert response.message is not None
    assert response.conversation_id == "conv-123"

