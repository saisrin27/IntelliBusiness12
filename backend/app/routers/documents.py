import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
import io
import textwrap
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from ..auth import create_document_view_token, get_current_user, verify_document_view_token
from ..database import get_db
from ..models import Document, DocumentSummary, User
from ..schemas import DocumentListResponse, DocumentResponse, DocumentStatsResponse, DocumentSummaryResponse, MessageResponse
from ..services.chroma_service import chroma_service
from ..services.document_processor import chunk_text, extract_text_by_file_type
from ..services.embedding_service import EmbeddingService
from ..services.summarization_service import SummarizationService

router = APIRouter(prefix="/api/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
}
MAX_FILE_SIZE = 10 * 1024 * 1024
UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads"
VIEW_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def safe_filename(filename: str) -> str:
    safe = Path(filename).name
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    return safe


def save_upload_file(file: UploadFile, user_id: int) -> tuple[str, Path, int]:
    user_folder = UPLOAD_ROOT / f"user_{user_id}"
    user_folder.mkdir(parents=True, exist_ok=True)

    original_name = safe_filename(file.filename or "document")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: PDF, DOCX, PPTX, XLSX, TXT.")

    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds the 10 MB limit.")

    unique_name = f"{uuid.uuid4().hex}{extension}"
    file_path = user_folder / unique_name
    file_path.write_bytes(contents)
    return original_name, file_path, len(contents)


def process_document_record(document: Document, db: Session) -> None:
    try:
        if not document.file_path:
            raise ValueError("Document file path is missing.")

        extracted_text = extract_text_by_file_type(document.file_path, document.file_type)
        cleaned_text = " ".join(extracted_text.split())
        if not cleaned_text:
            raise ValueError("No extractable text was found in the uploaded file.")

        chunks = chunk_text(cleaned_text, chunk_size=800, overlap=120)
        if not chunks:
            raise ValueError("The document could not be chunked for indexing.")

        embedding_service = EmbeddingService(api_key=os.getenv("AI_API_KEY"))
        embeddings = embedding_service.generate_embeddings(chunks)

        if not embedding_service.is_configured():
            document.processing_error = "AI_API_KEY not configured; using local deterministic embeddings for development."

        chroma_service.add_document_chunks(
            document_id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            chunks=chunks,
            embeddings=embeddings,
        )

        document.processing_status = "completed"
        document.processing_error = None
        db.commit()
    except Exception as exc:
        document.processing_status = "failed"
        document.processing_error = str(exc)[:500]
        db.commit()


def get_user_document_or_403(document_id: int, user_id: int, db: Session) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.user_id != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to access this document.")
    return document


def get_document_file_response(document: Document, inline: bool = False) -> FileResponse:
    file_path = Path(document.file_path).resolve()
    upload_root = UPLOAD_ROOT.resolve()
    if upload_root not in file_path.parents and file_path != upload_root:
        raise HTTPException(status_code=403, detail="Invalid document path.")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    media_type = VIEW_MEDIA_TYPES.get(document.file_type, "application/octet-stream")
    disposition = "inline" if inline else "attachment"
    return FileResponse(
        path=str(file_path),
        filename=document.original_filename,
        media_type=media_type,
        headers={"Content-Disposition": f"{disposition}; filename=\"{document.original_filename}\""},
    )


@router.get("/stats", response_model=DocumentStatsResponse)
def get_document_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stats = {
        "total": db.query(Document).filter(Document.user_id == current_user.id).count(),
        "processing": db.query(Document).filter(Document.user_id == current_user.id, Document.processing_status == "processing").count(),
        "completed": db.query(Document).filter(Document.user_id == current_user.id, Document.processing_status == "completed").count(),
        "failed": db.query(Document).filter(Document.user_id == current_user.id, Document.processing_status == "failed").count(),
    }
    return DocumentStatsResponse(**stats)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    search: Optional[str] = Query(default=None, alias="search"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Document.filename.ilike(term), Document.original_filename.ilike(term)))

    total = query.count()
    offset = (page - 1) * limit
    items = query.order_by(Document.upload_date.desc()).offset(offset).limit(limit).all()
    return DocumentListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[DocumentResponse.from_orm(item) for item in items],
    )


