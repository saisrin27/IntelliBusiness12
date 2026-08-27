import datetime
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ..models import History, User, Workflow, WorkflowRun
from .business_analytics_service import business_analytics_service
from .document_processor import extract_text_by_file_type
from .email_service import smtp_sender_service
from .summarization_service import SummarizationService


class WorkflowEngineService:
    """Service handling execution of multi-step business workflows and event triggers."""

    def __init__(self):
        self.summarizer = SummarizationService()

    @staticmethod
    def _output_text(output: Any) -> str:
        if isinstance(output, str):
            return output.strip()
        if output is None:
            return ""
        return json.dumps(output, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _select_email_body(context: Dict[str, Any]) -> tuple[str, str]:
        candidates = (
            ("last_output", context.get("last_output")),
            ("business_analysis", context.get("business_analysis")),
            ("analysis_result", context.get("analysis_result")),
            ("summary", context.get("summary")),
        )
        for source, value in candidates:
            text = WorkflowEngineService._output_text(value)
            if text:
                return text, source
        return "", "none"

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
            "document_id": trigger_payload.get("document_id"),
            "document_name": trigger_payload.get("original_filename", trigger_payload.get("document_title", "Document")),
            "file_type": trigger_payload.get("file_type", ""),
            "trigger_type": workflow.trigger_type,
            "user_name": user_name,
            "document_title": trigger_payload.get("original_filename", trigger_payload.get("document_title", "Document")),
            "document_text": trigger_payload.get("document_text", trigger_payload.get("text", "")),
            "summary": trigger_payload.get("summary", ""),
            "business_analysis": trigger_payload.get("business_analysis"),
            "analysis_result": trigger_payload.get("analysis_result"),
            "email_body": None,
            "last_output": None,
        }

        file_path = trigger_payload.get("file_path")
        if not context["document_text"] and file_path:
            file_type = context["file_type"] or str(file_path).rsplit(".", 1)[-1].lower()
            context["file_type"] = file_type
            try:
                context["document_text"] = extract_text_by_file_type(file_path, file_type)
            except ValueError:
                # Tabular analytics can consume the source file directly.
                context["document_text"] = ""

        try:
            idx = 0
            while idx < len(actions):
                action_item = actions[idx]
                idx += 1
                action_type = action_item.get("action_type", "")
                action_config = action_item.get("config", {})

                step_output = {}

                # Action 1: Generate AI Summary
                if action_type == "condition":
                    field_value = context.get(action_config.get("field", "last_output"))
                    expected_value = action_config.get("value")
                    operator = action_config.get("operator", "not_empty")
                    if operator == "equals":
                        condition_met = field_value == expected_value
                    elif operator == "contains":
                        condition_met = str(expected_value).casefold() in self._output_text(field_value).casefold()
                    else:
                        condition_met = bool(self._output_text(field_value))
                    branch_key = "yes_actions" if condition_met else "no_actions"
                    branch_actions = action_config.get(branch_key, [])
                    if isinstance(branch_actions, list):
                        actions[idx:idx] = branch_actions
                    step_output = {
                        "step": idx,
                        "action_type": action_type,
                        "status": "success",
                        "branch": "yes" if condition_met else "no",
                    }
                elif action_type == "generate_summary":
                    text_to_summarize = context["document_text"] or context["summary"]
                    if not text_to_summarize:
                        raise ValueError("No document content available to summarize.")
                    prompt = (
                        f"Summarize the following business document content concisely:\n\n{text_to_summarize}\n\n"
                        "Provide 3-5 bullet points highlighting the core facts."
                    )
                    summary_text = self.summarizer._call_gemini_api(prompt).strip()
                    context["summary"] = summary_text
                    context["last_output"] = summary_text
                    context["email_body"] = summary_text
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
                    
                    email_body, body_source = self._select_email_body(context)
                    print(
                        f"[WorkflowEngineService] Email context keys={list(context.keys())}; "
                        f"previous_step_type={step_results[-1].get('action_type') if step_results else None}; "
                        f"previous_output={email_body[:500]!r}; selected_source={body_source}"
                    )
                    if not email_body:
                        raise ValueError("No valid workflow result available to send by email.")
                    
                    if user_name not in email_body:
                        email_body += f"\n\nRegards,\n{user_name}"
                    context["email_body"] = email_body
                    context["last_output"] = email_body

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
                        "body_source": body_source,
                        "output": email_body,
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
                    context["last_output"] = step_output

                # Action 4: Run AI Analysis
                elif action_type == "run_analysis":
                    analysis_text = context["document_text"] or context["summary"]
                    if not analysis_text:
                        raise ValueError("No document content available for analysis.")
                    file_type = context.get("file_type", "")
                    if file_path and file_type in {"csv", "xlsx", "xls"}:
                        analysis_result = business_analytics_service.parse_and_analyze_data(
                            file_path, context["document_name"]
                        )
                    else:
                        prompt = (
                            f"Perform a strategic AI business analysis on this content:\n\n{analysis_text}\n\n"
                            "Identify: 1) Key Risks, 2) Opportunities, 3) Actionable Recommendations."
                        )
                        analysis_result = self.summarizer._call_gemini_api(prompt).strip()
                    context["analysis_result"] = analysis_result
                    context["business_analysis"] = analysis_result
                    context["last_output"] = analysis_result
                    context["email_body"] = analysis_result
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
            run.result = {"steps": step_results, "context": context}
            run.error_message = None

        except Exception as exc:
            run.status = "failed"
            run.completed_at = datetime.datetime.utcnow()
            run.result = {"steps": step_results, "context": context}
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
