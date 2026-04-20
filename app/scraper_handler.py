import json
import os
import logging
import boto3
from app.scraper import scrape_calendar, events_to_documents

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CHAT_LAMBDA_NAME = os.environ.get("CHAT_LAMBDA_NAME", "venue-agent")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")


def lambda_handler(event, context):
    """
    Triggered by EventBridge once per day (no VPC needed).
    1. Scrapes theatrerialto.ca/calendar
    2. Invokes chat Lambda (which has EFS access) to upsert into ChromaDB
    """
    logger.info("Scraper Lambda triggered.")

    try:
        events = scrape_calendar()
        if not events:
            logger.warning("No events scraped — site may be down or structure changed.")
            return {"statusCode": 200, "body": json.dumps({"scraped": 0})}

        documents = events_to_documents(events)
        logger.info(f"Scraped {len(documents)} events, invoking chat Lambda to upsert...")

        lambda_client = boto3.client("lambda", region_name=AWS_REGION)
        response = lambda_client.invoke(
            FunctionName=CHAT_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "source": "scraper",
                "documents": documents
            })
        )

        result = json.loads(response["Payload"].read())
        logger.info(f"Chat Lambda response: {result}")

        return {
            "statusCode": 200,
            "body": json.dumps({"scraped": len(documents), "upsert_result": result})
        }

    except Exception as e:
        logger.exception("Scraper Lambda failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }