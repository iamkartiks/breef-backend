"""Content Service - arXiv integration and paper management."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client
from typing import Optional, List
from datetime import datetime
from pydantic import HttpUrl
import sys
from pathlib import Path
import importlib.util

from shared.database import get_db
from shared.arxiv_client import arxiv_client
from shared.models import Paper, PaperListItem, PaperSearchParams, ErrorResponse

# Import get_current_user from user-service (handles hyphenated directory name)
def load_get_current_user():
    """Load get_current_user function from user-service."""
    backend_dir = Path(__file__).parent.parent.parent
    user_service_path = backend_dir / "services" / "user-service" / "main.py"
    
    spec = importlib.util.spec_from_file_location("user_service_main", user_service_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load user-service from {user_service_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_current_user

get_current_user = load_get_current_user()

router = APIRouter()


@router.get("", response_model=List[PaperListItem])
async def list_papers(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="arXiv category"),
    author: Optional[str] = Query(None, description="Author name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("relevance", description="Sort field"),
    sort_order: str = Query("descending", description="Sort order"),
    db: Client = Depends(get_db)
):
    """List/search papers with pagination."""
    try:
        # Calculate start index
        start = (page - 1) * page_size
        
        # Search arXiv
        papers = await arxiv_client.search(
            query=query,
            category=category,
            author=author,
            max_results=page_size,
            start=start,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Convert to list items
        list_items = []
        for paper in papers:
            list_items.append(PaperListItem(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                authors=[a.name for a in paper.authors],
                abstract=paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract,
                published=paper.published,
                primary_category=paper.primary_category,
                pdf_url=paper.pdf_url
            ))
        
        return list_items
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching papers: {str(e)}"
        )


@router.get("/{arxiv_id}")
async def get_paper(
    arxiv_id: str,
    db: Client = Depends(get_db)
):
    """Get paper details by arXiv ID."""
    try:
        # First check cache/database
        response = db.table("papers").select("*").eq("arxiv_id", arxiv_id).execute()
        
        if response.data:
            # Return from cache
            paper_data = response.data[0]
            # Parse datetime strings if they're stored as strings
            if 'published' in paper_data and isinstance(paper_data['published'], str):
                try:
                    paper_data['published'] = datetime.fromisoformat(paper_data['published'].replace('Z', '+00:00'))
                except:
                    pass
            if 'updated' in paper_data and isinstance(paper_data['updated'], str):
                try:
                    paper_data['updated'] = datetime.fromisoformat(paper_data['updated'].replace('Z', '+00:00'))
                except:
                    pass
            # HttpUrl fields should already be strings from database, Pydantic will validate them
            # Database uses 'arxiv_id', but Paper model expects it via alias 'id' or direct 'arxiv_id'
            # Since populate_by_name=True, we can use either
            paper = Paper(**paper_data)
            # Get vote counts for this paper
            votes_response = db.table("paper_votes").select("vote_type").eq("paper_id", arxiv_id).execute()
            upvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "upvote")
            downvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "downvote")
            
            # Return serialized with by_alias=True for API response (uses 'id' instead of 'arxiv_id')
            paper_dict = paper.model_dump(by_alias=True, mode='json')
            paper_dict['upvotes'] = upvotes
            paper_dict['downvotes'] = downvotes
            paper_dict['user_vote'] = None  # Will be set if user is authenticated
            return paper_dict
        else:
            # Fetch from arXiv
            paper = await arxiv_client.get_by_id(arxiv_id)
            
            if not paper:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Paper {arxiv_id} not found"
                )
            
            # Cache in database - convert datetime and HttpUrl to strings
            # Use by_alias=False to get 'arxiv_id' instead of 'id' for database column name
            # Exclude vote fields (upvotes, downvotes, user_vote) as they're not stored in papers table
            paper_dict = paper.model_dump(by_alias=False, mode='json', exclude={'upvotes', 'downvotes', 'user_vote'})
            # mode='json' converts datetime and HttpUrl to strings automatically
            db.table("papers").upsert(paper_dict, on_conflict="arxiv_id").execute()
        
        # Get vote counts for this paper
        votes_response = db.table("paper_votes").select("vote_type").eq("paper_id", arxiv_id).execute()
        upvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "upvote")
        downvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "downvote")
        
        # Add vote counts to paper data
        paper_dict = paper.model_dump(by_alias=True, mode='json')
        paper_dict['upvotes'] = upvotes
        paper_dict['downvotes'] = downvotes
        paper_dict['user_vote'] = None  # Will be set if user is authenticated
        
        return paper_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching paper: {str(e)}"
        )


@router.get("/trending", response_model=List[PaperListItem])
async def get_trending_papers(
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(20, ge=1, le=100, description="Number of papers"),
    db: Client = Depends(get_db)
):
    """Get trending papers (recent papers with most views)."""
    try:
        # Get recent papers from last 7 days
        papers = await arxiv_client.get_recent(category=category, max_results=limit)
        
        # Convert to list items with vote counts
        list_items = []
        for paper in papers:
            # Get vote counts for this paper
            votes_response = db.table("paper_votes").select("vote_type").eq("paper_id", paper.arxiv_id).execute()
            upvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "upvote")
            downvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "downvote")
            
            list_items.append(PaperListItem(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                authors=[a.name for a in paper.authors],
                abstract=paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract,
                published=paper.published,
                primary_category=paper.primary_category,
                pdf_url=paper.pdf_url,
                upvotes=upvotes,
                downvotes=downvotes,
                user_vote=None  # Will be set if user is authenticated
            ))
        
        return list_items
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching trending papers: {str(e)}"
        )


@router.post("/{arxiv_id}/vote")
async def vote_paper(
    arxiv_id: str,
    vote_type: str = Query(..., pattern="^(upvote|downvote)$"),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Vote on a paper (upvote or downvote)."""
    try:
        user_id = current_user["id"]
        
        # Check if user already voted
        existing_vote = db.table("paper_votes").select("*").eq("paper_id", arxiv_id).eq("user_id", user_id).execute()
        
        if existing_vote.data:
            # Update existing vote
            if existing_vote.data[0]["vote_type"] == vote_type:
                # Same vote - remove it (toggle off)
                db.table("paper_votes").delete().eq("paper_id", arxiv_id).eq("user_id", user_id).execute()
                return {"message": "Vote removed", "vote_type": None}
            else:
                # Different vote - update it
                db.table("paper_votes").update({"vote_type": vote_type}).eq("paper_id", arxiv_id).eq("user_id", user_id).execute()
                return {"message": "Vote updated", "vote_type": vote_type}
        else:
            # Create new vote
            db.table("paper_votes").insert({
                "user_id": user_id,
                "paper_id": arxiv_id,
                "vote_type": vote_type
            }).execute()
            return {"message": "Vote recorded", "vote_type": vote_type}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error voting on paper: {str(e)}"
        )


@router.get("/{arxiv_id}/votes")
async def get_paper_votes(
    arxiv_id: str,
    db: Client = Depends(get_db)
):
    """Get vote counts for a paper."""
    try:
        votes_response = db.table("paper_votes").select("vote_type").eq("paper_id", arxiv_id).execute()
        upvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "upvote")
        downvotes = sum(1 for v in votes_response.data if v.get("vote_type") == "downvote")
        
        return {
            "paper_id": arxiv_id,
            "upvotes": upvotes,
            "downvotes": downvotes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching votes: {str(e)}"
        )

