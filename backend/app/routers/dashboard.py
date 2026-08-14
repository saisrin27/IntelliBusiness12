from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from ..database import get_db
from ..models import User
from ..auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get(
    "/stats",
    summary="Get user dashboard statistics",
    response_model=Dict[str, int]
)
def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Protected Endpoint:
    Returns dashboard statistics for the authenticated user.
    If specific feature tables do not exist yet, default values are returned safely.
    """
    # Safe fallback values for Phase 3
    # In future phases, these will query the respective tables filtered by current_user.id
    return {
        "documents": 24,
        "ai_tasks": 156,
        "emails_generated": 42,
        "workflows": 8
    }


@router.get(
    "/recent-activity",
    summary="Get user recent activity timeline",
    response_model=List[Dict[str, Any]]
)
def get_recent_activity(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Protected Endpoint:
    Returns recent activities timeline for the authenticated user.
    """
    # Sample initial activity data for authenticated user context
    activities = [
        {
            "id": 1,
            "type": "document",
            "icon": "fas fa-file-pdf",
            "icon_color": "text-primary",
            "bg_color": "bg-primary-subtle",
            "title": "Quarterly_Financial_Report_Q2.pdf",
            "description": "Document analyzed & 14 key takeaways extracted by AI Assistant.",
            "timestamp": "2 hours ago"
        },
        {
            "id": 2,
            "type": "email",
            "icon": "fas fa-envelope-open-text",
            "icon_color": "text-purple",
            "bg_color": "bg-purple-subtle",
            "title": "Executive Email Drafted",
            "description": "Generated strategic partnership proposal email for Acme Corp.",
            "timestamp": "5 hours ago"
        },
        {
            "id": 3,
            "type": "ai_chat",
            "icon": "fas fa-robot",
            "icon_color": "text-success",
            "bg_color": "bg-success-subtle",
            "title": "Market Competitor Analysis Session",
            "description": "Completed 18 prompt queries with IntelliBusiness AI Assistant.",
            "timestamp": "Yesterday at 4:30 PM"
        },
        {
            "id": 4,
            "type": "workflow",
            "icon": "fas fa-network-wired",
            "icon_color": "text-warning",
            "bg_color": "bg-warning-subtle",
            "title": "Customer Onboarding Workflow",
            "description": "Automated workflow trigger executed successfully with 0 errors.",
            "timestamp": "2 days ago"
        }
    ]
    
    return activities
