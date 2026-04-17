import json
import logging
from app.scraper import scrape_calendar, events_to_documents
from app.embedder import upsert_documents

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def lambda_handler(event, context):
    """
    Triggered by EventBridge once per day.
    Scrapes Rialto calendar → generates embeddings → upserts into ChromaDB on EFS.
    """
    logger.info("Scraper Lambda triggered.")

    try:
        events = scrape_calendar()
        if not events:
            logger.warning("No events scraped — site may be down or structure changed.")
            return {"statusCode": 200, "body": json.dumps({"scraped": 0})}

        documents = events_to_documents(events)
        count = upsert_documents(documents)

        logger.info(f"Scrape complete: {count} events indexed.")
        return {
            "statusCode": 200,
            "body": json.dumps({"scraped": count})
        }

    except Exception as e:
        logger.exception("Scraper Lambda failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }