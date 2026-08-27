import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    ChatConversation,
    ChatMessage,
    Document,
    DocumentSummary,
    Email,
    User,
    Workflow,
)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def format_relative_time(dt: datetime.datetime) -> str:
    """Format datetime into friendly relative string (e.g. '5 minutes ago', 'Today at 2:30 PM')."""
    if not dt:
        return "Recently"

    now = datetime.datetime.utcnow()
    diff = now - dt

    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min ago" if minutes == 1 else f"{minutes} mins ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
    elif seconds < 172800:
        return f"Yesterday at {dt.strftime('%I:%M %p')}"
    else:
        return dt.strftime("%b %d, %Y at %I:%M %p")


@router.get(
    "/stats",
    summary="Get user real-time dashboard statistics",
    response_model=Dict[str, int],
)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Protected Endpoint:
    Returns REAL-TIME dashboard statistics for the authenticated user from MySQL database.
    """
    # 1. Real document count
    documents_count = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .count()
    )

    # 2. Real emails generated/sent count
    emails_count = (
        db.query(Email)
        .filter(Email.user_id == current_user.id)
        .count()
    )

    # 3. Real AI Tasks count (Summaries + AI Chat User Messages + Emails)
    summaries_count = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.user_id == current_user.id)
        .count()
    )
    chat_messages_count = (
        db.query(ChatMessage)
        .join(ChatConversation)
        .filter(ChatConversation.user_id == current_user.id, ChatMessage.role == "user")
        .count()
    )

    total_ai_tasks = summaries_count + chat_messages_count + emails_count

    # 4. Workflows count
    workflows_count = (
        db.query(Workflow)
        .filter(Workflow.user_id == current_user.id)
        .count()
    )

    return {
        "documents": documents_count,
        "ai_tasks": total_ai_tasks,
        "emails_generated": emails_count,
        "workflows": workflows_count,
    }


@router.get(
    "/recent-activity",
    summary="Get user real-time recent activity timeline",
    response_model=List[Dict[str, Any]],
)
def get_recent_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Protected Endpoint:
    Returns REAL-TIME recent activities timeline for the authenticated user.
    """
    activities = []

    # 1. Fetch recent document uploads
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )
    for doc in docs:
        kb_size = round(doc.file_size / 1024, 1) if doc.file_size else 0
        activities.append({
            "id": f"doc_{doc.id}",
            "raw_time": doc.upload_date,
            "type": "document",
            "icon": "fas fa-file-alt",
            "icon_color": "text-primary",
            "bg_color": "bg-primary-subtle",
            "title": doc.original_filename,
            "description": f"Document uploaded ({kb_size} KB, Status: {doc.processing_status.capitalize()})",
            "timestamp": format_relative_time(doc.upload_date),
        })

    # 2. Fetch recent emails
    emails = (
        db.query(Email)
        .filter(Email.user_id == current_user.id)
        .order_by(Email.created_at.desc())
        .all()
    )
    for email in emails:
        recipient = email.recipient_email or "recipient"
        status_text = (email.status or "draft").capitalize()
        activities.append({
            "id": f"email_{email.id}",
            "raw_time": email.created_at,
            "type": "email",
            "icon": "fas fa-paper-plane",
            "icon_color": "text-purple",
            "bg_color": "bg-purple-subtle",
            "title": f"Email: {email.subject}",
            "description": f"Recipient: {recipient} ({status_text})",
            "timestamp": format_relative_time(email.created_at),
        })

    # 3. Fetch recent AI chat conversations
    chats = (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == current_user.id)
        .order_by(ChatConversation.updated_at.desc())
        .all()
    )
    for chat in chats:
        msg_count = len(chat.messages) if chat.messages else 0
        activities.append({
            "id": f"chat_{chat.id}",
            "raw_time": chat.updated_at,
            "type": "ai_chat",
            "icon": "fas fa-robot",
            "icon_color": "text-success",
            "bg_color": "bg-success-subtle",
            "title": f"AI Chat: {chat.title}",
            "description": f"RAG Assistant session ({msg_count} messages)",
            "timestamp": format_relative_time(chat.updated_at),
        })

    # Sort combined activities by raw_time descending
    activities.sort(key=lambda x: x["raw_time"] if x["raw_time"] else datetime.datetime.min, reverse=True)

    # Return the complete combined activity stream; the dashboard controls the initial view limit.
    final_activities = []
    for item in activities:
        final_activities.append({
            "id": item["id"],
            "type": item["type"],
            "icon": item["icon"],
            "icon_color": item["icon_color"],
            "bg_color": item["bg_color"],
            "title": item["title"],
            "description": item["description"],
            "timestamp": item["timestamp"],
        })

    return final_activities


@router.get(
    "/chart-data",
    summary="Get real-time productivity weekly chart data",
    response_model=Dict[str, Any],
)
def get_chart_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns real daily breakdown of AI tasks and documents for past 7 days.
    """
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]

    labels = [d.strftime("%a") for d in days]
    docs_data = []
    ai_tasks_data = []

    for d in days:
        start_dt = datetime.datetime.combine(d, datetime.time.min)
        end_dt = datetime.datetime.combine(d, datetime.time.max)

        # Real documents for this day
        d_count = (
            db.query(Document)
            .filter(
                Document.user_id == current_user.id,
                Document.upload_date >= start_dt,
                Document.upload_date <= end_dt,
            )
            .count()
        )
        docs_data.append(d_count)

        # Real AI tasks for this day (Summaries + Chat Messages + Emails)
        sum_c = (
            db.query(DocumentSummary)
            .filter(
                DocumentSummary.user_id == current_user.id,
                DocumentSummary.created_at >= start_dt,
                DocumentSummary.created_at <= end_dt,
            )
            .count()
        )
        msg_c = (
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
        email_c = (
            db.query(Email)
            .filter(
                Email.user_id == current_user.id,
                Email.created_at >= start_dt,
                Email.created_at <= end_dt,
            )
            .count()
        )

        ai_tasks_data.append(sum_c + msg_c + email_c)

    return {
        "labels": labels,
        "ai_tasks": ai_tasks_data,
        "documents": docs_data,
    }
