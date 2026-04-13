# Venue Agent

Serverless AI agent that answers questions about a venue — events, tickets, FAQ — powered by OpenAI GPT-4o-mini and deployed on AWS Lambda as a Docker container image.

## Architecture

```
HTTP POST /ask
    → API Gateway
    → AWS Lambda (Docker container)
    → OpenAI GPT-4o-mini
    → JSON response
```

CI/CD: every push to `main` automatically builds and deploys via GitHub Actions.

## Tech Stack

- **Python 3.11**
- **OpenAI API** (GPT-4o-mini)
- **Docker** — container image deployment
- **AWS Lambda** — serverless compute
- **AWS ECR** — container registry
- **API Gateway** — HTTP endpoint
- **GitHub Actions** — CI/CD pipeline

## Project Structure

```
venue-agent/
├── app/
│   ├── handler.py      # Lambda entrypoint
│   ├── agent.py        # OpenAI integration
│   └── knowledge.py    # Context builder from venue data
├── data/
│   └── venue_info.json # Venue knowledge base
├── .github/
│   └── workflows/
│       └── deploy.yml  # CI/CD pipeline
├── Dockerfile
└── requirements.txt
```

## Engineering Decisions

**Docker over zip deployment** — container image provides a reproducible environment, simplifies local testing via Lambda Runtime Interface, and supports heavier dependencies without size constraints.

**Context injection via system prompt** — venue data is loaded from a JSON knowledge base and injected into the LLM system prompt at runtime. This keeps the agent factually grounded without requiring a vector database for this scale.

**API key authentication** — requests require an `x-api-key` header, validated in the Lambda handler before any LLM call is made. Keys are stored as Lambda environment variables, never in source code.

**Stateless design** — each Lambda invocation is fully independent, consistent with serverless best practices and horizontal scaling.

## Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
python3 -c "from app.agent import ask_agent; print(ask_agent('When is the next event?'))"
```

## Local Docker Test

```bash
docker build -t venue-agent .
docker run -p 9000:8080 -e OPENAI_API_KEY=$OPENAI_API_KEY -e API_KEY=your-key venue-agent
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{"body": "{\"question\": \"When is the next event?\"}"}'
```

## Deploy Your Own

1. Create AWS ECR repository and Lambda function
2. Add GitHub Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`
3. Push to `main` — GitHub Actions handles the rest

## API Usage

```bash
curl -X POST "https://your-api-id.execute-api.us-east-2.amazonaws.com/prod/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"question": "When is the next event?"}'
```

Response:
```json
{
  "answer": "The next event at Rialto Theatre is Jazz Night on May 10, 2025, at 20:00."
}
```