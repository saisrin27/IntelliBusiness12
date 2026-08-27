import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import BusinessDataset, User
from ..services.business_analytics_service import business_analytics_service

router = APIRouter(prefix="/api/business-analytics", tags=["AI Business Analytics"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "storage" / "datasets"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


class QuestionRequest(BaseModel):
    question: str


# ============================================
# 1. FILE UPLOAD & AI ANALYSIS ENDPOINT
# ============================================

@router.post("/upload")
def upload_and_analyze_business_data(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    original_name = file.filename or "business_data"
    ext = Path(original_name).suffix.lower()
    if ext not in [".csv", ".xlsx", ".xls", ".pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload CSV, Excel (.xlsx/.xls), or PDF.")

    user_folder = UPLOAD_ROOT / f"user_{current_user.id}"
    user_folder.mkdir(parents=True, exist_ok=True)

    saved_filename = f"{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{original_name}"
    file_path = user_folder / saved_filename

    contents = file.file.read()
    file_path.write_bytes(contents)

    # Perform backend analysis & calculations
    try:
        analysis_result = business_analytics_service.parse_and_analyze_data(str(file_path), original_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error analyzing business data: {str(exc)}")

    # Store in database
    dataset = BusinessDataset(
        user_id=current_user.id,
        filename=saved_filename,
        original_filename=original_name,
        file_path=str(file_path),
        file_type=ext.replace(".", ""),
        extracted_summary=analysis_result.get("key_stats", {}),
        insights=analysis_result.get("insights", []),
        charts_config=analysis_result.get("charts_config", []),
        created_at=datetime.datetime.utcnow(),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    # Let workflows consume the exact analysis generated for this upload.
    try:
        from ..services.workflow_service import workflow_engine_service
        workflow_engine_service.trigger_event(
            user_id=current_user.id,
            trigger_type="document_uploaded",
            payload={
                "document_id": dataset.id,
                "original_filename": original_name,
                "file_path": str(file_path),
                "file_type": ext.replace(".", ""),
                "business_analysis": analysis_result,
            },
            db=db,
        )
    except Exception as exc:
        print(f"[BusinessAnalyticsUpload] Workflow trigger error: {exc}")

    return {
        "id": dataset.id,
        "filename": original_name,
        "key_stats": analysis_result.get("key_stats", {}),
        "insights": analysis_result.get("insights", []),
        "charts_config": analysis_result.get("charts_config", []),
        "created_at": dataset.created_at,
    }


# ============================================
# 2. DATASETS LIST & GET DETAILS
# ============================================

@router.get("/datasets")
def list_user_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    datasets = (
        db.query(BusinessDataset)
        .filter(BusinessDataset.user_id == current_user.id)
        .order_by(BusinessDataset.created_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.original_filename,
            "file_type": d.file_type.upper(),
            "created_at": d.created_at,
            "key_stats": d.extracted_summary or {},
        }
        for d in datasets
    ]


@router.get("/datasets/{dataset_id}")
def get_dataset_details(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = (
        db.query(BusinessDataset)
        .filter(BusinessDataset.id == dataset_id, BusinessDataset.user_id == current_user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    return {
        "id": dataset.id,
        "filename": dataset.original_filename,
        "key_stats": dataset.extracted_summary or {},
        "insights": dataset.insights or [],
        "charts_config": dataset.charts_config or [],
        "created_at": dataset.created_at,
    }


# ============================================
# 3. ASK AI ABOUT DATASET
# ============================================

@router.post("/datasets/{dataset_id}/ask")
def ask_question_about_dataset(
    dataset_id: int,
    req: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Please enter a question about your business data.")

    dataset = (
        db.query(BusinessDataset)
        .filter(BusinessDataset.id == dataset_id, BusinessDataset.user_id == current_user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    dataset_info = {
        "filename": dataset.original_filename,
        "file_path": dataset.file_path,
        "file_type": dataset.file_type,
        "key_stats": dataset.extracted_summary or {},
        "insights": dataset.insights or [],
    }

    answer = business_analytics_service.answer_data_question(dataset_info, req.question.strip())
    return {"question": req.question.strip(), "answer": answer}


# ============================================
# 4. DOWNLOAD PDF REPORT
# ============================================

@router.get("/datasets/{dataset_id}/pdf")
def download_pdf_report(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = (
        db.query(BusinessDataset)
        .filter(BusinessDataset.id == dataset_id, BusinessDataset.user_id == current_user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    pdf_filename = f"Business_Analysis_Report_{dataset.id}.pdf"
    pdf_path = Path(dataset.file_path).parent / pdf_filename

    dataset_info = {
        "filename": dataset.original_filename,
        "key_stats": dataset.extracted_summary or {},
        "insights": dataset.insights or [],
        "charts_config": dataset.charts_config or [],
    }

    try:
        business_analytics_service.generate_pdf_report(dataset_info, str(pdf_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generating PDF report: {str(exc)}")

    return FileResponse(
        path=str(pdf_path),
        filename=f"Business_Report_{dataset.original_filename}.pdf",
        media_type="application/pdf",
    )
