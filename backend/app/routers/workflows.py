import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Workflow, WorkflowRun
from ..services.workflow_service import workflow_engine_service

router = APIRouter(prefix="/api/workflows", tags=["Workflow Automation"])


# ============================================
# PYDANTIC SCHEMAS FOR WORKFLOWS
# ============================================

class WorkflowActionSchema(BaseModel):
    action_type: str  # generate_summary, send_email, generate_notification, run_analysis
    config: Optional[Dict[str, Any]] = {}


class WorkflowCreateRequest(BaseModel):
    name: str
    trigger_type: str  # document_uploaded, document_processed, email_generated, manual_trigger
    actions: List[WorkflowActionSchema]
    is_active: Optional[bool] = True


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    actions: Optional[List[WorkflowActionSchema]] = None
    is_active: Optional[bool] = None


class WorkflowRunResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class WorkflowResponse(BaseModel):
    id: int
    user_id: int
    name: str
    trigger_type: str
    actions: List[Dict[str, Any]]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# ============================================
# WORKFLOW MANAGEMENT ENDPOINTS
# ============================================

@router.get("", response_model=List[WorkflowResponse])
def list_workflows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflows = (
        db.query(Workflow)
        .filter(Workflow.user_id == current_user.id)
        .order_by(Workflow.created_at.desc())
        .all()
    )
    return workflows


@router.post("", response_model=WorkflowResponse)
def create_workflow(
    req: WorkflowCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Workflow name cannot be empty.")
    if not req.trigger_type:
        raise HTTPException(status_code=400, detail="Please select a workflow trigger type.")
    if not req.actions or len(req.actions) == 0:
        raise HTTPException(status_code=400, detail="Please add at least one action step to the workflow.")

    actions_list = [a.dict() for a in req.actions]

    wf = Workflow(
        user_id=current_user.id,
        name=req.name.strip(),
        trigger_type=req.trigger_type,
        actions=actions_list,
        is_active=req.is_active if req.is_active is not None else True,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return wf


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: int,
    req: WorkflowUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    if req.name is not None and req.name.strip():
        wf.name = req.name.strip()
    if req.trigger_type is not None:
        wf.trigger_type = req.trigger_type
    if req.actions is not None:
        wf.actions = [a.dict() for a in req.actions]
    if req.is_active is not None:
        wf.is_active = req.is_active

    wf.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(wf)
    return wf


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    db.delete(wf)
    db.commit()
    return {"message": "Workflow deleted successfully."}


@router.post("/{workflow_id}/toggle", response_model=WorkflowResponse)
def toggle_workflow_status(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    wf.is_active = not wf.is_active
    wf.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(wf)
    return wf


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
def run_workflow_manually(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    run = workflow_engine_service.execute_workflow(
        workflow=wf,
        trigger_payload={"manual": True, "document_title": "Manual Workflow Execution"},
        db=db,
    )
    return run


class AiWorkflowPromptRequest(BaseModel):
    prompt: str


@router.post("/generate-from-ai")
def generate_workflow_from_ai_prompt(
    req: AiWorkflowPromptRequest,
    current_user: User = Depends(get_current_user),
):
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Please describe the workflow you want to create.")

    from ..services.summarization_service import SummarizationService
    import json
    summarizer = SummarizationService()

    ai_prompt = (
        "You are IntelliBusiness AI Workflow Architect.\n"
        "Convert the user's natural language request into a valid JSON workflow object.\n\n"
        "AVAILABLE TRIGGERS:\n"
        "- 'document_uploaded' (Triggered when user uploads a file/invoice/document)\n"
        "- 'document_processed' (Triggered when document is processed)\n"
        "- 'email_generated' (Triggered when email is created)\n"
        "- 'manual_trigger' (Triggered manually by user)\n\n"
        "AVAILABLE ACTIONS:\n"
        "- 'generate_summary' (AI Summary)\n"
        "- 'run_analysis' (AI Business Data Analysis)\n"
        "- 'send_email' (Send Email Alert / Report)\n"
        "- 'generate_notification' (Generate Notification Log)\n\n"
        "USER REQUEST: " + req.prompt.strip() + "\n\n"
        "Return ONLY a valid JSON object with this exact structure:\n"
        "{\n"
        '  "name": "Descriptive Workflow Name",\n'
        '  "trigger_type": "document_uploaded",\n'
        '  "actions": [\n'
        '    {"action_type": "run_analysis", "config": {}},\n'
        '    {"action_type": "send_email", "config": {"recipient_email": ""}}\n'
        '  ]\n'
        "}\n"
        "Do not wrap in markdown block quotes. Output strictly valid JSON."
    )

    try:
        raw_res = summarizer._call_gemini_api(ai_prompt).strip()
        if "```json" in raw_res:
            raw_res = raw_res.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_res:
            raw_res = raw_res.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw_res)
        return parsed
    except Exception as exc:
        return {
            "name": "AI Generated Routine",
            "trigger_type": "document_uploaded",
            "actions": [
                {"action_type": "run_analysis", "config": {}},
                {"action_type": "generate_summary", "config": {}},
                {"action_type": "send_email", "config": {}},
            ],
        }


# ============================================
# WORKFLOW EXECUTION HISTORY ENDPOINTS
# ============================================

@router.get("/runs/history", response_model=List[WorkflowRunResponse])
def list_workflow_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.user_id == current_user.id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(50)
        .all()
    )
    return runs


@router.get("/{workflow_id}/runs", response_model=List[WorkflowRunResponse])
def list_runs_for_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workflow_id == workflow_id, WorkflowRun.user_id == current_user.id)
        .order_by(WorkflowRun.started_at.desc())
        .all()
    )
    return runs

