"""Cron job for daily arXiv metadata sync."""
import asyncio
import logging
from datetime import datetime
from shared.database import db
from .arxiv_harvester import harvester

logger = logging.getLogger(__name__)


async def daily_sync():
    """Run daily sync job."""
    logger.info(f"Starting daily arXiv sync at {datetime.utcnow()}")
    
    try:
        # Sync papers from last 24 hours
        count = await harvester.sync_recent(days=1, db=db.get_client())
        logger.info(f"Daily sync completed. Harvested {count} papers.")
    except Exception as e:
        logger.error(f"Error during daily sync: {e}")


if __name__ == "__main__":
    # Run sync
    asyncio.run(daily_sync())

