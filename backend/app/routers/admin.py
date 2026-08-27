import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_admin
from ..database import get_db
from ..models import (
    ChatConversation,
    ChatMessage,
    Document,
    DocumentSummary,
    Email,
    User,
    Workflow,
    WorkflowRun,
    AdminAutomation,
    AdminAutomationRun,
)
from ..schemas import AdminAutomationResponse, AdminAutomationRunResponse, AdminAutomationTestRequest, AdminAutomationUpdate
from ..services.admin_automation_service import execute_welcome_automation, get_or_create_welcome_automation, WELCOME_TRIGGER
from ..services.email_service import smtp_sender_service

router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard"])

AI_ACTION_TYPES = {"generate_summary", "run_analysis", "send_email"}


@router.get("/automations", response_model=List[AdminAutomationResponse])
def list_admin_automations(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    get_or_create_welcome_automation(db)
    return db.query(AdminAutomation).order_by(AdminAutomation.created_at.asc()).all()


@router.put("/automations/{automation_id}", response_model=AdminAutomationResponse)
def update_admin_automation(
    automation_id: int,
    request: AdminAutomationUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    automation = db.query(AdminAutomation).filter(AdminAutomation.id == automation_id).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Admin automation not found.")
    if automation.trigger_type != WELCOME_TRIGGER:
        raise HTTPException(status_code=400, detail="This automation trigger is not available yet.")
    automation.is_active = request.is_active
    automation.email_subject = request.email_subject.strip()
    automation.email_template = request.email_template.strip()
    automation.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(automation)
    return automation


@router.post("/automations/{automation_id}/test")
def test_admin_automation(
    automation_id: int,
    request: AdminAutomationTestRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    automation = db.query(AdminAutomation).filter(AdminAutomation.id == automation_id).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Admin automation not found.")
    if automation.trigger_type != WELCOME_TRIGGER:
        raise HTTPException(status_code=400, detail="This automation trigger is not available yet.")

    result = smtp_sender_service.send_email(
        recipient_email=request.recipient_email,
        subject=automation.email_subject,
        content=automation.email_template.replace("{user_name}", current_admin.full_name).replace(
            "{email}", request.recipient_email
        ).replace("{company_name}", current_admin.company_name or ""),
        recipient_name=current_admin.full_name,
        user_name="The IntelliBusiness Team",
    )
    run = AdminAutomationRun(
        automation_id=automation.id,
        triggered_user_id=current_admin.id,
        status="success" if result.get("success") else "failed",
        result="Test email sent successfully." if result.get("success") else "Test email delivery failed.",
        error_message=None if result.get("success") else result.get("error", "SMTP send failed."),
        created_at=datetime.datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Test email sending failed."))
    return {"message": "Test email sent successfully.", "run_id": run.id}


@router.get("/automations/runs", response_model=List[AdminAutomationRunResponse])
def list_admin_automation_runs(
    automation_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AdminAutomationRun)
    if automation_id:
        query = query.filter(AdminAutomationRun.automation_id == automation_id)
    return query.order_by(AdminAutomationRun.created_at.desc()).limit(limit).all()


def date_window(days: int = 30):
    today = datetime.date.today()
    dates = [today - datetime.timedelta(days=index) for index in range(days - 1, -1, -1)]
    return dates, [date.strftime("%b %d") for date in dates]


def active_user_ids(db: Session, start: datetime.datetime) -> set[int]:
    ids: set[int] = set()
    for query in (
        db.query(Document.user_id).filter(Document.upload_date >= start),
        db.query(DocumentSummary.user_id).filter(DocumentSummary.created_at >= start),
        db.query(Email.user_id).filter(Email.created_at >= start),
        db.query(WorkflowRun.user_id).filter(WorkflowRun.started_at >= start),
        db.query(ChatConversation.user_id).join(ChatMessage).filter(ChatMessage.created_at >= start),
    ):
        ids.update(row[0] for row in query.distinct().all())
    return ids


def ai_usage_counts(db: Session) -> Dict[str, int]:
    summaries = db.query(DocumentSummary).count()
    chat_queries = (
        db.query(ChatMessage)
        .join(ChatConversation)
        .filter(ChatMessage.role == "user")
        .count()
    )
    emails = db.query(Email).count()
    workflow_ai_actions = 0
    for actions, in db.query(Workflow.actions).all():
        if isinstance(actions, list):
            workflow_ai_actions += sum(
                1 for action in actions
                if isinstance(action, dict) and action.get("action_type") in AI_ACTION_TYPES
            )
    return {
        "document_summaries": summaries,
        "chat_queries": chat_queries,
        "email_generation": emails,
        "workflow_ai_actions": workflow_ai_actions,
    }


@router.get("/overview")
def get_admin_overview(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    now = datetime.datetime.utcnow()
    active_ids = active_user_ids(db, now - datetime.timedelta(days=30))
    workflows = db.query(Workflow)
    runs = db.query(WorkflowRun)
    ai_counts = ai_usage_counts(db)
    ai_total = sum(ai_counts.values())
    tracked_events = (
        ai_total
        + db.query(Document).count()
        + db.query(Email).count()
        + db.query(WorkflowRun).count()
    )

    return {
        "total_users": db.query(User).count(),
        "total_active_users": len(active_ids),
        "total_workflows": workflows.count(),
        "currently_running_workflows": runs.filter(WorkflowRun.status == "running").count(),
        "completed_workflows": runs.filter(WorkflowRun.status == "completed").count(),
        "failed_workflows": runs.filter(WorkflowRun.status == "failed").count(),
        "total_ai_usage": ai_total,
        "ai_usage_percentage": round((ai_total / tracked_events) * 100, 2) if tracked_events else 0,
        "ai_usage_breakdown": ai_counts,
    }


@router.get("/users")
def get_admin_users(
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (User.full_name.ilike(term))
            | (User.email.ilike(term))
            | (User.company_name.ilike(term))
        )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    active_ids = active_user_ids(db, datetime.datetime.utcnow() - datetime.timedelta(days=30))
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "company_name": user.company_name,
                "created_at": user.created_at,
                "status": "Active" if user.id in active_ids else "Inactive",
            }
            for user in users
        ],
    }


@router.get("/analytics")
def get_admin_analytics(
    days: int = Query(default=30, ge=7, le=90),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    dates, labels = date_window(days)
    user_growth = []
    ai_usage = []
    workflow_activity = []

    for date in dates:
        start = datetime.datetime.combine(date, datetime.time.min)
        end = datetime.datetime.combine(date, datetime.time.max)
        user_growth.append(db.query(User).filter(User.created_at >= start, User.created_at <= end).count())
        ai_usage.append(
            db.query(DocumentSummary).filter(DocumentSummary.created_at >= start, DocumentSummary.created_at <= end).count()
            + db.query(ChatMessage).filter(ChatMessage.role == "user", ChatMessage.created_at >= start, ChatMessage.created_at <= end).count()
            + db.query(Email).filter(Email.created_at >= start, Email.created_at <= end).count()
        )
        workflow_activity.append(
            db.query(WorkflowRun).filter(WorkflowRun.started_at >= start, WorkflowRun.started_at <= end).count()
        )

    return {
        "labels": labels,
        "user_growth": user_growth,
        "ai_usage_over_time": ai_usage,
        "workflow_activity": workflow_activity,
        "workflow_status_distribution": {
            status: db.query(WorkflowRun).filter(WorkflowRun.status == status).count()
            for status in ("pending", "running", "completed", "failed")
        },
    }


@router.get("/workflows")
def get_admin_workflows(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "status_distribution": {
            status: db.query(WorkflowRun).filter(WorkflowRun.status == status).count()
            for status in ("pending", "running", "completed", "failed")
        },
        "active_workflows": db.query(Workflow).filter(Workflow.is_active == True).count(),
        "total_runs": db.query(WorkflowRun).count(),
    }
