import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from ..models import AdminAutomation, AdminAutomationRun, User
from .email_service import smtp_sender_service

WELCOME_TRIGGER = "new_user_registered"
DEFAULT_WELCOME_SUBJECT = "Welcome to IntelliBusiness!"
DEFAULT_WELCOME_TEMPLATE = """Hello {user_name},

Welcome to IntelliBusiness!

Thank you for registering with us. We’re excited to have you on board and hope IntelliBusiness helps you simplify your business tasks using AI and automation.

Start exploring your documents, AI assistant, analytics, emails, and workflows.

Regards,
The IntelliBusiness Team"""


def get_or_create_welcome_automation(db: Session) -> AdminAutomation:
    automation = db.query(AdminAutomation).filter(
        AdminAutomation.trigger_type == WELCOME_TRIGGER
    ).first()
    if automation:
        return automation

    automation = AdminAutomation(
        name="Welcome Email",
        trigger_type=WELCOME_TRIGGER,
        is_active=False,
        email_subject=DEFAULT_WELCOME_SUBJECT,
        email_template=DEFAULT_WELCOME_TEMPLATE,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(automation)
    db.commit()
    db.refresh(automation)
    return automation


def render_welcome_email(template: str, user: User) -> str:
    values = {
        "user_name": user.full_name,
        "email": user.email,
        "company_name": user.company_name or "",
    }
    content = template
    for key, value in values.items():
        content = content.replace("{" + key + "}", value)
    return content


def execute_welcome_automation(
    db: Session,
    user: User,
    automation: Optional[AdminAutomation] = None,
) -> Optional[AdminAutomationRun]:
    automation = automation or db.query(AdminAutomation).filter(
        AdminAutomation.trigger_type == WELCOME_TRIGGER,
        AdminAutomation.is_active == True,
    ).first()
    if not automation:
        return None

    content = render_welcome_email(automation.email_template, user)
    run = AdminAutomationRun(
        automation_id=automation.id,
        triggered_user_id=user.id,
        status="sending",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = smtp_sender_service.send_email(
            recipient_email=user.email,
            subject=automation.email_subject,
            content=content,
            recipient_name=user.full_name,
            user_name="The IntelliBusiness Team",
        )
        if result.get("success"):
            run.status = "success"
            run.result = "Welcome email sent successfully."
            run.error_message = None
        else:
            run.status = "failed"
            run.result = "Welcome email delivery failed."
            run.error_message = result.get("error", "SMTP send failed.")
    except Exception as exc:
        run.status = "failed"
        run.result = "Welcome email delivery failed."
        run.error_message = str(exc)

    db.commit()
    db.refresh(run)
    return run
