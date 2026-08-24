import os
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ..models import Document, DocumentSummary
from .chroma_service import chroma_service
from .document_processor import chunk_text, extract_text_by_file_type
from .embedding_service import EmbeddingService
from .summarization_service import SummarizationService


def resolve_document_path(doc: Document) -> Optional[str]:
    """Resolve doc.file_path to an existing absolute path on disk if available."""
    if not doc:
        return None
    if doc.file_path and os.path.exists(doc.file_path):
        return doc.file_path

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_dir = os.path.abspath(os.path.join(backend_dir, ".."))

    filename_base = os.path.basename(doc.file_path) if doc.file_path else doc.filename

    candidates = [
        os.path.join(root_dir, doc.file_path) if doc.file_path else "",
        os.path.join(backend_dir, doc.file_path) if doc.file_path else "",
        os.path.join(backend_dir, "uploads", f"user_{doc.user_id}", filename_base),
        os.path.join(backend_dir, "uploads", f"user_{doc.user_id}", doc.filename or ""),
        os.path.join(backend_dir, "uploads", f"user_{doc.user_id}", doc.original_filename or ""),
        os.path.join(root_dir, "uploads", f"user_{doc.user_id}", filename_base),
        os.path.join(root_dir, "uploads", f"user_{doc.user_id}", doc.filename or ""),
        os.path.join(root_dir, "backend", "uploads", f"user_{doc.user_id}", filename_base),
        os.path.join(root_dir, "backend", "uploads", f"user_{doc.user_id}", doc.filename or ""),
        os.path.join(backend_dir, "storage", "documents", f"user_{doc.user_id}", filename_base),
        os.path.join(backend_dir, "storage", "datasets", f"user_{doc.user_id}", filename_base),
    ]

    for c in candidates:
        if c and os.path.exists(c):
            return c

    return None



