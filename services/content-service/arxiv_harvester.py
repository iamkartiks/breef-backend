"""arXiv OAI-PMH harvester for bulk metadata sync."""
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from supabase import Client

from shared.config import settings
from shared.database import db

logger = logging.getLogger(__name__)


class ArxivHarvester:
    """Harvester for arXiv metadata using OAI-PMH protocol."""
    
    def __init__(self):
        """Initialize harvester."""
        self.oai_base = settings.arxiv_oai_base
        self.rate_limit_delay = settings.arxiv_rate_limit_delay
    
    def _parse_record(self, record_element: ET.Element) -> Optional[dict]:
        """Parse OAI-PMH record to paper metadata."""
        try:
            metadata = record_element.find('.//{http://arxiv.org/OAI/arXivRaw/}arXivRaw')
            if metadata is None:
                return None
            
            # Extract arXiv ID
            arxiv_id_elem = metadata.find('.//{http://arxiv.org/OAI/arXivRaw/}id')
            if arxiv_id_elem is None:
                return None
            
            arxiv_id = arxiv_id_elem.text.split('v')[0] if arxiv_id_elem.text else None
            if not arxiv_id:
                return None
            
            # Extract title
            title_elem = metadata.find('.//{http://arxiv.org/OAI/arXivRaw/}title')
            title = title_elem.text if title_elem is not None else "Untitled"
            
            # Extract abstract
            abstract_elem = metadata.find('.//{http://arxiv.org/OAI/arXivRaw/}abstract')
            abstract = abstract_elem.text if abstract_elem is not None else ""
            
            # Extract authors
            authors = []
            for author_elem in metadata.findall('.//{http://arxiv.org/OAI/arXivRaw/}author'):
                name_elem = author_elem.find('.//{http://arxiv.org/OAI/arXivRaw/}keyname')
                forenames_elem = author_elem.find('.//{http://arxiv.org/OAI/arXivRaw/}forenames')
                name = ""
                if name_elem is not None and forenames_elem is not None:
                    name = f"{forenames_elem.text} {name_elem.text}"
                elif name_elem is not None:
                    name = name_elem.text
                
                if name:
                    authors.append({"name": name.strip(), "affiliation": None})
            
            # Extract categories
            categories = []
            for cat_elem in metadata.findall('.//{http://arxiv.org/OAI/arXivRaw/}categories/{http://arxiv.org/OAI/arXivRaw/}category'):
                if cat_elem.text:
                    categories.append(cat_elem.text)
            
            primary_category = categories[0] if categories else "unknown"
            secondary = categories[1:] if len(categories) > 1 else None
            
            # Extract dates
            created_elem = metadata.find('.//{http://arxiv.org/OAI/arXivRaw/}created')
            updated_elem = metadata.find('.//{http://arxiv.org/OAI/arXivRaw/}updated')
            
            published = datetime.utcnow()
            updated = datetime.utcnow()
            
            if created_elem is not None and created_elem.text:
                try:
                    published = datetime.strptime(created_elem.text, "%Y-%m-%d")
                except:
                    pass
            
            if updated_elem is not None and updated_elem.text:
                try:
                    updated = datetime.strptime(updated_elem.text, "%Y-%m-%d")
                except:
                    pass
            
            # Build URLs
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            return {
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "categories": {"primary": primary_category, "secondary": secondary},
                "published": published.isoformat(),
                "updated": updated.isoformat(),
                "pdf_url": pdf_url,
                "arxiv_url": arxiv_url,
                "primary_category": primary_category
            }
        except Exception as e:
            logger.error(f"Error parsing record: {e}")
            return None
    
    async def harvest_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        set_name: Optional[str] = None,
        db: Client = None
    ) -> int:
        """
        Harvest papers from a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            set_name: Optional set name (e.g., "cs" for computer science)
            db: Supabase client
        
        Returns:
            Number of papers harvested
        """
        if db is None:
            db = db.get_client()
        
        harvested = 0
        resumption_token = None
        
        while True:
            try:
                # Build OAI-PMH request
                params = {
                    "verb": "ListRecords",
                    "metadataPrefix": "arXivRaw",
                    "from": start_date.strftime("%Y-%m-%d"),
                    "until": end_date.strftime("%Y-%m-%d")
                }
                
                if set_name:
                    params["set"] = set_name
                
                if resumption_token:
                    params["resumptionToken"] = resumption_token
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(self.oai_base, params=params)
                    response.raise_for_status()
                    response_text = response.text
                
                # Parse XML
                root = ET.fromstring(response_text)
                
                # Extract namespace
                ns = {'oai': 'http://www.openarchives.org/OAI/2.0/'}
                
                # Process records
                records = root.findall('.//oai:record', ns)
                papers_to_insert = []
                
                for record in records:
                    paper_data = self._parse_record(record)
                    if paper_data:
                        papers_to_insert.append(paper_data)
                
                # Batch insert to database
                if papers_to_insert:
                    try:
                        db.table("papers").upsert(papers_to_insert, on_conflict="arxiv_id").execute()
                        harvested += len(papers_to_insert)
                        logger.info(f"Harvested {len(papers_to_insert)} papers (total: {harvested})")
                    except Exception as e:
                        logger.error(f"Error inserting papers: {e}")
                
                # Check for resumption token
                resumption_token_elem = root.find('.//oai:resumptionToken', ns)
                if resumption_token_elem is not None and resumption_token_elem.text:
                    resumption_token = resumption_token_elem.text
                else:
                    break
                
                # Rate limiting
                import asyncio
                await asyncio.sleep(self.rate_limit_delay)
            
            except Exception as e:
                logger.error(f"Error during harvest: {e}")
                break
        
        return harvested
    
    async def sync_recent(self, days: int = 1, db: Client = None) -> int:
        """
        Sync recent papers (last N days).
        
        Args:
            days: Number of days to look back
            db: Supabase client
        
        Returns:
            Number of papers synced
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"Syncing papers from {start_date.date()} to {end_date.date()}")
        return await self.harvest_date_range(start_date, end_date, db=db)


# Global harvester instance
harvester = ArxivHarvester()

