import os
import logging
from typing import Optional

# Patch sqlite3 for AWS Lambda (Amazon Linux 2 ships sqlite3 < 3.35.0)
# pysqlite3-binary provides a newer version that ChromaDB requires
__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

import chromadb
from chromadb.config import Settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# EFS mount path — Lambda монтирует EFS сюда (настраивается в AWS консоли)
EFS_MOUNT_PATH = os.environ.get("EFS_MOUNT_PATH", "/mnt/efs")
CHROMA_PATH = os.path.join(EFS_MOUNT_PATH, "chroma")
COLLECTION_NAME = "venue_events"

EMBEDDING_MODEL = "text-embedding-3-small"

_client: Optional[chromadb.Client] = None
_collection = None


def _get_collection():
    """Lazy singleton — инициализируется один раз на lifetime Lambda контейнера."""
    global _client, _collection
    if _collection is not None:
        return _collection

    _client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"ChromaDB collection '{COLLECTION_NAME}' ready at {CHROMA_PATH}")
    return _collection


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a batch of texts."""
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def upsert_documents(documents: list[dict]) -> int:
    """
    Upsert documents into ChromaDB.
    Each document: {"id": str, "text": str, "metadata": dict}
    Returns count of upserted documents.
    """
    if not documents:
        logger.warning("No documents to upsert.")
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

    logger.info(f"Upserted {len(documents)} documents into ChromaDB.")
    return len(documents)


def query_collection(question: str, n_results: int = 3) -> list[str]:
    """
    Query ChromaDB with a natural language question.
    Returns top-n matching document texts.
    """
    collection = _get_collection()

    if collection.count() == 0:
        logger.warning("ChromaDB collection is empty — no events indexed yet.")
        return []

    question_embedding = embed_texts([question])[0]

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    docs = results.get("documents", [[]])[0]
    logger.info(f"Query returned {len(docs)} results.")
    return docs