import datetime
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ..models import History, User, Workflow, WorkflowRun
from .email_service import smtp_sender_service
from .summarization_service import SummarizationService


class WorkflowEngineService:
    """Service handling execution of multi-step business workflows and event triggers."""

    def __init__(self):
        self.summarizer = SummarizationService()

    def execute_workflow(
        self,
        workflow: Workflow,
        trigger_payload: Optional[Dict[str, Any]] = None,
        db: Session = None,
    ) -> WorkflowRun:
        """Executes a workflow's action steps sequentially, logging the run status and outputs."""
        if not db:
            raise ValueError("Database session is required for workflow execution.")

        trigger_payload = trigger_payload or {}

        # 1. Create WorkflowRun entry with status 'running'
        run = WorkflowRun(
            workflow_id=workflow.id,
            user_id=workflow.user_id,
            status="running",
            started_at=datetime.datetime.utcnow(),
            result={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Get user details for signatures & sending
        user = db.query(User).filter(User.id == workflow.user_id).first()
        user_name = user.full_name if user else "IntelliBusiness User"

        actions = workflow.actions if isinstance(workflow.actions, list) else []
        step_results = []
        context = {
            "trigger_type": workflow.trigger_type,
            "user_name": user_name,
            "document_title": trigger_payload.get("original_filename", trigger_payload.get("document_title", "Document")),
            "document_text": trigger_payload.get("document_text", trigger_payload.get("text", "")),
            "summary": trigger_payload.get("summary", ""),
            "last_output": "",
        }

        try:
            for idx, action_item in enumerate(actions, start=1):
                action_type = action_item.get("action_type", "")
                action_config = action_item.get("config", {})

                step_output = {}

                # Action 1: Generate AI Summary
                if action_type == "generate_summary":
                    text_to_summarize = context["document_text"] or context["summary"] or context["document_title"]
                    prompt = (
                        f"Summarize the following business document content concisely:\n\n{text_to_summarize}\n\n"
                        "Provide 3-5 bullet points highlighting the core facts."
                    )
                    summary_text = self.summarizer._call_gemini_api(prompt).strip()
                    context["summary"] = summary_text
                    context["last_output"] = summary_text
                    step_output = {
                        "step": idx,
                        "action_type": action_type,
                        "status": "success",
                        "output": summary_text,
                    }

                # Action 2: Send Email
                elif action_type == "send_email":
                    recipient_email = action_config.get("recipient_email") or trigger_payload.get("recipient_email") or (user.email if user else "")
                    subject = action_config.get("subject") or f"Automated Workflow Alert: {workflow.name}"
                    
                    email_body = action_config.get("content") or context["last_output"] or context["summary"] or f"Workflow '{workflow.name}' completed successfully."
                    
                    if user_name not in email_body:
                        email_body += f"\n\nRegards,\n{user_name}"

                    send_res = smtp_sender_service.send_email(
                        recipient_email=recipient_email,
                        subject=subject,
                        content=email_body,
                        user_name=user_name,
                    )
                    
                    step_output = {
                        "step": idx,
                        "action_type": action_type,
                        "status": "success" if send_res.get("success") else "failed",
                        "recipient": recipient_email,
                        "subject": subject,
                        "error": send_res.get("error"),
                    }

                # Action 3: Generate Notification
                elif action_type == "generate_notification":
                    title = action_config.get("title") or f"Workflow Notification: {workflow.name}"
                    desc = action_config.get("message") or f"Workflow step executed for {context['document_title']}"
                    
                    history_entry = History(
                        user_id=workflow.user_id,
                        action_type="workflow_notification",
                        title=title,
                        description=desc,
                        created_at=datetime.datetime.utcnow(),
                    )
                    db.add(history_entry)
                    step_output = {
                        "step": idx,
                        "action_type": action_type,
                        "status": "success",
                        "notification_title": title,
                        "notification_desc": desc,
                    }

                # Action 4: Run AI Analysis
                elif action_type == "run_analysis":
                    analysis_text = context["document_text"] or context["summary"] or context["document_title"]
                    prompt = (
                        f"Perform a strategic AI business analysis on this content:\n\n{analysis_text}\n\n"
                        "Identify: 1) Key Risks, 2) Opportunities, 3) Actionable Recommendations."
                    )
                    analysis_result = self.summarizer._call_gemini_api(prompt).strip()
                    context["last_output"] = analysis_result
                    step_output = {
                        "step": idx,
                        "action_type": action_type,
                        "status": "success",
                        "output": analysis_result,
                    }

                else:
                    step_output = {
                        "step": idx,
                        "action_type": action_type,
                        "status": "skipped",
                        "message": f"Unknown action type '{action_type}'",
                    }

                step_results.append(step_output)

            # Workflow complete
            run.status = "completed"
            run.completed_at = datetime.datetime.utcnow()
            run.result = {"steps": step_results, "context": {"document_title": context["document_title"]}}
            run.error_message = None

        except Exception as exc:
            run.status = "failed"
            run.completed_at = datetime.datetime.utcnow()
            run.result = {"steps": step_results}
            run.error_message = f"Workflow execution error: {str(exc)}"

        db.commit()
        db.refresh(run)
        return run

    def trigger_event(self, user_id: int, trigger_type: str, payload: Dict[str, Any], db: Session) -> List[WorkflowRun]:
        """Automatically checks for active workflows for user_id matching trigger_type and executes them."""
        active_workflows = (
            db.query(Workflow)
            .filter(
                Workflow.user_id == user_id,
                Workflow.is_active == True,
                Workflow.trigger_type == trigger_type,
            )
            .all()
        )

        runs = []
        for wf in active_workflows:
            try:
                run = self.execute_workflow(workflow=wf, trigger_payload=payload, db=db)
                runs.append(run)
            except Exception as exc:
                print(f"[WorkflowEngineService] Error executing workflow {wf.id}: {exc}")

        return runs


workflow_engine_service = WorkflowEngineService()
