import json
import os
import re
import resend
from typing import Any, Dict, Optional

from .summarization_service import SummarizationService


class EmailGeneratorService:
    """Service to generate and refine business emails using Gemini AI."""

    def __init__(self):
        self.summarizer = SummarizationService()

    def generate_email(
        self,
        purpose: str,
        recipient_name: Optional[str] = "",
        recipient_email: Optional[str] = "",
        tone: str = "Professional",
        length: str = "Medium",
        user_name: str = "User",
    ) -> Dict[str, str]:
        """Generate subject and structured email body based on user inputs."""
        name_str = f"to {recipient_name}" if recipient_name else ""
        user_signature = f"Regards,\n{user_name}"
        
        prompt = (
            "You are IntelliBusiness Email AI, an expert business communicator.\n\n"
            f"Write a high-quality email {name_str}.\n"
            f"- Sender Name: {user_name}\n"
            f"- Purpose/Description: {purpose}\n"
            f"- Tone: {tone}\n"
            f"- Length: {length}\n\n"
            "Return your response ONLY as a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "subject": "Clear, engaging email subject line",\n'
            '  "greeting": "Formal or appropriate greeting (e.g., Dear John, / Hi Sarah,)",\n'
            '  "body": "The main paragraphs of the email",\n'
            f'  "closing": "Regards,\\n{user_name}"\n'
            "}\n\n"
            "Do not wrap in markdown block quotes or extra text. Output strictly valid JSON."
        )

        try:
            raw_response = self.summarizer._call_gemini_api(prompt).strip()
            json_str = raw_response
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()

            parsed = json.loads(json_str)
            subject = parsed.get("subject", "Business Communication").strip()
            greeting = parsed.get("greeting", "Hello,").strip()
            body = parsed.get("body", "").strip()
            closing = parsed.get("closing", user_signature).strip()

            if user_name not in closing:
                closing = f"{closing}\n{user_name}"

            full_content = f"{greeting}\n\n{body}\n\n{closing}"
            return {
                "subject": subject,
                "content": full_content,
            }
        except Exception as exc:
            print(f"[EmailGeneratorService] JSON generation fallback: {exc}")
            fallback_prompt = (
                f"Write a {tone} business email {name_str} with length {length}.\n"
                f"Purpose: {purpose}\n"
                f"Include closing signature: 'Regards,\\n{user_name}'\n"
                "Format: Line 1 must be 'Subject: <subject>'. Followed by blank line and email content."
            )
            raw = self.summarizer._call_gemini_api(fallback_prompt).strip()
            subject = "Business Communication"
            content = raw
            if raw.lower().startswith("subject:"):
                lines = raw.split("\n")
                subject = lines[0].replace("Subject:", "").replace("subject:", "").strip()
                content = "\n".join(lines[1:]).strip()

            if user_name not in content:
                content += f"\n\nRegards,\n{user_name}"

            return {
                "subject": subject,
                "content": content,
            }

    def improve_email(self, subject: str, content: str, action: str, user_name: str = "User") -> Dict[str, str]:
        """Perform AI quick improvements on an existing subject and content."""
        action_instructions = {
            "make_professional": "Rewrite the email to be strictly professional, executive-level, polished, and authoritative.",
            "make_shorter": "Make the email concise, brief, and direct while preserving all essential information.",
            "make_friendlier": "Rewrite the email to be warm, friendly, positive, and approachable.",
            "fix_grammar": "Fix all spelling, grammar, punctuation, and phrasing errors without altering the core tone or meaning.",
        }

        instruction = action_instructions.get(action, "Improve clarity and phrasing.")

        prompt = (
            "You are IntelliBusiness Email AI.\n"
            f"Task: {instruction}\n\n"
            f"Sender Name: {user_name}\n"
            f"CURRENT SUBJECT: {subject}\n"
            f"CURRENT CONTENT:\n{content}\n\n"
            "Return your response ONLY as a valid JSON object:\n"
            "{\n"
            '  "subject": "Updated subject line",\n'
            '  "content": "Updated full email content including greeting, body, and closing signature (Regards,\\n[Sender Name])"\n'
            "}\n"
            "Output strictly valid JSON."
        )

        try:
            raw_response = self.summarizer._call_gemini_api(prompt).strip()
            json_str = raw_response
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()

            parsed = json.loads(json_str)
            updated_content = parsed.get("content", content).strip()
            if user_name not in updated_content:
                updated_content += f"\n\nRegards,\n{user_name}"

            return {
                "subject": parsed.get("subject", subject).strip(),
                "content": updated_content,
            }
        except Exception as exc:
            print(f"[EmailGeneratorService] Improve fallback: {exc}")
            return {
                "subject": subject,
                "content": content,
            }


from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent.parent.parent
dotenv_path = root_dir / ".env"


class ResendEmailService:
    """Service to send emails using the Resend API."""

    def _get_config(self):
        api_key = os.getenv("RESEND_API_KEY", "").strip()

        from_email = os.getenv(
            "RESEND_FROM_EMAIL",
            "onboarding@resend.dev"
        ).strip()

        return api_key, from_email

    def is_configured(self) -> bool:
        api_key, _ = self._get_config()
        return bool(api_key)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        content: str,
        recipient_name: Optional[str] = "",
        user_name: str = "IntelliBusiness User",
        attachment_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        if not recipient_email or "@" not in recipient_email:
            return {
                "success": False,
                "error": "Invalid recipient email address.",
            }

        api_key, from_email = self._get_config()

        if not api_key:
            return {
                "success": False,
                "error": "Resend API is not configured. Please add RESEND_API_KEY.",
            }

        try:
            resend.api_key = api_key

            html_content = (
                content
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n\n", "</p><p>")
                .replace("\n", "<br>")
            )

            params = {
                "from": f"IntelliBusiness <{from_email}>",
                "to": [recipient_email],
                "subject": subject,
                "text": content,
                "html": f"""
                <html>
                    <body style="
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    ">
                        <div style="
                            background: #ffffff;
                            border: 1px solid #e2e8f0;
                            border-radius: 8px;
                            padding: 24px;
                        ">
                            <p>{html_content}</p>
                        </div>

                        <div style="
                            margin-top: 16px;
                            font-size: 12px;
                            color: #64748b;
                            text-align: center;
                        ">
                            Sent via IntelliBusiness AI Email Assistant
                        </div>
                    </body>
                </html>
                """,
            }

            if attachment_path:
                attachment_file = Path(attachment_path)

                if not attachment_file.is_file():
                    return {
                        "success": False,
                        "error": "The requested email attachment was not found.",
                    }

                with attachment_file.open("rb") as file_handle:
                    params["attachments"] = [
                        {
                            "filename": attachment_file.name,
                            "content": list(file_handle.read()),
                        }
                    ]

            response = resend.Emails.send(params)

            print(f"[Resend] Email sent successfully: {response}")

            return {
                "success": True,
                "error": None,
            }

        except Exception as exc:
            print(f"[Resend] Email sending error: {exc}")

            return {
                "success": False,
                "error": f"Unable to send email: {str(exc)}",
            }

    def send_password_reset_otp(
        self,
        recipient_email: str,
        otp: str
    ) -> Dict[str, Any]:

        return self.send_email(
            recipient_email=recipient_email,
            subject="IntelliBusiness Password Reset",
            content=(
                f"Your password reset code is: {otp}"
                "\n\n"
                "This code will expire in 10 minutes."
                "\n\n"
                "If you did not request a password reset, please ignore this email."
            ),
            user_name="IntelliBusiness Security",
        )


email_generator_service = EmailGeneratorService()
smtp_sender_service =  ResendEmailService()
