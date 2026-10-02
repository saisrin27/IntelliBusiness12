import json
import logging
from typing import Any, Dict, Optional

from .gmail_service import gmail_service
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
            return {"subject": subject, "content": full_content}
        except Exception as exc:
            logging.warning("Email generation fallback triggered: %s", exc)
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
            return {"subject": subject, "content": content}

    def improve_email(self, subject: str, content: str, action: str, user_name: str = "User") -> Dict[str, str]:
        action_instructions = {
            "make_professional": "Rewrite to be strictly professional and polished.",
            "make_shorter": "Make it concise and direct while preserving the key message.",
            "make_friendlier": "Make it warm and approachable.",
            "fix_grammar": "Fix grammar and wording without changing meaning.",
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
            '  "content": "Updated full email content including greeting, body, and closing signature"\n'
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
            return {"subject": parsed.get("subject", subject).strip(), "content": updated_content}
        except Exception as exc:
            logging.warning("Email improvement fallback triggered: %s", exc)
            return {"subject": subject, "content": content}


email_generator_service = EmailGeneratorService()
# Gmail is the only supported sender for application mail.
GmailApiSender = gmail_service.__class__
email_sender_service = gmail_service
gmail_oauth_email_service = gmail_service
