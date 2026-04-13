import json
import os
from app.agent import ask_agent

API_KEY = os.environ.get("API_KEY")

def lambda_handler(event, context):
    try:
        # API key check
        headers = event.get("headers", {})
        request_key = headers.get("x-api-key") or headers.get("X-Api-Key")

        if API_KEY and request_key != API_KEY:
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"})
            }

        body = json.loads(event.get("body", "{}"))
        question = body.get("question", "").strip()

        if not question:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing 'question' field"})
            }

        answer = ask_agent(question)

        return {
            "statusCode": 200,
            "body": json.dumps({"answer": answer})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }