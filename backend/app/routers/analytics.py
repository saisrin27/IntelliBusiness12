import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    ChatConversation,
    ChatMessage,
    Document,
    DocumentSummary,
    Email,
    History,
    User,
    Workflow,
    WorkflowRun,
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics Dashboard"])


def get_start_date(period: str) -> Optional[datetime.datetime]:
    """Helper to convert period string into a starting datetime filter."""
    now = datetime.datetime.utcnow()
    if period == "7d":
        return now - datetime.timedelta(days=7)
    elif period == "30d":
        return now - datetime.timedelta(days=30)
    elif period == "90d":
        return now - datetime.timedelta(days=90)
    return None  # All time


def format_relative_time(dt: datetime.datetime) -> str:
    """Format datetime into friendly string."""
    if not dt:
        return "Recently"
    now = datetime.datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins} min ago" if mins == 1 else f"{mins} mins ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
    elif seconds < 172800:
        return f"Yesterday at {dt.strftime('%I:%M %p')}"
    else:
        return dt.strftime("%b %d, %Y")


# ============================================
# 1. OVERVIEW KPIS ENDPOINT
# ============================================

@router.get("/overview")
def get_analytics_overview(
    period: str = Query(default="7d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = get_start_date(period)

    # Documents
    doc_q = db.query(Document).filter(Document.user_id == current_user.id)
    if start_date:
        doc_q = doc_q.filter(Document.upload_date >= start_date)
    total_docs = doc_q.count()
    processed_docs = doc_q.filter(Document.processing_status == "completed").count()

    # Summaries
    sum_q = db.query(DocumentSummary).filter(DocumentSummary.user_id == current_user.id)
    if start_date:
        sum_q = sum_q.filter(DocumentSummary.created_at >= start_date)
    total_summaries = sum_q.count()

    # AI Chat Questions
    chat_q = (
        db.query(ChatMessage)
        .join(ChatConversation)
        .filter(ChatConversation.user_id == current_user.id, ChatMessage.role == "user")
    )
    if start_date:
        chat_q = chat_q.filter(ChatMessage.created_at >= start_date)
    chat_questions = chat_q.count()

    # Emails
    email_q = db.query(Email).filter(Email.user_id == current_user.id)
    if start_date:
        email_q = email_q.filter(Email.created_at >= start_date)
    emails_generated = email_q.count()
    emails_sent = email_q.filter(Email.status == "sent").count()

    # Workflows
    wf_q = db.query(Workflow).filter(Workflow.user_id == current_user.id)
    active_workflows = wf_q.filter(Workflow.is_active == True).count()

    return {
        "period": period,
        "total_documents": total_docs,
        "processed_documents": processed_docs,
        "total_summaries": total_summaries,
        "chat_questions": chat_questions,
        "emails_generated": emails_generated,
        "emails_sent": emails_sent,
        "active_workflows": active_workflows,
    }


# ============================================
# 2. DOCUMENT ANALYTICS ENDPOINT
# ============================================

@router.get("/documents")
def get_document_analytics(
    period: str = Query(default="7d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = get_start_date(period)
    doc_q = db.query(Document).filter(Document.user_id == current_user.id)
    if start_date:
        doc_q = doc_q.filter(Document.upload_date >= start_date)

    # Status breakdown
    completed = doc_q.filter(Document.processing_status == "completed").count()
    processing = doc_q.filter(Document.processing_status == "processing").count()
    failed = doc_q.filter(Document.processing_status == "failed").count()

    # Time series (daily breakdown for chart)
    num_days = 7 if period == "7d" else (30 if period == "30d" else (90 if period == "90d" else 30))
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(num_days - 1, -1, -1)]

    labels = [d.strftime("%b %d") for d in days]
    series_data = []

    for d in days:
        start_dt = datetime.datetime.combine(d, datetime.time.min)
        end_dt = datetime.datetime.combine(d, datetime.time.max)
        c = (
            db.query(Document)
            .filter(
                Document.user_id == current_user.id,
                Document.upload_date >= start_dt,
                Document.upload_date <= end_dt,
            )
            .count()
        )
        series_data.append(c)

    # Recent uploads
    recent_uploads = (
        doc_q.order_by(Document.upload_date.desc())
        .limit(5)
        .all()
    )
    recent_list = [
        {
            "id": d.id,
            "filename": d.original_filename,
            "file_type": d.file_type.upper(),
            "file_size": round(d.file_size / 1024, 1) if d.file_size else 0,
            "status": d.processing_status,
            "upload_date": format_relative_time(d.upload_date),
        }
        for d in recent_uploads
    ]

    return {
        "status_distribution": {
            "completed": completed,
            "processing": processing,
            "failed": failed,
        },
        "time_series": {
            "labels": labels,
            "data": series_data,
        },
        "recent_uploads": recent_list,
    }


# ============================================
# 3. AI USAGE ANALYTICS ENDPOINT
# ============================================

@router.get("/ai-usage")
def get_ai_usage_analytics(
    period: str = Query(default="7d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = get_start_date(period)

    # Feature usage breakdown
    summaries_cnt = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.user_id == current_user.id)
    )
    if start_date:
        summaries_cnt = summaries_cnt.filter(DocumentSummary.created_at >= start_date)
    summaries_count = summaries_cnt.count()

    chats_cnt = (
        db.query(ChatMessage)
        .join(ChatConversation)
        .filter(ChatConversation.user_id == current_user.id, ChatMessage.role == "user")
    )
    if start_date:
        chats_cnt = chats_cnt.filter(ChatMessage.created_at >= start_date)
    chats_count = chats_cnt.count()

    emails_cnt = (
        db.query(Email)
        .filter(Email.user_id == current_user.id)
    )
    if start_date:
        emails_cnt = emails_cnt.filter(Email.created_at >= start_date)
    emails_count = emails_cnt.count()

    # Time series (daily questions & AI tasks)
    num_days = 7 if period == "7d" else (30 if period == "30d" else (90 if period == "90d" else 30))
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(num_days - 1, -1, -1)]

    labels = [d.strftime("%b %d") for d in days]
    questions_series = []

    for d in days:
        start_dt = datetime.datetime.combine(d, datetime.time.min)
        end_dt = datetime.datetime.combine(d, datetime.time.max)
        c = (
            db.query(ChatMessage)
            .join(ChatConversation)
            .filter(
                ChatConversation.user_id == current_user.id,
                ChatMessage.role == "user",
                ChatMessage.created_at >= start_dt,
                ChatMessage.created_at <= end_dt,
            )
            .count()
        )
        questions_series.append(c)

    return {
        "feature_breakdown": {
            "Document Summaries": summaries_count,
            "AI Chat Queries": chats_count,
            "AI Email Generation": emails_count,
        },
        "questions_series": {
            "labels": labels,
            "data": questions_series,
        },
    }


# ============================================
# 4. EMAIL ANALYTICS ENDPOINT
# ============================================

@router.get("/emails")
def get_email_analytics(
    period: str = Query(default="7d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = get_start_date(period)
    q = db.query(Email).filter(Email.user_id == current_user.id)
    if start_date:
        q = q.filter(Email.created_at >= start_date)

    generated = q.count()
    sent = q.filter(Email.status == "sent").count()
    failed = q.filter(Email.status == "failed").count()
    drafts = q.filter(Email.status == "draft").count()

    # Time series
    num_days = 7 if period == "7d" else (30 if period == "30d" else (90 if period == "90d" else 30))
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(num_days - 1, -1, -1)]

    labels = [d.strftime("%b %d") for d in days]
    sent_series = []

    for d in days:
        start_dt = datetime.datetime.combine(d, datetime.time.min)
        end_dt = datetime.datetime.combine(d, datetime.time.max)
        c = (
            db.query(Email)
            .filter(
                Email.user_id == current_user.id,
                Email.status == "sent",
                Email.sent_at >= start_dt,
                Email.sent_at <= end_dt,
            )
            .count()
        )
        sent_series.append(c)

    return {
        "metrics": {
            "generated": generated,
            "sent": sent,
            "failed": failed,
            "drafts": drafts,
        },
        "time_series": {
            "labels": labels,
            "data": sent_series,
        },
    }


# ============================================
# 5. WORKFLOW ANALYTICS ENDPOINT
# ============================================

@router.get("/workflows")
def get_workflow_analytics(
    period: str = Query(default="7d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = get_start_date(period)

    total_workflows = db.query(Workflow).filter(Workflow.user_id == current_user.id).count()
    active_workflows = db.query(Workflow).filter(Workflow.user_id == current_user.id, Workflow.is_active == True).count()

    run_q = db.query(WorkflowRun).filter(WorkflowRun.user_id == current_user.id)
    if start_date:
        run_q = run_q.filter(WorkflowRun.started_at >= start_date)

    total_runs = run_q.count()
    completed_runs = run_q.filter(WorkflowRun.status == "completed").count()
    failed_runs = run_q.filter(WorkflowRun.status == "failed").count()
    running_runs = run_q.filter(WorkflowRun.status == "running").count()

    return {
        "total_workflows": total_workflows,
        "active_workflows": active_workflows,
        "total_runs": total_runs,
        "status_distribution": {
            "completed": completed_runs,
            "failed": failed_runs,
            "running": running_runs,
        },
    }


# ============================================
# 6. RECENT ACTIVITY LOG ENDPOINT
# ============================================

@router.get("/activity")
def get_analytics_activity(
    period: str = Query(default="7d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = get_start_date(period)
    activities = []

    # 1. Documents Uploaded
    doc_q = db.query(Document).filter(Document.user_id == current_user.id)
    if start_date:
        doc_q = doc_q.filter(Document.upload_date >= start_date)
    for doc in doc_q.order_by(Document.upload_date.desc()).limit(8).all():
        activities.append({
            "id": f"doc_{doc.id}",
            "raw_time": doc.upload_date,
            "category": "Document",
            "icon": "fas fa-file-alt",
            "icon_color": "text-primary",
            "bg_color": "bg-primary-subtle",
            "title": f"Document Uploaded: {doc.original_filename}",
            "description": f"File type: {doc.file_type.upper()} ({doc.processing_status})",
            "timestamp": format_relative_time(doc.upload_date),
        })

    # 2. Emails Generated/Sent
    email_q = db.query(Email).filter(Email.user_id == current_user.id)
    if start_date:
        email_q = email_q.filter(Email.created_at >= start_date)
    for email in email_q.order_by(Email.created_at.desc()).limit(8).all():
        status_text = (email.status or "draft").capitalize()
        activities.append({
            "id": f"email_{email.id}",
            "raw_time": email.created_at,
            "category": "Email",
            "icon": "fas fa-paper-plane",
            "icon_color": "text-purple",
            "bg_color": "bg-purple-subtle",
            "title": f"Email {status_text}: {email.subject}",
            "description": f"Recipient: {email.recipient_email}",
            "timestamp": format_relative_time(email.created_at),
        })

    # 3. AI Chat Sessions
    chat_q = db.query(ChatConversation).filter(ChatConversation.user_id == current_user.id)
    if start_date:
        chat_q = chat_q.filter(ChatConversation.updated_at >= start_date)
    for chat in chat_q.order_by(ChatConversation.updated_at.desc()).limit(8).all():
        activities.append({
            "id": f"chat_{chat.id}",
            "raw_time": chat.updated_at,
            "category": "AI Assistant",
            "icon": "fas fa-robot",
            "icon_color": "text-success",
            "bg_color": "bg-success-subtle",
            "title": f"AI Assistant Session: {chat.title}",
            "description": "Multi-document RAG query executed",
            "timestamp": format_relative_time(chat.updated_at),
        })

    # 4. Workflow Runs
    wf_q = db.query(WorkflowRun).filter(WorkflowRun.user_id == current_user.id)
    if start_date:
        wf_q = wf_q.filter(WorkflowRun.started_at >= start_date)
    for run in wf_q.order_by(WorkflowRun.started_at.desc()).limit(8).all():
        activities.append({
            "id": f"wfrun_{run.id}",
            "raw_time": run.started_at,
            "category": "Workflow",
            "icon": "fas fa-network-wired",
            "icon_color": "text-warning",
            "bg_color": "bg-warning-subtle",
            "title": f"Workflow Run #{run.id}",
            "description": f"Status: {run.status.capitalize()}",
            "timestamp": format_relative_time(run.started_at),
        })

    # Sort combined activities by raw_time descending
    activities.sort(key=lambda x: x["raw_time"] if x["raw_time"] else datetime.datetime.min, reverse=True)

    # Return top 15 items
    final_list = []
    for item in activities[:15]:
        final_list.append({
            "id": item["id"],
            "category": item["category"],
            "icon": item["icon"],
            "icon_color": item["icon_color"],
            "bg_color": item["bg_color"],
            "title": item["title"],
            "description": item["description"],
            "timestamp": item["timestamp"],
        })

    return final_list
