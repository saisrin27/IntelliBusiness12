import json
import os
import re
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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


class SMTPSenderService:
    """Service to send emails securely via one central IntelliBusiness backend SMTP account."""

    def _get_config(self):
        """Fetch fresh SMTP configuration from environment variables."""
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path, override=True)

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME", "").strip()
        # Remove spaces in case user pasted a Google App Password like 'abcd efgh ijkl mnop'
        smtp_password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_username or "intellibusiness@company.com").strip()
        return smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email


    def is_configured(self) -> bool:
        _, _, username, password, _ = self._get_config()
        return bool(username and password and username != "your_email@gmail.com")

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        content: str,
        recipient_name: Optional[str] = "",
        user_name: str = "IntelliBusiness User",
        attachment_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email to recipient using the central IntelliBusiness backend SMTP account."""
        if not recipient_email or "@" not in recipient_email:
            return {
                "success": False,
                "error": "Invalid recipient email address.",
            }

        smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email = self._get_config()

        if not smtp_username or not smtp_password or smtp_username == "your_email@gmail.com":
            return {
                "success": False,
                "error": "Backend SMTP is not configured yet. Please set SMTP_USERNAME and SMTP_PASSWORD (Google App Password) in your backend .env file.",
            }

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = f"IntelliBusiness Service <{smtp_from_email}>"
            msg["To"] = f"{recipient_name} <{recipient_email}>" if recipient_name else recipient_email
            msg["Reply-To"] = smtp_from_email

            # Attach plain text version
            text_part = MIMEText(content, "plain", "utf-8")
            msg.attach(text_part)

            # Convert newlines to HTML paragraphs for clean formatting
            html_content = content.replace("\n\n", "</p><p>").replace("\n", "<br>")
            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px;">
                        <p>{html_content}</p>
                    </div>
                    <div style="margin-top: 16px; font-size: 12px; color: #64748b; text-align: center;">
                        Sent via IntelliBusiness AI Email Assistant on behalf of {user_name}
                    </div>
                </body>
            </html>
            """
            html_part = MIMEText(html_body, "html", "utf-8")
            msg.attach(html_part)

            if attachment_path:
                attachment_file = Path(attachment_path)
                if not attachment_file.is_file():
                    return {"success": False, "error": "The requested email attachment was not found."}
                with attachment_file.open("rb") as file_handle:
                    attachment = MIMEBase("application", "pdf")
                    attachment.set_payload(file_handle.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment_file.name,
                )
                msg.attach(attachment)

            # Connect and send via SMTP with STARTTLS
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from_email, [recipient_email], msg.as_string())
            server.quit()

            return {"success": True, "error": None}
        except smtplib.SMTPAuthenticationError as exc:
            return {
                "success": False,
                "error": "SMTP Authentication Failed (535 Bad Credentials). If using Gmail, you MUST use a 16-character Google App Password (not your normal Gmail password). Enable 2-Step Verification on your Google Account and generate an App Password at https://myaccount.google.com/apppasswords.",
            }
        except smtplib.SMTPException as exc:
            return {
                "success": False,
                "error": f"SMTP Server error: {str(exc)}",
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Unable to send email: {str(exc)}",
            }

    def send_password_reset_otp(self, recipient_email: str, otp: str) -> Dict[str, Any]:
        """Send a reset code through the central backend mailbox."""
        return self.send_email(
            recipient_email=recipient_email,
            subject="IntelliBusiness Password Reset",
            content=(
                "Your password reset code is: " + otp +
                "\n\nThis code will expire in 10 minutes."
            ),
            user_name="IntelliBusiness Security",
        )



email_generator_service = EmailGeneratorService()
smtp_sender_service = SMTPSenderService()