class RAGService:
    """Automatic multi-document RAG Service restricted strictly to authenticated user's documents."""

    def __init__(self):
        self.summarizer = SummarizationService()
        self.embedding_service = EmbeddingService()

    def get_document_text(self, doc: Document, db: Session) -> str:
        """Extract text from file on disk or fallback to DocumentSummary text in DB."""
        real_path = resolve_document_path(doc)
        if real_path:
            try:
                extracted = extract_text_by_file_type(real_path, doc.file_type)
                cleaned = " ".join(extracted.split())
                if cleaned:
                    return cleaned
            except Exception as exc:
                print(f"[RAGService] File extract error for doc {doc.id}: {exc}")

        # Fallback: check DocumentSummary table in DB
        summary_record = (
            db.query(DocumentSummary)
            .filter(DocumentSummary.document_id == doc.id, DocumentSummary.user_id == doc.user_id)
            .first()
        )
        if summary_record:
            text_parts = [summary_record.summary or ""]
            if summary_record.key_points:
                text_parts.append("Key Points: " + ", ".join(summary_record.key_points))
            if summary_record.important_information:
                text_parts.append("Important Information: " + ", ".join(summary_record.important_information))
            if summary_record.action_items:
                text_parts.append("Action Items: " + ", ".join(summary_record.action_items))
            combined = " ".join(" ".join(text_parts).split())
            if combined:
                return combined

        return ""

    def ensure_user_documents_indexed(self, user_id: int, db: Session) -> List[Document]:
        """Ensure all valid documents belonging to user_id are extracted and indexed in ChromaDB."""
        completed_docs = (
            db.query(Document)
            .filter(Document.user_id == user_id, Document.processing_status != "failed")
            .all()
        )

        if not completed_docs:
            return []

        for doc in completed_docs:
            # Check if ChromaDB has vectors for this document_id
            try:
                existing = chroma_service.collection.get(
                    where={
                        "$and": [
                            {"document_id": str(doc.id)},
                            {"user_id": str(user_id)},
                        ]
                    }
                )

                if not existing.get("ids"):
                    cleaned_text = self.get_document_text(doc, db)
                    if cleaned_text:
                        chunks = chunk_text(cleaned_text, chunk_size=800, overlap=120)
                        if chunks:
                            embeddings = self.embedding_service.generate_embeddings(chunks)
                            chroma_service.add_document_chunks(
                                document_id=doc.id,
                                user_id=user_id,
                                filename=doc.original_filename,
                                chunks=chunks,
                                embeddings=embeddings,
                            )
            except Exception as exc:
                print(f"[RAGService] Indexing error for doc {doc.id}: {exc}")

        return completed_docs

    def rewrite_query_for_context(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Rewrite an ambiguous follow-up question using recent conversation history into a standalone search query."""
        if not conversation_history or len(conversation_history) == 0:
            return question

        formatted_messages = []
        for msg in conversation_history[-6:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = (msg.get("content") or "").strip()
            if content:
                formatted_messages.append(f"{role}: {content}")

        if not formatted_messages:
            return question

        history_str = "\n".join(formatted_messages)

        prompt = (
            "Given the following recent chat conversation between a user and an AI document assistant, "
            "rewrite the latest user question into a complete, standalone, self-contained search query "
            "suitable for searching uploaded business documents.\n\n"
            "RULES:\n"
            "1. Replace pronouns (it, that, they, this) or underspecified references "
            "with full context from the prior conversation.\n"
            "2. Do NOT answer the question.\n"
            "3. Return ONLY the rewritten standalone search query as a single line of plain text.\n"
            "4. If the question is already a complete standalone question, return it as is.\n\n"
            f"CONVERSATION HISTORY:\n{history_str}\n\n"
            f"LATEST USER QUESTION:\n{question}"
        )

        try:
            rewritten = self.summarizer._call_gemini_api(prompt)
            clean_rewritten = rewritten.strip().replace("\n", " ")
            if clean_rewritten and len(clean_rewritten) > 3:
                return clean_rewritten
        except Exception as exc:
            print(f"[RAGService] Query rewrite fallback: {exc}")

        return question

    def retrieve_relevant_chunks(
        self,
        user_id: int,
        question: str,
        n_results: int = 8,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant text chunks across ALL completed documents belonging to user_id."""
        if not question or not question.strip():
            return []

        # 1. Ensure user's completed documents are indexed
        completed_docs = []
        if db:
            completed_docs = self.ensure_user_documents_indexed(user_id, db)

        # 2. Get vector search matches from ChromaDB
        vector_matches = []
        try:
            vector_matches = chroma_service.search_document_chunks(
                query_text=question,
                user_id=user_id,
                n_results=n_results,
            )
        except Exception as exc:
            print(f"[RAGService] Vector search error: {exc}")

        # 3. Perform hybrid keyword & text matching across user's document text for maximum recall
        query_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', question.lower()))

        # Expand synonym / typo terms
        expanded_words = set(query_words)
        for w in query_words:
            if "leav" in w or "pto" in w or "vacat" in w:
                expanded_words.update(["leave", "leaves", "policy", "entitlement", "pto", "vacation"])
            if "sick" in w or "ill" in w or "sl" in w or "medic" in w:
                expanded_words.update(["sick", "sl", "illness", "medical", "leave", "doctor", "certificate"])

        hybrid_chunks = []
        seen_texts = set()

        # Add ChromaDB vector matches
        for match in vector_matches:
            text = match.get("text", "").strip()
            meta = match.get("metadata", {})
            doc_id = meta.get("document_id")

            if str(meta.get("user_id")) != str(user_id):
                continue

            normalized = " ".join(text.lower().split()[:20])
            if normalized in seen_texts:
                continue
            seen_texts.add(normalized)

            hybrid_chunks.append({
                "document_id": int(doc_id) if doc_id and str(doc_id).isdigit() else 0,
                "filename": meta.get("filename", "Document"),
                "text": text,
                "score": 10.0,
            })

        # If vector search returned few chunks, perform direct document text chunk search across ALL user docs
        if len(hybrid_chunks) < 5 and completed_docs and db:
            for doc in completed_docs:
                try:
                    cleaned_text = self.get_document_text(doc, db)
                    if not cleaned_text:
                        continue

                    doc_chunks = chunk_text(cleaned_text, chunk_size=800, overlap=120)
                    for chunk in doc_chunks:
                        chunk_lower = chunk.lower()
                        score = sum(1 for word in expanded_words if word in chunk_lower)
                        if score == 0:
                            score = 0.5  # Baseline score so general queries ('summarize', 'tell me about file') always get chunks!

                        normalized = " ".join(chunk_lower.split()[:20])
                        if normalized not in seen_texts:
                            seen_texts.add(normalized)
                            hybrid_chunks.append({
                                "document_id": doc.id,
                                "filename": doc.original_filename,
                                "text": chunk,
                                "score": float(score),
                            })
                except Exception as exc:
                    print(f"[RAGService] Direct text search error on doc {doc.id}: {exc}")

        # Sort by score descending and return top chunks
        hybrid_chunks.sort(key=lambda x: x["score"], reverse=True)
        return hybrid_chunks[:6]


    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return ""

        context_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            context_parts.append(
                f"[Source {idx}: {chunk['filename']} (Document ID: {chunk['document_id']})]\n{chunk['text']}"
            )
        return "\n\n".join(context_parts)

    def generate_rag_answer(
        self,
        user_id: int,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Perform automatic RAG across ALL completed documents for user_id and generate direct answer."""
        if db:
            completed_count = (
                db.query(Document)
                .filter(Document.user_id == user_id, Document.processing_status == "completed")
                .count()
            )
            if completed_count == 0:
                return {
                    "answer": "You haven't uploaded any documents yet. Please upload business documents to start using the AI Assistant.",
                    "sources": [],
                    "has_documents": False,
                }

        # 1. Rewrite ambiguous follow-up questions internally into a standalone search query
        search_query = self.rewrite_query_for_context(question, conversation_history)
        if search_query != question:
            print(f"[RAGService] Follow-Up Rewritten Query: '{search_query}' (Original: '{question}')")

        # 2. Retrieve top relevant chunks across ALL completed documents for current user using search_query
        chunks = self.retrieve_relevant_chunks(user_id=user_id, question=search_query, db=db)

        if not chunks:
            return {
                "answer": "I couldn't find that information in your uploaded documents.",
                "sources": [],
                "has_documents": True,
            }

        context = self.build_context(chunks)

        history_text = ""
        if conversation_history:
            formatted_messages = []
            for msg in conversation_history[-6:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                formatted_messages.append(f"{role}: {msg.get('content', '')}")
            if formatted_messages:
                history_text = "RECENT CONVERSATION HISTORY:\n" + "\n".join(formatted_messages) + "\n\n"

        prompt = (
            "You are IntelliBusiness, an AI assistant for business documents.\n\n"
            "Answer the user's question using ONLY the information provided in the retrieved context from the user's uploaded documents.\n\n"
            "Your response must be:\n"
            "- Short\n"
            "- Direct\n"
            "- Clear\n"
            "- Easy to understand\n"
            "- Relevant to the user's exact question\n\n"
            "IMPORTANT RULES:\n"
            "1. Search results may come from multiple documents.\n"
            "2. Combine relevant information when necessary.\n"
            "3. Do not invent facts.\n"
            "4. Do not use information outside the retrieved document context.\n"
            "5. Do not guess when information is missing.\n"
            "6. Preserve important dates, names, and numbers.\n"
            "7. Do not repeat the question.\n"
            "8. Do not give a long explanation unless the user explicitly asks for detail.\n"
            "9. Prefer 1 to 4 short paragraphs.\n"
            "10. If the answer can be given in one sentence, do so.\n"
            "11. Use bullet points only when they improve clarity.\n\n"
            "If the information is not available in the provided context, say:\n"
            "'I couldn't find that information in your uploaded documents.'\n\n"
            f"{history_text}"
            f"RETRIEVED DOCUMENT CONTEXT:\n{context}\n\n"
            f"USER QUESTION:\n{question}"
        )

        try:
            raw_answer = self.summarizer._call_gemini_api(prompt)
            answer = raw_answer.strip()
        except Exception as exc:
            err_str = str(exc)
            if "GEMINI_API_KEY" in err_str or "API key" in err_str or "invalid" in err_str.lower():
                answer = f"⚠️ AI Assistant Notice: {err_str}"
            else:
                answer = f"I couldn't process the query: {err_str}"


        # Deduplicate sources used
        sources_dict = {}
        for chunk in chunks:
            doc_id = chunk["document_id"]
            if doc_id and doc_id not in sources_dict:
                sources_dict[doc_id] = {
                    "document_id": doc_id,
                    "filename": chunk["filename"],
                }

        sources = list(sources_dict.values())

        return {
            "answer": answer,
            "sources": sources,
            "has_documents": True,
        }


rag_service = RAGService()
