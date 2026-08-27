import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Email, User, UserSettings
from ..schemas import (
    EmailGenerateRequest,
    EmailImproveRequest,
    EmailResponse,
    EmailSaveDraftRequest,
    EmailSendRequest,
)
from ..services.email_service import email_generator_service, smtp_sender_service

router = APIRouter(prefix="/api/emails", tags=["Email Generator & Sender"])


# ============================================
# 1. GENERATION & IMPROVEMENT
# ============================================

@router.post("/generate")
def generate_email(
    req: EmailGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not req.purpose or not req.purpose.strip():
        raise HTTPException(status_code=400, detail="Please enter an email purpose or description.")

    user_name = current_user.full_name or "User"
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    tone = req.tone
    if settings and req.tone == "Professional":
        tone = settings.default_email_tone
    result = email_generator_service.generate_email(
        purpose=req.purpose.strip(),
        recipient_name=req.recipient_name.strip() if req.recipient_name else "",
        recipient_email=req.recipient_email.strip() if req.recipient_email else "",
        tone=tone,
        length=req.length,
        user_name=user_name,
    )
    return result


@router.post("/improve")
def improve_email(
    req: EmailImproveRequest,
    current_user: User = Depends(get_current_user),
):
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Email content cannot be empty.")

    user_name = current_user.full_name or "User"
    result = email_generator_service.improve_email(
        subject=req.subject.strip(),
        content=req.content.strip(),
        action=req.action,
        user_name=user_name,
    )
    return result


# ============================================
# 2. DRAFT & SENDING VIA CENTRAL SMTP
# ============================================

@router.post("/draft", response_model=EmailResponse)
def save_or_update_draft(
    req: EmailSaveDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not req.recipient_email or "@" not in req.recipient_email:
        raise HTTPException(status_code=400, detail="Please provide a valid recipient email address.")
    if not req.subject or not req.subject.strip():
        raise HTTPException(status_code=400, detail="Please enter an email subject line.")
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Email content cannot be empty.")

    user_name = current_user.full_name or "User"

    email_record = None
    if req.id:
        email_record = (
            db.query(Email)
            .filter(Email.id == req.id, Email.user_id == current_user.id)
            .first()
        )

    if not email_record:
        email_record = Email(
            user_id=current_user.id,
            user_name=user_name,
            recipient_name=req.recipient_name.strip() if req.recipient_name else "",
            recipient_email=req.recipient_email.strip(),
            subject=req.subject.strip(),
            content=req.content.strip(),
            tone=req.tone or "Professional",
            length=req.length or "Medium",
            status="draft",
            created_at=datetime.datetime.utcnow(),
        )
        db.add(email_record)
    else:
        email_record.user_name = user_name
        email_record.recipient_name = req.recipient_name.strip() if req.recipient_name else ""
        email_record.recipient_email = req.recipient_email.strip()
        email_record.subject = req.subject.strip()
        email_record.content = req.content.strip()
        email_record.tone = req.tone or email_record.tone
        email_record.length = req.length or email_record.length
        email_record.status = "draft"

    db.commit()
    db.refresh(email_record)
    return email_record


@router.post("/send", response_model=EmailResponse)
def send_email(
    req: EmailSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipient_email = req.recipient_email.strip() if req.recipient_email else ""
    if not recipient_email or "@" not in recipient_email or "." not in recipient_email:
        raise HTTPException(status_code=400, detail="Please provide a valid recipient email address.")
    if not req.subject or not req.subject.strip():
        raise HTTPException(status_code=400, detail="Email subject line cannot be empty.")
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Email content cannot be empty.")

    user_name = current_user.full_name or "User"

    # 1. Get existing record or create new
    email_record = None
    if req.id:
        email_record = (
            db.query(Email)
            .filter(Email.id == req.id, Email.user_id == current_user.id)
            .first()
        )

    if not email_record:
        email_record = Email(
            user_id=current_user.id,
            user_name=user_name,
            recipient_name=req.recipient_name.strip() if req.recipient_name else "",
            recipient_email=recipient_email,
            subject=req.subject.strip(),
            content=req.content.strip(),
            status="sending",
            created_at=datetime.datetime.utcnow(),
        )
        db.add(email_record)
    else:
        email_record.user_name = user_name
        email_record.recipient_name = req.recipient_name.strip() if req.recipient_name else ""
        email_record.recipient_email = recipient_email
        email_record.subject = req.subject.strip()
        email_record.content = req.content.strip()
        email_record.status = "sending"

    db.commit()
    db.refresh(email_record)

    # 2. Execute email sending via central backend SMTP account
    send_result = smtp_sender_service.send_email(
        recipient_email=recipient_email,
        subject=req.subject.strip(),
        content=req.content.strip(),
        recipient_name=req.recipient_name.strip() if req.recipient_name else "",
        user_name=user_name,
    )

    if send_result.get("success"):
        email_record.status = "sent"
        email_record.sent_at = datetime.datetime.utcnow()
        email_record.error_message = None
    else:
        email_record.status = "failed"
        email_record.error_message = send_result.get("error", "SMTP send failed.")

    db.commit()
    db.refresh(email_record)

    if not send_result.get("success"):
        raise HTTPException(status_code=500, detail=send_result.get("error", "Email sending failed."))

    return email_record


# ============================================
# 3. HISTORY MANAGEMENT (PER-USER JWT SCOPED)
# ============================================

@router.get("", response_model=List[EmailResponse])
def list_emails(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    emails = (
        db.query(Email)
        .filter(Email.user_id == current_user.id)
        .order_by(Email.created_at.desc())
        .all()
    )
    return emails


@router.get("/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email_record = (
        db.query(Email)
        .filter(Email.id == email_id, Email.user_id == current_user.id)
        .first()
    )
    if not email_record:
        raise HTTPException(status_code=404, detail="Email record not found.")
    return email_record


@router.delete("/{email_id}")
def delete_email(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email_record = (
        db.query(Email)
        .filter(Email.id == email_id, Email.user_id == current_user.id)
        .first()
    )
    if not email_record:
        raise HTTPException(status_code=404, detail="Email record not found.")

    db.delete(email_record)
    db.commit()
    return {"message": "Email record deleted successfully."}
