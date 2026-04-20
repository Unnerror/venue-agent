import json
import os
import logging
from pydantic import BaseModel, field_validator, ValidationError
from app.agent import ask_agent
from app.embedder import upsert_documents

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

API_KEY = os.environ.get("API_KEY")


class QuestionRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > 1000:
            raise ValueError("question must be 1000 characters or fewer")
        return v


def lambda_handler(event, context):
    if event.get("source") == "scraper":
        return _handle_upsert(event)
    return _handle_question(event)


def _handle_upsert(event):
    try:
        documents = event.get("documents", [])
        if not documents:
            return {"statusCode": 400, "body": json.dumps({"error": "No documents provided"})}
        count = upsert_documents(documents)
        logger.info(f"Upserted {count} documents from scraper.")
        return {"statusCode": 200, "body": json.dumps({"upserted": count})}
    except Exception as e:
        logger.exception("Upsert failed")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def _handle_question(event):
    try:
        headers = event.get("headers", {})
        request_key = headers.get("x-api-key") or headers.get("X-Api-Key")
        if API_KEY and request_key != API_KEY:
            return _response(401, {"error": "Unauthorized"})

        raw_body = event.get("body", "{}")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})

        try:
            request = QuestionRequest(**body)
        except ValidationError as e:
            return _response(400, {"error": e.errors()[0]["msg"]})

        answer = ask_agent(request.question)
        return _response(200, {"answer": answer})

    except Exception as e:
        logger.exception("Unhandled error in _handle_question")
        return _response(500, {"error": "Internal server error"})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }