import json
import logging
import os
import re
import resend
from typing import Any, Dict, Optional

from .summarization_service import SummarizationService
from .email_templates import render_email_template


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
    """Central email sender backed by the Resend production API."""

    def _get_config(self):
        api_key = os.getenv("RESEND_API_KEY", "").strip()
        from_email = (
            os.getenv("RESEND_FROM_EMAIL")
            or os.getenv("MAIL_FROM")
            or os.getenv("SMTP_FROM_EMAIL", "")
        ).strip()
        from_name = os.getenv("MAIL_FROM_NAME", "IntelliBusiness").strip()
        return api_key, from_email, from_name

    def is_configured(self) -> bool:
        api_key, from_email, _ = self._get_config()
        return bool(api_key and from_email)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        content: str,
        recipient_name: Optional[str] = "",
        user_name: str = "IntelliBusiness User",
        attachment_path: Optional[str] = None,
        html_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not recipient_email or "@" not in recipient_email:
            return {"success": False, "error": "Invalid recipient email address."}

        api_key, from_email, from_name = self._get_config()
        if not api_key or not from_email:
            logging.error("Email delivery is not configured.")
            return {"success": False, "error": "Email delivery is not configured."}

        try:
            resend.api_key = api_key
            params = {
                "from": f"{from_name} <{from_email}>",
                "to": [recipient_email],
                "subject": subject,
                "text": content,
                "html": html_content or render_email_template(
                    title=subject,
                    paragraphs=content.split("\n\n") or [content],
                ),
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
                        {"filename": attachment_file.name, "content": list(file_handle.read())}
                    ]

            resend.Emails.send(params)
            logging.info("Email accepted by provider for delivery.")
            return {"success": True, "error": None}
        except Exception as exc:
            logging.error("Email provider request failed (%s).", type(exc).__name__)
            return {
                "success": False,
                "error": "Email delivery failed. Please try again later.",
            }

    def send_verification_email(
        self,
        recipient_email: str,
        verification_url: str,
    ) -> Dict[str, Any]:
        subject = "Verify your IntelliBusiness email"
        content = (
            "Verify your email address using the link below. The link expires in 24 hours.\n\n"
            f"{verification_url}\n\n"
            "If you did not create this account, you can ignore this message."
        )
        return self.send_email(
            recipient_email=recipient_email,
            subject=subject,
            content=content,
            user_name="IntelliBusiness Security",
            html_content=render_email_template(
                title=subject,
                paragraphs=["Verify your email address to finish creating your account."],
                action_label="Verify email",
                action_url=verification_url,
                security_notice="This link expires in 24 hours. If you did not create this account, ignore this email.",
            ),
        )

    def send_email_verified_confirmation(self, recipient_email: str) -> Dict[str, Any]:
        subject = "Your IntelliBusiness email is verified"
        content = "Your email address has been verified. You can now sign in to IntelliBusiness."
        return self.send_email(
            recipient_email=recipient_email,
            subject=subject,
            content=content,
            user_name="IntelliBusiness Security",
            html_content=render_email_template(
                title=subject,
                paragraphs=["Your email address has been verified. You can now sign in to IntelliBusiness."],
            ),
        )

    def send_password_reset_otp(
        self,
        recipient_email: str,
        otp: str,
    ) -> Dict[str, Any]:
        subject = "Your IntelliBusiness password reset code"
        content = (
            f"Your password reset code is {otp}. It expires in 10 minutes.\n\n"
            "If you did not request a password reset, ignore this email."
        )
        return self.send_email(
            recipient_email=recipient_email,
            subject=subject,
            content=content,
            user_name="IntelliBusiness Security",
            html_content=render_email_template(
                title=subject,
                paragraphs=["Use this one-time code to reset your password."],
                code=otp,
                security_notice="The code expires in 10 minutes. If you did not request this, ignore this email.",
            ),
        )

    def send_password_reset_confirmation(self, recipient_email: str) -> Dict[str, Any]:
        subject = "Your IntelliBusiness password was changed"
        content = (
            "Your IntelliBusiness password was changed successfully.\n\n"
            "If you did not make this change, contact support immediately."
        )
        return self.send_email(
            recipient_email=recipient_email,
            subject=subject,
            content=content,
            user_name="IntelliBusiness Security",
            html_content=render_email_template(
                title=subject,
                paragraphs=["Your IntelliBusiness password was changed successfully."],
                security_notice="If you did not make this change, contact support immediately.",
            ),
        )


email_generator_service = EmailGeneratorService()
resend_email_service = ResendEmailService()

# Keep old imports working
smtp_sender_service = resend_email_service
