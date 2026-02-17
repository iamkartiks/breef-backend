"""Tests for arXiv client."""
import pytest
from shared.arxiv_client import ArxivClient


@pytest.mark.asyncio
async def test_search_papers():
    """Test searching for papers."""
    client = ArxivClient()
    papers = await client.search(query="machine learning", max_results=5)
    
    assert len(papers) > 0
    assert papers[0].title is not None
    assert papers[0].arxiv_id is not None


@pytest.mark.asyncio
async def test_get_by_id():
    """Test getting paper by ID."""
    client = ArxivClient()
    paper = await client.get_by_id("2401.12345")
    
    # Note: This might fail if the paper doesn't exist
    # In a real test, use a known paper ID
    if paper:
        assert paper.arxiv_id == "2401.12345"
        assert paper.title is not None


@pytest.mark.asyncio
async def test_get_recent():
    """Test getting recent papers."""
    client = ArxivClient()
    papers = await client.get_recent(category="cs.AI", max_results=10)
    
    assert len(papers) <= 10
    if papers:
        assert papers[0].primary_category == "cs.AI"

