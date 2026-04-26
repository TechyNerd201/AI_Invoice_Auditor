from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings
from langchain_groq import ChatGroq as ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from log_utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class RetrieverService:
    """
    Retrieves relevant chunks from Qdrant based on a query,
    then sends them as context to the LLM for a grounded answer.
    """

    def __init__(self, collection_name: str = "invoice_collection", top_k: int = 5):
        self.collection_name = collection_name
        self.top_k = top_k

        self.embeddings = BedrockEmbeddings(
            model_id=os.getenv("AWS_BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

        self.llm = ChatOpenAI(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

        self.qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
            timeout=60,
        )

        logger.info(
            "[retriever_service] Initialized — collection='%s', top_k=%d",
            self.collection_name, self.top_k,
        )

    def retrieve(self, query: str, job_id: str = None, invoice_file: str = None) -> List[Dict[str, Any]]:
        """
        Embed the query and search Qdrant for the top-k most similar chunks.

        Args:
            query:        Natural language question
            job_id:       Filter to chunks from a specific job (e.g. "DEMO-001")
            invoice_file: Filter to chunks from a specific invoice file (e.g. "INV_DE_004.pdf")

        Returns:
            List of dicts with keys: 'text', 'score', 'metadata'
        """
        logger.info("[retriever_service][retrieve] Query: '%s' | job_id=%s | invoice_file=%s",
                    query, job_id, invoice_file)

        query_vector = self.embeddings.embed_query(query)

        # Build Qdrant filter if any filter criteria provided
        qdrant_filter = None
        conditions = []
        if job_id:
            conditions.append(FieldCondition(key="job_id", match=MatchValue(value=job_id)))
        if invoice_file:
            conditions.append(FieldCondition(key="invoice_file", match=MatchValue(value=invoice_file)))
        if conditions:
            qdrant_filter = Filter(must=conditions)
            logger.debug("[retriever_service][retrieve] Applying filter: %s",
                         {"job_id": job_id, "invoice_file": invoice_file})

        hits = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=self.top_k,
            with_payload=True,
            query_filter=qdrant_filter,
        ).points

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append({
                "text": payload.get("text", ""),
                "score": round(hit.score, 4),
                "metadata": {k: v for k, v in payload.items() if k != "text"},
            })

        logger.info("[retriever_service][retrieve] Retrieved %d chunk(s)", len(results))
        return results

    def answer(self, query: str, job_id: str = None, invoice_file: str = None) -> Dict[str, Any]:
        """
        Retrieve relevant chunks and send them with the query to the LLM.

        Args:
            query:        Natural language question
            job_id:       Filter to a specific job (e.g. "DEMO-001")
            invoice_file: Filter to a specific invoice file (e.g. "INV_DE_004.pdf")

        Returns:
            Dict with keys: 'query', 'answer', 'chunks_used', 'chunks'
        """
        chunks = self.retrieve(query, job_id=job_id, invoice_file=invoice_file)

        if not chunks:
            logger.warning("[retriever_service][answer] No chunks retrieved — LLM cannot answer")
            return {
                "query": query,
                "answer": "No relevant invoice data found in the vector store for this query.",
                "chunks_used": 0,
                "chunks": [],
            }

        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(chunks, start=1):
            meta = chunk["metadata"]
            meta_str = ", ".join(f"{k}={v}" for k, v in meta.items() if v) if meta else ""
            header = f"[Chunk {i} | score={chunk['score']}" + (f" | {meta_str}" if meta_str else "") + "]"
            context_parts.append(f"{header}\n{chunk['text']}")

        context = "\n\n".join(context_parts)

        messages = [
            SystemMessage(
                content=(
                    "You are an AI Invoice Auditor assistant. "
                    "Answer the user's question using ONLY the invoice chunks provided as context. "
                    "If the answer cannot be found in the context, say so clearly. "
                    "Be concise and precise."
                )
            ),
            HumanMessage(
                content=f"Context (retrieved invoice chunks):\n\n{context}\n\n---\n\nQuestion: {query}"
            ),
        ]

        logger.info("[retriever_service][answer] Sending %d chunk(s) to LLM", len(chunks))
        response = self.llm.invoke(messages)
        answer_text = response.content

        logger.info("[retriever_service][answer] LLM response received (%d chars)", len(answer_text))
        return {
            "query": query,
            "answer": answer_text,
            "chunks_used": len(chunks),
            "chunks": chunks,
        }


if __name__ == "__main__":
    # Quick test — run: python services/retriever_service.py
    service = RetrieverService(top_k=5)
    query = input("Enter your query: ").strip()
    job_id = input("Filter by job_id (leave blank for all): ").strip() or None
    invoice_file = input("Filter by invoice_file (leave blank for all): ").strip() or None

    result = service.answer(query, job_id=job_id, invoice_file=invoice_file)

    print(f"\nQuery: {result['query']}")
    print(f"Chunks used: {result['chunks_used']}")
    print(f"\nAnswer:\n{result['answer']}")
    print("\n--- Retrieved Chunks ---")
    for i, chunk in enumerate(result["chunks"], 1):
        print(f"\n[{i}] score={chunk['score']} | {chunk['metadata']}")
        print(chunk["text"][:300])
