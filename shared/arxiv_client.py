"""arXiv API client wrapper."""
import httpx
import feedparser
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import time
import logging
from .config import settings
from .models import Paper, PaperAuthor, PaperCategory

logger = logging.getLogger(__name__)


class ArxivClient:
    """Client for interacting with arXiv API."""
    
    def __init__(self):
        """Initialize arXiv client."""
        self.base_url = settings.arxiv_api_base
        self.rate_limit_delay = settings.arxiv_rate_limit_delay
        self.last_request_time: Optional[float] = None
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def _parse_entry(self, entry: Dict[str, Any]) -> Paper:
        """Parse arXiv feed entry to Paper model."""
        # Extract arXiv ID from id field (format: http://arxiv.org/abs/2401.12345v1)
        arxiv_id = entry.id.split('/')[-1].split('v')[0]
        
        # Parse authors
        authors = []
        if 'authors' in entry:
            for author in entry.authors:
                authors.append(PaperAuthor(name=author.name))
        
        # Parse categories
        categories = entry.get('tags', [])
        primary_category = categories[0].term if categories else "unknown"
        secondary = [tag.term for tag in categories[1:]] if len(categories) > 1 else None
        
        # Parse dates
        published = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.utcnow()
        updated = datetime(*entry.updated_parsed[:6]) if hasattr(entry, 'updated_parsed') else published
        
        # Build URLs
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
        
        return Paper(
            arxiv_id=arxiv_id,
            title=entry.title,
            abstract=entry.summary,
            authors=authors,
            categories=PaperCategory(primary=primary_category, secondary=secondary),
            published=published,
            updated=updated,
            pdf_url=pdf_url,
            arxiv_url=arxiv_url,
            doi=entry.get('arxiv_doi'),
            journal_ref=entry.get('arxiv_journal_ref'),
            primary_category=primary_category,
            comment=entry.get('arxiv_comment')
        )
    
    async def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        author: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 20,
        start: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "descending"
    ) -> List[Paper]:
        """
        Search arXiv papers.
        
        Args:
            query: Search query string
            category: arXiv category (e.g., "cs.AI")
            author: Author name
            start_date: Start date for filtering
            end_date: End date for filtering
            max_results: Maximum number of results
            start: Starting index for pagination
            sort_by: Sort field (relevance, submittedDate, lastUpdatedDate)
            sort_order: Sort order (ascending, descending)
        
        Returns:
            List of Paper objects
        """
        self._rate_limit()
        
        # Build search query
        search_parts = []
        if query:
            search_parts.append(f"all:{query}")
        if category:
            search_parts.append(f"cat:{category}")
        if author:
            search_parts.append(f"au:{author}")
        if start_date:
            date_str = start_date.strftime("%Y%m%d")
            search_parts.append(f"submittedDate:[{date_str}000000 TO {date_str}235959]")
        if end_date:
            date_str = end_date.strftime("%Y%m%d")
            search_parts.append(f"submittedDate:[{date_str}000000 TO {date_str}235959]")
        
        # Build search query
        if search_parts:
            search_query = " AND ".join(search_parts)
        else:
            # For "all papers", use a date range query (last 30 days) as arXiv requires a query
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            search_query = f"submittedDate:[{start_str}000000 TO {end_str}235959]"
        
        # Build URL
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, 2000),  # arXiv limit
        }
        
        # Map sort_by to arXiv's expected values
        sort_mapping = {
            "relevance": "relevance",
            "submittedDate": "submittedDate", 
            "lastUpdatedDate": "lastUpdatedDate"
        }
        if sort_by in sort_mapping:
            params["sortBy"] = sort_mapping[sort_by]
            params["sortOrder"] = sort_order
        
        try:
            # Log the request for debugging
            logger.debug(f"arXiv API request: {self.base_url} with params: {params}")
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(self.base_url, params=params)
                
                # Log response status
                logger.debug(f"arXiv API response status: {response.status_code}")
                
                # Check for errors before parsing
                if response.status_code != 200:
                    error_text = response.text[:500]  # First 500 chars
                    logger.error(f"arXiv API error {response.status_code}: {error_text}")
                    raise Exception(f"arXiv API returned {response.status_code}: {error_text}")
                
                response.raise_for_status()
                response_text = response.text
            
            # Parse feed (feedparser is synchronous)
            feed = feedparser.parse(response_text)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")
            
            papers = []
            for entry in feed.entries:
                try:
                    paper = self._parse_entry(entry)
                    papers.append(paper)
                except Exception as e:
                    logger.error(f"Error parsing entry: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(papers)} papers from arXiv")
            return papers
        
        except Exception as e:
            logger.error(f"Error searching arXiv: {e}")
            raise
    
    async def get_by_id(self, arxiv_id: str) -> Optional[Paper]:
        """
        Get a specific paper by arXiv ID.
        
        Args:
            arxiv_id: arXiv ID (e.g., "2401.12345")
        
        Returns:
            Paper object or None if not found
        """
        self._rate_limit()
        
        params = {
            "id_list": arxiv_id,
            "max_results": 1
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                response_text = response.text
            
            feed = feedparser.parse(response_text)
            
            if not feed.entries:
                return None
            
            return self._parse_entry(feed.entries[0])
        
        except Exception as e:
            logger.error(f"Error fetching paper {arxiv_id}: {e}")
            return None
    
    async def get_recent(self, category: Optional[str] = None, max_results: int = 100) -> List[Paper]:
        """
        Get recent papers.
        
        Args:
            category: Optional category filter
            max_results: Maximum number of results
        
        Returns:
            List of recent Paper objects
        """
        # Get papers from last 7 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        return await self.search(
            category=category,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
            sort_by="submittedDate",
            sort_order="descending"
        )


# Global client instance
arxiv_client = ArxivClient()

