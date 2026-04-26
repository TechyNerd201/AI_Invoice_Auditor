import os
from langchain_core.messages import SystemMessage
from pathlib import Path
import sys
import json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from state import JobState

from langchain_experimental.text_splitter import SemanticChunker
from langchain_aws import BedrockEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv
from log_utils.logger import get_logger


load_dotenv()

logger = get_logger(__name__)




class Chunker:
    def __init__(self,state:JobState):
        self.state = state

    def semantic_chunking(self, data):
        logger.debug("[ingestion_agent][Chunker.semantic_chunking] Starting — input length: %d chars", len(data) if isinstance(data, str) else len(str(data)))
        try:
            splitter = SemanticChunker(
                embeddings=BedrockEmbeddings(
                    model_id=os.getenv("AWS_BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                ),
                breakpoint_threshold_type="standard_deviation",
                breakpoint_threshold_amount=0.5
            )
            chunks = splitter.create_documents([data])
            logger.info("[ingestion_agent][Chunker.semantic_chunking] Created %d semantic chunks", len(chunks))
            return chunks
        except Exception as e:
            logger.error("[ingestion_agent][Chunker.semantic_chunking] Failed: %s", e, exc_info=True)
            raise

    def table_chunker(self  , table_data) -> list:
        """Each table row → one Document with table/row metadata."""
        logger.debug("[ingestion_agent][Chunker.table_chunker] Processing %d table(s)", len(table_data) if table_data else 0)
        try:
            tables = table_data
            chunks = []

            for table in tables:
                page = table.get("page", "?")
                table_idx = table.get("table_index", "?")

                for row_idx, row in enumerate(table.get("rows", [])):
                    cell_texts = [str(cell).strip() for cell in row if cell and str(cell).strip()]
                    if not cell_texts:
                        continue

                    row_text = " | ".join(cell_texts)

                    chunks.append(Document(
                        page_content=row_text,
                        metadata={
                            "source": "table",
                            "data_type": "invoice_input",
                            "chunk_type": "invoice_input::table_row",
                            "job_id": self.state.get("job_id", ""),
                            "invoice_file": Path(self.state.get("invoice_path", "")).name,
                            "page": page,
                            "table_index": table_idx,
                            "row_index": row_idx,
                        }
                    ))
            logger.info("[ingestion_agent][Chunker.table_chunker] Created %d table-row chunk(s) from %d table(s)", len(chunks), len(tables))
            return chunks if chunks else None
        except Exception as e:
            logger.error("[ingestion_agent][Chunker.table_chunker] Failed: %s", e, exc_info=True)
            raise

    def line_items_chunker(self , line_item_data:json) -> list:
        """Each line item dict → one Document with all fields as readable text."""
        logger.debug("[ingestion_agent][Chunker.line_items_chunker] Processing %d line item(s)", len(line_item_data) if line_item_data else 0)
        try:
            # If translation corrupted the JSON, line_item_data may arrive as a raw
            # JSON string instead of an already-parsed list.  Try to recover it.
            if isinstance(line_item_data, str):
                import json as _json
                try:
                    line_item_data = _json.loads(line_item_data)
                except Exception:
                    logger.warning("[ingestion_agent][Chunker.line_items_chunker] line_item_data is a string and could not be parsed as JSON — skipping")
                    return []
            line_items = line_item_data
            chunks = []

            for idx, item in enumerate(line_items):
                lines = [f"{key}: {value}" for key, value in item.items() if value not in (None, "", [])]
                if not lines:
                    continue

                chunks.append(Document(
                    page_content="\n".join(lines),
                    metadata={
                        "source": "line_item",
                        "data_type": "invoice_input",
                        "chunk_type": "invoice_input::line_item",
                        "job_id": self.state.get("job_id", ""),
                        "invoice_file": Path(self.state.get("invoice_path", "")).name,
                        "line_item_index": idx,
                    }
                ))

            logger.info("[ingestion_agent][Chunker.line_items_chunker] Created %d line-item chunk(s)", len(chunks))
            return chunks
        except Exception as e:
            logger.error("[ingestion_agent][Chunker.line_items_chunker] Failed: %s", e, exc_info=True)
            raise

    def metadata_chunker(self, data:dict):
        logger.debug("[ingestion_agent][Chunker.metadata_chunker] Processing metadata with %d keys", len(data) if isinstance(data, dict) else 0)
        try:
            metadata = data
            if not metadata:
                logger.debug("[ingestion_agent][Chunker.metadata_chunker] No metadata provided — skipping")
                return None

            lines = [f"{key}: {value}" for key, value in metadata.items() if value not in (None, "", [])]
            if not lines:
                return None

            return Document(
                page_content="\n".join(lines),
                metadata={
                    "source": "metadata",
                    "data_type": "invoice_input",
                    "chunk_type": "invoice_input::metadata",
                    "job_id": self.state.get("job_id", ""),
                    "invoice_file": Path(self.state.get("invoice_path", "")).name,
                }
            )
        except Exception as e:
            logger.error("[ingestion_agent][Chunker.metadata_chunker] Failed: %s", e, exc_info=True)
            raise

    def extract_chunking(self):
        logger.info("[ingestion_agent][Chunker.extract_chunking] Starting chunking for job_id=%s", self.state.get("job_id", "unknown"))
        try:
            raw_invoice_text = self.state.get("raw_invoice_text")
            table_data = self.state.get("tables")
            line_item_data = self.state.get("line_items")
            metadata = self.state.get("metadata")
            report_data = self.state.get("report")
            chunks = []

            if raw_invoice_text:
                text_chunks = self.semantic_chunking(raw_invoice_text)
                for idx, chunk in enumerate(text_chunks):
                    chunk.metadata["source"] = "raw_invoice_text"
                    chunk.metadata["data_type"] = "invoice_input"
                    chunk.metadata["chunk_type"] = "invoice_input::raw_invoice_text"
                    chunk.metadata["job_id"] = self.state.get("job_id", "")
                    chunk.metadata["invoice_file"] = Path(self.state.get("invoice_path", "")).name
                    chunk.metadata["chunk_index"] = idx
                chunks.extend(text_chunks)

            if table_data:
                chunks.extend(self.table_chunker(table_data))
            if line_item_data:
                # print(line_item_data[0])
                if isinstance(line_item_data, str):
                    import json as _json
                    try:
                        line_item_data = _json.loads(line_item_data)
                    except Exception as e:
                        logger.warning("[ingestion_agent][extract_chunking] line_item_data is a string and could not be parsed as JSON — skipping. Error: %s", e)
                        line_item_data = []
                
                chunks.extend(self.line_items_chunker(line_item_data))
            if metadata:
                logger.info("METADATA: %s", metadata)
                logger.info("METADATA TYPE: %s", type(metadata))
                result = self.metadata_chunker(metadata)
                if result:
                    chunks.append(result)

            if report_data:
                report_chunks = self.semantic_chunking(report_data)
                for idx, chunk in enumerate(report_chunks):
                    chunk.metadata["source"] = "report"
                    chunk.metadata["data_type"] = "invoice_output"
                    chunk.metadata["chunk_type"] = "invoice_output::report"
                    chunk.metadata["job_id"] = self.state.get("job_id", "")
                    chunk.metadata["invoice_file"] = Path(self.state.get("invoice_path", "")).name
                    chunk.metadata["chunk_index"] = idx
                chunks.extend(report_chunks)

            logger.info("[ingestion_agent][Chunker.extract_chunking] Total %d chunk(s) produced for job_id=%s", len(chunks), self.state.get("job_id", "unknown"))
            return chunks
        except Exception as e:
            logger.error("[ingestion_agent][Chunker.extract_chunking] Failed for job_id=%s: %s", self.state.get("job_id", "unknown"), e, exc_info=True)
            raise

    def embedder(self, chunks):
        logger.info("[ingestion_agent][Chunker.embedder] Embedding %d chunk(s) for job_id=%s", len(chunks), self.state.get("job_id", "unknown"))
        try:
            embeddings = BedrockEmbeddings(
                model_id=os.getenv("AWS_BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )
            texts = [doc.page_content for doc in chunks]
            vectors = embeddings.embed_documents(texts)

            embedded_chunks = [
                {
                    "text": doc.page_content,
                    "vector": vector,
                    "metadata": doc.metadata
                }
                for doc, vector in zip(chunks, vectors)
            ]
            logger.info("[ingestion_agent][Chunker.embedder] Successfully created %d embedding vector(s)", len(embedded_chunks))
            return embedded_chunks
        except Exception as e:
            logger.error("[ingestion_agent][Chunker.embedder] Embedding failed: %s", e, exc_info=True)
            raise


class VectorStore:
    """Handles all Qdrant vector DB operations."""

    def __init__(self, collection_name: str = "invoice_collection"):
        from qdrant_client import QdrantClient
        self.collection_name = collection_name
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
            timeout=60,  # seconds — increased for slow/proxied connections
        )

    def ensure_collection(self, vector_size: int):
        """Create collection if it doesn't exist."""
        try:
            from qdrant_client.models import VectorParams, Distance
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in existing:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                logger.info("[ingestion_agent][VectorStore.ensure_collection] Created new Qdrant collection '%s' (vector_size=%d)", self.collection_name, vector_size)
            else:
                logger.debug("[ingestion_agent][VectorStore.ensure_collection] Collection '%s' already exists — skipping creation", self.collection_name)
        except Exception as e:
            logger.error("[ingestion_agent][VectorStore.ensure_collection] Failed for collection '%s': %s", self.collection_name, e, exc_info=True)
            raise

    def push(self, embedded_chunks: list) -> int:
        """
        Push embedded chunks to Qdrant.
        Each item: {text, vector, metadata}
        Returns number of points stored.
        """
        logger.debug("[ingestion_agent][VectorStore.push] Preparing to push %d embedded chunk(s) to collection '%s'", len(embedded_chunks), self.collection_name)
        try:
            from qdrant_client.models import PointStruct
            import uuid

            if not embedded_chunks:
                logger.warning("[ingestion_agent][VectorStore.push] No embedded chunks provided — nothing to push")
                return 0

            vector_size = len(embedded_chunks[0]["vector"])
            self.ensure_collection(vector_size)

            def deterministic_id(item: dict) -> str:
                m = item["metadata"]
                key = f"{m.get('job_id','')}::{m.get('chunk_type','')}::{m.get('chunk_index', m.get('row_index', m.get('line_item_index', '')))}"
                return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))

            points = [
                PointStruct(
                    id=deterministic_id(item),
                    vector=item["vector"],
                    payload={"text": item["text"], **item["metadata"]}
                )
                for item in embedded_chunks
            ]
            # Upsert in small batches to avoid write timeouts over slow/proxied connections
            batch_size = 5
            for i in range(0, len(points), batch_size):
                batch = points[i: i + batch_size]
                self.client.upsert(collection_name=self.collection_name, points=batch)
                logger.debug("[ingestion_agent][VectorStore.push] Upserted batch %d-%d of %d", i + 1, i + len(batch), len(points))
            logger.info("[ingestion_agent][VectorStore.push] Upserted %d vector(s) to collection '%s'", len(points), self.collection_name)
            return len(points)
        except Exception as e:
            logger.error("[ingestion_agent][VectorStore.push] Failed for collection '%s': %s", self.collection_name, e, exc_info=True)
            raise


def ingestion_agent(state: JobState) -> dict:
    """
    Ingestion agent node for LangGraph.
    Chunks all invoice data, embeds it, and stores it in Qdrant.
    Returns updates to merge into JobState.
    """

    job_id = state.get("job_id", "unknown")
    events = []

    events.append(SystemMessage(content=f"[ingestion_agent] Started for job_id={job_id}"))
    logger.info("[ingestion_agent] Starting for job_id=%s", job_id)

    # 1. Chunk
    try:
        chunker = Chunker(state)
        chunks = chunker.extract_chunking()
        if not chunks:
            events.append(SystemMessage(content="[ingestion_agent] No chunks produced — aborting"))
            logger.warning("[ingestion_agent] No chunks produced for job_id=%s — aborting", job_id)
            return {
                "events": events,
                "error": ["ingestion_agent: No chunks produced"],
            }
        events.append(SystemMessage(content=f"[ingestion_agent] Chunking complete — {len(chunks)} chunks produced"))
        logger.info("[ingestion_agent] Chunking complete — %d chunk(s) produced for job_id=%s", len(chunks), job_id)
    except Exception as e:
        events.append(SystemMessage(content=f"[ingestion_agent] Chunking failed: {e}"))
        logger.error("[ingestion_agent] Chunking failed for job_id=%s: %s", job_id, e, exc_info=True)
        return {
            "events": events,
            "error": [f"[ingestion_agent]: Chunking failed: {e}"],
        }

    # 2. Embed
    try:
        embedded = chunker.embedder(chunks)
        events.append(SystemMessage(content=f"[ingestion_agent] Embedding complete — {len(embedded)} vectors ready"))
        logger.info("[ingestion_agent] Embedding complete — %d vector(s) ready for job_id=%s", len(embedded), job_id)
    except Exception as e:
        events.append(SystemMessage(content=f"[ingestion_agent] Embedding failed: {e}"))
        logger.error("[ingestion_agent] Embedding failed for job_id=%s: %s", job_id, e, exc_info=True)
        return {
            "events": events,
            "error": [f"[ingestion_agent] Embedding failed: {e}"],
        }

    # 3. Store
    try:
        collection = os.getenv("QDRANT_COLLECTION", "invoice_collection")
        store = VectorStore(collection_name=collection)
        count = store.push(embedded)
        events.append(SystemMessage(content=f"[ingestion_agent] Stored {count} vectors in Qdrant collection '{collection}'"))
        logger.info("[ingestion_agent] Stored %d vector(s) in Qdrant collection '%s' for job_id=%s", count, collection, job_id)
    except Exception as e:
        events.append(SystemMessage(content=f"[ingestion_agent] Qdrant storage failed: {e}"))
        logger.error("[ingestion_agent] Qdrant storage failed for job_id=%s: %s", job_id, e, exc_info=True)
        result = {
            "events": events,
            "error": [f"[ingestion_agent] Qdrant storage failed: {e}"],
        }
        logger.warning("STATE IN INGESTION AGENT : %s", result)
        return result


    logger.info("[ingestion_agent] Completed successfully for job_id=%s — %d vector(s) stored", job_id, count)
    return {
        "events": events,
        "chunk_count": count,
    }


# if __name__ == "__main__":
#     state = {
#         "job_id": "DEMO-001",
#         "invoice_path": "uploads/INV_DE_004.pdf",
#         "raw_invoice_text": (
#             "BLUE LOGISTIC VIETNAM\nNO 89--98 HAM MG STREET\n"
#             "Bill of Lading: SGN24XXX25\nDate: 03-Dec-2024\n"
#             "Voyage: 1TUB2XXXA Vessel: ROOSEVELT\n"
#             "Total Excluding Tax 134,131,986.00\nTotal Including Tax 134,462,512.00"
#         ),
#         "tables": [
#             {
#                 "page": 1, "table_index": 0,
#                 "rows": [
#                     ["Payment_Info\nBill of Lading: SGN24XXX25", "DEBIT NOTE COPY\nDate: 03-Dec-2024", None],
#                     ["C Freight charge 1 USD 5000", None, "127,495,000.00"],
#                 ]
#             }
#         ],
#         "line_items": [
#             {"description": "Freight charge", "rate": "5000", "currency": "USD", "amount_vnd": "127,495,000.00"},
#             {"description": "Port handling fee", "rate": "6050000", "currency": "VND", "amount_vnd": "6,050,000.00"},
#         ],
#         "metadata": {
#             "sender": "accounts@oceanfreight.in",
#             "subject": "Invoice for Container Transport - PO-1006",
#             "received_timestamp": "2025-06-01T09:00:00Z",
#         },
#         "report": None,
#     }

#     SEP = "=" * 60

#     # ── STEP 1: CHUNKING ──────────────────────────────────────────
#     print(f"\n{SEP}")
#     print("STEP 1 — CHUNKING")
#     print(SEP)

#     chunker = Chunker(state)
#     chunks = chunker.extract_chunking()

#     print(f"Total chunks produced: {len(chunks)}")
#     for i, c in enumerate(chunks, 1):
#         print(f"\n  --- Chunk {i} ---")
#         print(f"  chunk_type : {c.metadata.get('chunk_type')}")
#         print(f"  job_id     : {c.metadata.get('job_id')}")
#         print(f"  invoice    : {c.metadata.get('invoice_file')}")
#         print(f"  metadata   : { {k: v for k, v in c.metadata.items() if k not in ('chunk_type', 'job_id', 'invoice_file')} }")
#         print(f"  content    : {c.page_content[:150]}")

#     # ── STEP 2: EMBEDDING ─────────────────────────────────────────
#     print(f"\n{SEP}")
#     print("STEP 2 — EMBEDDING")
#     print(SEP)

#     embedded_chunks = chunker.embedder(chunks)

#     print(f"Embedded {len(embedded_chunks)} chunks")
#     for i, ec in enumerate(embedded_chunks, 1):
#         vector_preview = ec["vector"][:5]
#         print(f"\n  --- Embedded Chunk {i} ---")
#         print(f"  chunk_type  : {ec['metadata'].get('chunk_type')}")
#         print(f"  vector dim  : {len(ec['vector'])}")
#         print(f"  vector[:5]  : {[round(v, 6) for v in vector_preview]}")
#         print(f"  text preview: {ec['text'][:100]}")

#     # ── STEP 3: QDRANT STORAGE ────────────────────────────────────
#     print(f"\n{SEP}")
#     print("STEP 3 — STORING IN QDRANT")
#     print(SEP)

#     store = VectorStore(collection_name=f"invoice_collection")
#     count = store.push(embedded_chunks)

#     print(f"\nSuccessfully stored {count} vectors in collection '{store.collection_name}'")

#     # ── SUMMARY ──────────────────────────────────────────────────
#     print(f"\n{SEP}")
#     print("DEMO COMPLETE — SUMMARY")
#     print(SEP)
#     print(f"  job_id           : {state['job_id']}")
#     print(f"  invoice_file     : {Path(state['invoice_path']).name}")
#     print(f"  chunks produced  : {len(chunks)}")
#     print(f"  vectors stored   : {count}")
#     print(f"  qdrant collection: {store.collection_name}")
#     print(SEP)


