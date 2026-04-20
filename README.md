# Venue Agent

Serverless RAG chatbot that answers questions about Théâtre Rialto — upcoming events, tickets, and venue FAQ. Powered by OpenAI GPT-4o-mini with ChromaDB vector search, deployed on AWS Lambda + Vercel.

**Live demo:** [venue-agent-nine.vercel.app](https://venue-agent-nine.vercel.app)

## Architecture

```
EventBridge (daily 6 AM)
    → Scraper Lambda
        → scrapes theatrerialto.ca/calendar
        → OpenAI embeddings
        → ChromaDB (persisted to S3)

User (Vercel frontend)
    → Next.js /api/chat (proxy)
        → API Gateway
            → Chat Lambda
                → ChromaDB metadata filter + semantic search (RAG)
                → GPT-4o-mini
                → answer with event details + ticket links
```

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | ChromaDB (persistent, S3-backed) |
| Backend | Python 3.11, AWS Lambda (Docker) |
| Container registry | AWS ECR |
| HTTP endpoint | AWS API Gateway |
| Scheduler | AWS EventBridge |
| Frontend | Next.js 14 + TypeScript |
| Frontend hosting | Vercel |
| CI/CD | GitHub Actions |
| Validation | Pydantic v2 |

## Project Structure

```
venue-agent/
├── app/
│   ├── handler.py          # Chat Lambda entrypoint + Pydantic validation
│   ├── agent.py            # RAG pipeline (date-aware metadata filtering)
│   ├── embedder.py         # ChromaDB client + OpenAI embeddings + S3 backup
│   ├── scraper.py          # theatrerialto.ca/calendar parser
│   └── scraper_handler.py  # Scraper Lambda entrypoint
├── frontend/
│   ├── app/
│   │   ├── page.tsx        # Chat UI
│   │   ├── layout.tsx
│   │   └── globals.css
│   └── pages/api/
│       └── chat.ts         # Vercel serverless proxy
├── .github/workflows/
│   └── deploy.yml          # CI/CD — builds Docker image, deploys both Lambdas
├── Dockerfile
└── requirements.txt
```

## Engineering Decisions

**RAG with metadata filtering** — ChromaDB stores event embeddings with structured metadata (`date_int: YYYYMMDD`). Date-range queries (e.g. "this weekend", "events in May") use metadata filtering rather than pure semantic similarity, which is more precise for temporal queries. Specific questions ("tell me about Bingo Loco") use cosine similarity search.

**S3-backed ChromaDB** — Lambda `/tmp` is ephemeral. After each scrape, the ChromaDB directory is archived and uploaded to S3. On cold start, the chat Lambda restores from S3 before serving requests — no persistent compute needed.

**Two-Lambda architecture** — scraper and chat are separate Lambda functions sharing one Docker image (different CMD). Scraper runs without VPC (needs internet to scrape), chat Lambda handles user requests. EventBridge triggers the scraper daily.

**Vercel proxy** — the API key never reaches the browser. Vercel serverless function proxies requests to API Gateway, injecting the key from environment variables server-side.

**Docker over zip** — container image provides reproducible environment, simplifies local testing via Lambda Runtime Interface Emulator, and supports heavy dependencies (ChromaDB, numpy) without Lambda size constraints.

## Local Development

```bash
# Build image
docker build -t venue-agent .

# Run scraper (populates ChromaDB in /tmp/venue-chroma)
docker run --rm \
  -e OPENAI_API_KEY=sk-... \
  -e EFS_MOUNT_PATH=/tmp \
  -v /tmp/venue-chroma:/tmp/chroma \
  -p 9000:8080 \
  venue-agent app.scraper_handler.lambda_handler

curl -X POST http://localhost:9000/2015-03-31/functions/function/invocations -d '{}'

# Run chat Lambda (reads from same volume)
docker run --rm \
  -e OPENAI_API_KEY=sk-... \
  -e EFS_MOUNT_PATH=/tmp \
  -e API_KEY=test-key \
  -v /tmp/venue-chroma:/tmp/chroma \
  -p 9000:8080 \
  venue-agent app.handler.lambda_handler

curl -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
  -H "Content-Type: application/json" \
  -d '{"headers":{"x-api-key":"test-key"},"body":"{\"question\":\"What is on this weekend?\"}"}'
```

## Deploy Your Own

### AWS Setup
1. Create ECR repository: `venue-agent`
2. Create two Lambda functions: `venue-agent` and `venue-agent-scraper` (same image, different CMD)
3. Create S3 bucket for ChromaDB backup
4. Create EventBridge schedule targeting `venue-agent-scraper` (daily cron)
5. Add IAM policy: scraper Lambda can invoke chat Lambda

### GitHub Secrets
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_ACCOUNT_ID
```

### Vercel Setup
1. Import repo, set Root Directory to `frontend`
2. Add environment variables:
   - `LAMBDA_URL` — API Gateway endpoint
   - `API_KEY` — Lambda API key
3. In Project Settings → General → Ignored Build Step, select "Only build if there are changes in a folder" and enter `frontend/`

**Deployment triggers:**
- Push changes to `app/`, `Dockerfile`, or `requirements.txt` → AWS Lambda redeploys
- Push changes to `frontend/` → Vercel redeploys
- Push changes to `README.md` or other files → nothing redeploys

## API

```bash
curl -X POST "https://your-api-id.execute-api.us-east-2.amazonaws.com/prod/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -d '{"question": "What is on this weekend?"}'
```

```json
{
  "answer": "This weekend at Théâtre Rialto, there are two events on Saturday, April 25: Candlelight: Tribute to Adele at 6:30 PM and Candlelight: A Tribute to Coldplay at 9:00 PM."
}
```