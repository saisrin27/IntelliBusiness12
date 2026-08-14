import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings


CHROMA_DEFAULT_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
COLLECTION_NAME = "intellibusiness_documents"


class ChromaService:
    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or CHROMA_DEFAULT_PERSIST_DIR
        self.client = chromadb.Client(Settings(
            persist_directory=self.persist_directory,
            anonymized_telemetry=False,
        ))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document_chunks(
        self,
        document_id: int,
        user_id: int,
        filename: str,
        chunks: List[str],
        embeddings: List[List[float]],
    ) -> None:
        if not chunks:
            return

        ids = []
        embeddings_list = []
        metadatas = []
        for index, chunk in enumerate(chunks):
            ids.append(f"doc_{document_id}_chunk_{index}")
            embeddings_list.append(embeddings[index])
            metadatas.append({
                "user_id": str(user_id),
                "document_id": str(document_id),
                "filename": filename,
                "chunk_index": str(index),
            })

        self.collection.add(
            ids=ids,
            embeddings=embeddings_list,
            metadatas=metadatas,
            documents=chunks,
        )

    def search_document_chunks(
        self,
        query_text: str,
        user_id: int,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        if not query_text.strip():
            return []

        # The embedding service is intentionally lightweight and deterministic.
        # We generate a query embedding in the same way for a consistent search.
        from .embedding_service import EmbeddingService

        service = EmbeddingService(api_key=os.getenv("AI_API_KEY"))
        query_embedding = service.generate_embedding(query_text)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"user_id": str(user_id)},
        )

        matches = []
        if not results.get("documents"):
            return matches

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results.get("distances", [[]])[0]
        for idx, doc in enumerate(documents):
            match = {
                "text": doc,
                "metadata": metadatas[idx],
                "distance": distances[idx] if idx < len(distances) else None,
            }
            matches.append(match)
        return matches

    def delete_document_vectors(self, document_id: int, user_id: int) -> None:
        try:
            self.collection.delete(
                where={
                    "$and": [
                        {"document_id": str(document_id)},
                        {"user_id": str(user_id)},
                    ]
                }
            )
        except Exception:
            pass


chroma_service = ChromaService()
