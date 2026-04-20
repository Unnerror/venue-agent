import os
import io
import tarfile
import logging
from typing import Optional

# Patch sqlite3 for AWS Lambda
__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

import boto3
import chromadb
from chromadb.config import Settings
from openai import OpenAI

logger = logging.getLogger(__name__)

CHROMA_PATH = "/tmp/chroma"
COLLECTION_NAME = "venue_events"
EMBEDDING_MODEL = "text-embedding-3-small"
S3_BUCKET = os.environ.get("S3_BUCKET", "venue-agent-chromadb")
S3_KEY = "chroma_backup.tar.gz"

_collection = None


def _restore_from_s3():
    try:
        s3 = boto3.client("s3")
        buf = io.BytesIO()
        s3.download_fileobj(S3_BUCKET, S3_KEY, buf)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall("/tmp")
        logger.info("ChromaDB restored from S3.")
        return True
    except Exception as e:
        logger.warning(f"Could not restore from S3: {e}")
        return False


def _backup_to_s3():
    try:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(CHROMA_PATH, arcname="chroma")
        buf.seek(0)
        s3 = boto3.client("s3")
        s3.upload_fileobj(buf, S3_BUCKET, S3_KEY)
        logger.info("ChromaDB backed up to S3.")
    except Exception as e:
        logger.error(f"S3 backup failed: {e}")


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    if not os.path.exists(CHROMA_PATH):
        _restore_from_s3()

    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"ChromaDB ready, count={_collection.count()}")
    return _collection


def embed_texts(texts: list[str]) -> list[list[float]]:
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def upsert_documents(documents: list[dict]) -> int:
    if not documents:
        return 0

    collection = _get_collection()
    ids = [doc["id"] for doc in documents]
    texts = [doc["text"] for doc in documents]
    metadatas = [doc["metadata"] for doc in documents]

    logger.info(f"Generating embeddings for {len(texts)} documents...")
    embeddings = embed_texts(texts)

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    _backup_to_s3()
    return len(documents)


def query_collection(question: str, n_results: int = 5) -> list[str]:
    """Semantic similarity search — for specific questions like 'tell me about Bingo Loco'."""
    collection = _get_collection()
    if collection.count() == 0:
        return []

    question_embedding = embed_texts([question])[0]
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents"],
    )
    return results.get("documents", [[]])[0]


def query_by_date_range(date_from: str, date_to: str) -> list[str]:
    """
    Metadata filter search — for date/schedule queries.
    date_from, date_to: ISO format strings e.g. '2026-04-25'
    Returns all events within the date range.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    try:
        results = collection.get(
            where={
                "$and": [
                    {"date": {"$gte": date_from}},
                    {"date": {"$lte": date_to}},
                ]
            },
            include=["documents"],
        )
        docs = results.get("documents", [])
        logger.info(f"Date range query {date_from}→{date_to}: {len(docs)} results")
        return docs
    except Exception as e:
        logger.error(f"Date range query failed: {e}")
        return []


def get_all_documents() -> list[str]:
    """Fallback — return all documents."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    results = collection.get(include=["documents"])
    return results.get("documents", [])