@router.get("/search")
def search_documents(
    q: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not q or not q.strip():
        items = db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.upload_date.desc()).all()
        return {"items": [DocumentResponse.from_orm(item) for item in items]}

    query = db.query(Document).filter(Document.user_id == current_user.id)
    term = f"%{q.strip()}%"
    items = query.filter(or_(Document.filename.ilike(term), Document.original_filename.ilike(term))).all()
    return {"items": [DocumentResponse.from_orm(item) for item in items]}


@router.post("/upload", response_model=List[DocumentResponse])
def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved_documents = []

    for file in files:
        original_name, file_path, file_size = save_upload_file(file, current_user.id)
        doc = Document(
            user_id=current_user.id,
            filename=file_path.name,
            original_filename=original_name,
            file_path=str(file_path),
            file_type=ALLOWED_EXTENSIONS.get(Path(original_name).suffix.lower(), "txt"),
            file_size=file_size,
            processing_status="processing",
            processing_error=None,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Trigger active workflows for 'document_uploaded'
        try:
            from ..services.workflow_service import workflow_engine_service
            workflow_engine_service.trigger_event(
                user_id=current_user.id,
                trigger_type="document_uploaded",
                payload={
                    "document_id": doc.id,
                    "original_filename": original_name,
                    "file_path": str(file_path),
                },
                db=db,
            )
        except Exception as exc:
            print(f"[DocumentUpload] Workflow trigger error: {exc}")

        process_document_record(doc, db)

        # Trigger active workflows for 'document_processed'
        if doc.processing_status == "completed":
            try:
                workflow_engine_service.trigger_event(
                    user_id=current_user.id,
                    trigger_type="document_processed",
                    payload={
                        "document_id": doc.id,
                        "original_filename": original_name,
                        "file_path": str(file_path),
                    },
                    db=db,
                )
            except Exception as exc:
                print(f"[DocumentProcessed] Workflow trigger error: {exc}")

        saved_documents.append(doc)


    return [DocumentResponse.from_orm(item) for item in saved_documents]


@router.get("/{document_id}/view-token")
def generate_document_view_token(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_user_document_or_403(document_id, current_user.id, db)
    token = create_document_view_token(document.id, current_user.id)
    return {"token": token, "view_url": f"{os.getenv('CORS_ORIGINS', 'http://127.0.0.1:3000').split(',')[0]}/api/documents/{document.id}/view?token={token}"}


@router.get("/{document_id}/view")
def view_document(document_id: int, token: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    if token is None:
        raise HTTPException(status_code=403, detail="You do not have permission to access this document.")

    try:
        user_id = verify_document_view_token(token, document_id)
    except HTTPException:
        raise

    auth_user = db.query(User).filter(User.id == user_id).first()
    if auth_user is None:
        raise HTTPException(status_code=403, detail="You do not have permission to access this document.")

    document = get_user_document_or_403(document_id, auth_user.id, db)
    if document.file_type != "pdf":
        raise HTTPException(status_code=400, detail="Preview is not available for this file type. Please download the file.")

    return get_document_file_response(document, inline=True)


@router.get("/{document_id}/preview")
def preview_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_user_document_or_403(document_id, current_user.id, db)

    if document.file_type == "txt":
        try:
            with open(document.file_path, "r", encoding="utf-8", errors="replace") as file:
                text = file.read()
            return {"type": "txt", "content": text[:20000]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to read document text: {str(exc)}")

    if document.file_type == "pdf":
        return {"type": "pdf", "download_url": f"/api/documents/{document_id}/download"}

    return {"type": "unsupported", "message": "Preview is not available for this file type. Please download the file.", "download_url": f"/api/documents/{document_id}/download"}


@router.get("/{document_id}/download")
def download_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_user_document_or_403(document_id, current_user.id, db)
    return get_document_file_response(document, inline=False)


@router.delete("/{document_id}")
def delete_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    chroma_service.delete_document_vectors(document.id, current_user.id)
    db.delete(document)
    db.commit()
    return {"message": "Document deleted successfully."}


@router.post("/{document_id}/summarize")
def summarize_document(document_id: int, regenerate: bool = Query(default=False), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_user_document_or_403(document_id, current_user.id, db)
    if document.processing_status != "completed":
        raise HTTPException(status_code=400, detail="Your document is still being processed. Please try again shortly.")

    if not document.file_path or not Path(document.file_path).exists():
        raise HTTPException(status_code=404, detail="File not found.")

    existing_summary = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.document_id == document.id, DocumentSummary.user_id == current_user.id)
        .order_by(DocumentSummary.created_at.desc())
        .first()
    )

    if existing_summary and not regenerate:
        return {
            "message": "Summary loaded successfully.",
            "document_id": document.id,
            "filename": document.original_filename,
            "executive_summary": existing_summary.summary,
            "key_points": existing_summary.key_points or [],
            "important_information": existing_summary.important_information or [],
            "action_items": existing_summary.action_items or [],
            "keywords": existing_summary.keywords or [],
            "created_at": existing_summary.created_at.isoformat(),
        }

    try:
        extracted_text = extract_text_by_file_type(document.file_path, document.file_type)
        final_text = " ".join(extracted_text.split())
        if not final_text:
            raise ValueError("No extractable text was found in the uploaded file.")

        summarizer = SummarizationService(api_key=os.getenv("GEMINI_API_KEY"))
        response = summarizer.summarize_document_text(final_text, document.original_filename)

        if existing_summary and regenerate:
            existing_summary.summary = response["executive_summary"]
            existing_summary.key_points = response["key_points"]
            existing_summary.important_information = response["important_information"]
            existing_summary.action_items = response["action_items"]
            existing_summary.keywords = response["keywords"]
            existing_summary.updated_at = __import__("datetime").datetime.utcnow()
            db.commit()
            db.refresh(existing_summary)
            summary_record = existing_summary
            message = "Summary regenerated successfully."
        else:
            summary_record = DocumentSummary(
                document_id=document.id,
                user_id=current_user.id,
                summary=response["executive_summary"],
                key_points=response["key_points"],
                important_information=response["important_information"],
                action_items=response["action_items"],
                keywords=response["keywords"],
                created_at=__import__("datetime").datetime.utcnow(),
                updated_at=__import__("datetime").datetime.utcnow(),
            )
            db.add(summary_record)
            db.commit()
            db.refresh(summary_record)
            message = "Summary generated successfully."

        return {
            "message": message,
            "document_id": document.id,
            "filename": document.original_filename,
            "executive_summary": summary_record.summary,
            "key_points": summary_record.key_points or [],
            "important_information": summary_record.important_information or [],
            "action_items": summary_record.action_items or [],
            "keywords": summary_record.keywords or [],
            "created_at": summary_record.created_at.isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{document_id}/summary")
def get_document_summary(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_user_document_or_403(document_id, current_user.id, db)
    summary_record = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.document_id == document.id, DocumentSummary.user_id == current_user.id)
        .order_by(DocumentSummary.created_at.desc())
        .first()
    )
    if not summary_record:
        raise HTTPException(status_code=404, detail="Summary not found for this document.")

    return {
        "document_id": document.id,
        "filename": document.original_filename,
        "executive_summary": summary_record.summary,
        "key_points": summary_record.key_points or [],
        "important_information": summary_record.important_information or [],
        "action_items": summary_record.action_items or [],
        "keywords": summary_record.keywords or [],
        "created_at": summary_record.created_at.isoformat(),
    }


@router.get("/{document_id}")
def get_document_detail(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.from_orm(document)


@router.get("/{document_id}/summary/pdf")
def download_summary_pdf(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_user_document_or_403(document_id, current_user.id, db)

    summary_record = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.document_id == document.id, DocumentSummary.user_id == current_user.id)
        .order_by(DocumentSummary.created_at.desc())
        .first()
    )

    if not summary_record:
        # If no summary exists, attempt to generate one on-demand
        if document.processing_status != "completed":
            raise HTTPException(status_code=400, detail="Your document is still being processed. Please try again shortly.")

        try:
            extracted_text = extract_text_by_file_type(document.file_path, document.file_type)
            final_text = " ".join(extracted_text.split())
            if not final_text:
                raise ValueError("No extractable text was found in the uploaded file.")

            summarizer = SummarizationService(api_key=os.getenv("GEMINI_API_KEY"))
            response = summarizer.summarize_document_text(final_text, document.original_filename)

            summary_record = DocumentSummary(
                document_id=document.id,
                user_id=current_user.id,
                summary=response["executive_summary"],
                key_points=response["key_points"],
                important_information=response["important_information"],
                action_items=response["action_items"],
                keywords=response["keywords"],
                created_at=__import__("datetime").datetime.utcnow(),
                updated_at=__import__("datetime").datetime.utcnow(),
            )
            db.add(summary_record)
            db.commit()
            db.refresh(summary_record)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Build a printable text representation
    lines = []
    lines.append(f"Document: {document.original_filename}")
    lines.append(f"Generated: {summary_record.created_at.strftime('%d %b %Y')}")
    lines.append("")
    lines.append("EXECUTIVE SUMMARY")
    lines.append(summary_record.summary or "Not specified in the document.")
    lines.append("")
    lines.append("KEY POINTS")
    for kp in (summary_record.key_points or []):
        lines.append(f"• {kp}")
    lines.append("")
    lines.append("IMPORTANT INFORMATION")
    for info in (summary_record.important_information or []):
        lines.append(f"• {info}")
    lines.append("")
    lines.append("ACTION ITEMS")
    for act in (summary_record.action_items or []):
        lines.append(f"• {act}")
    lines.append("")
    lines.append("KEYWORDS")
    kw = ", ".join(summary_record.keywords or [])
    lines.append(kw or "Not specified in the document.")

    full_text = "\n".join(lines)

    # Generate PDF in-memory
    buffer = io.BytesIO()
    page_width, page_height = A4
    margin = 40

    # Try different font sizes to fit content into one page
    for font_size in (12, 11, 10, 9, 8):
        buffer.seek(0)
        buffer.truncate()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont("Helvetica", font_size)
        max_line_width = page_width - margin * 2
        approx_char_width = font_size * 0.6
        chars_per_line = max(20, int(max_line_width / approx_char_width))
        wrapped_lines = []
        for paragraph in full_text.split('\n'):
            wrapped_lines.extend(textwrap.wrap(paragraph, width=chars_per_line) or [""]) 

        line_height = font_size * 1.2
        max_lines = int((page_height - margin * 2) / line_height)

        if len(wrapped_lines) <= max_lines:
            y = page_height - margin
            for ln in wrapped_lines:
                c.drawString(margin, y, ln)
                y -= line_height
            c.showPage()
            c.save()
            buffer.seek(0)
            break
    else:
        # If nothing fit, truncate to max_lines with ellipsis
        buffer.seek(0)
        buffer.truncate()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont("Helvetica", 8)
        approx_char_width = 8 * 0.6
        chars_per_line = int((page_width - margin * 2) / approx_char_width)
        wrapped_lines = []
        for paragraph in full_text.split('\n'):
            wrapped_lines.extend(textwrap.wrap(paragraph, width=chars_per_line) or [""])
        max_lines = int((page_height - margin * 2) / (8 * 1.2))
        truncated = wrapped_lines[: max_lines - 1]
        truncated.append("... (truncated)")
        y = page_height - margin
        for ln in truncated:
            c.drawString(margin, y, ln)
            y -= 8 * 1.2
        c.showPage()
        c.save()
        buffer.seek(0)

    filename = f"{Path(document.original_filename).stem}_summary.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=\"{filename}\""})
