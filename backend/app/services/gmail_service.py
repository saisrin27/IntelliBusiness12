import base64
import json
import logging
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .email_templates import render_email_template

CENTRAL_GMAIL_SENDER = "intellibusiness12@gmail.com"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_IDENTITY_SCOPES = ("openid", "https://www.googleapis.com/auth/userinfo.email")
GMAIL_AUTH_SCOPES = [GMAIL_SEND_SCOPE, *GMAIL_IDENTITY_SCOPES]


class GmailApiService:
    """Server-side Gmail API sender for the central IntelliBusiness mail account."""

    @staticmethod
    def _get_credentials() -> Credentials:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "").strip()

        if not client_id or not client_secret or not refresh_token:
            raise RuntimeError("Gmail OAuth credentials are not configured on the backend.")

        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=GMAIL_AUTH_SCOPES,
        )

    def _ensure_valid_credentials(self, credentials: Credentials) -> Credentials:
        if credentials.expired or not credentials.token:
            credentials.refresh(GoogleRequest())
        return credentials

    @staticmethod
    def _email_is_valid(value: str) -> bool:
        return bool(value and "@" in value)

    @staticmethod
    def _log_api_error(error: HttpError) -> None:
        status = getattr(error.resp, "status", "unknown")
        reasons = []
        try:
            payload = json.loads(error.content.decode("utf-8"))
            details = payload.get("error", {})
            reasons = [
                item["reason"]
                for item in details.get("errors", [])
                if isinstance(item, dict) and isinstance(item.get("reason"), str)
            ]
            if not reasons and isinstance(details.get("status"), str):
                reasons = [details["status"]]
        except (AttributeError, TypeError, ValueError):
            pass
        logging.error(
            "Gmail API authorization/send error: HTTP %s; reason=%s",
            status,
            ",".join(reasons) if reasons else "unavailable",
        )

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        content: str,
        recipient_name: Optional[str] = "",
        user_name: str = "IntelliBusiness User",
        attachment_path: Optional[str] = None,
        html_content: Optional[str] = None,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not self._email_is_valid(recipient_email):
            return {"success": False, "error": "Invalid recipient email address."}

        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "").strip()
        credential_configured = bool(client_id and client_secret)
        logging.info(
            "Gmail credential configuration found: %s; Gmail refresh token available: %s",
            "yes" if credential_configured else "no",
            "yes" if refresh_token else "no",
        )
        logging.info("Configured central Gmail sender email: %s", CENTRAL_GMAIL_SENDER)
        if not credential_configured or not refresh_token:
            missing = []
            if not client_id:
                missing.append("GOOGLE_CLIENT_ID")
            if not client_secret:
                missing.append("GOOGLE_CLIENT_SECRET")
            if not refresh_token:
                missing.append("GMAIL_REFRESH_TOKEN")
            logging.error("Gmail sender configuration is incomplete; missing: %s", ", ".join(missing))
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }

        try:
            credentials = self._ensure_valid_credentials(self._get_credentials())
        except RefreshError as exc:
            error_code = next(
                (code for code in ("invalid_grant", "invalid_client", "unauthorized_client", "access_denied")
                 if code in str(exc).lower()),
                "unknown",
            )
            logging.error(
                "Gmail OAuth authorization error during token refresh: %s. "
                "Check whether the refresh token was revoked or expired and whether it matches the configured OAuth client.",
                error_code,
            )
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }
        except Exception as exc:
            logging.error("Gmail OAuth credential initialization failed (%s).", type(exc).__name__)
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }

        try:
            identity_response = AuthorizedSession(credentials).get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                timeout=10,
            )
            if identity_response.status_code != 200:
                logging.error(
                    "Gmail authorized-account lookup failed: HTTP %s.",
                    identity_response.status_code,
                )
                return {
                    "success": False,
                    "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
                }
            authorized_email = str(identity_response.json().get("email", "")).strip().lower()
        except Exception as exc:
            logging.error("Gmail authorized-account lookup failed (%s).", type(exc).__name__)
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }

        logging.info("Authorized sender email: %s", authorized_email or "unavailable")
        if authorized_email != CENTRAL_GMAIL_SENDER.lower():
            logging.error(
                "Gmail OAuth account mismatch: expected central sender %s; authorized sender %s.",
                CENTRAL_GMAIL_SENDER,
                authorized_email or "unavailable",
            )
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }

        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            logging.info("Gmail API client initialized: yes")
        except Exception as exc:
            logging.error("Gmail API client initialized: no (%s).", type(exc).__name__)
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }

        try:
            message = EmailMessage()
            message["To"] = recipient_email
            message["From"] = CENTRAL_GMAIL_SENDER
            message["Subject"] = subject

            if html_content:
                message.set_content(content)
                message.add_alternative(html_content, subtype="html")
            else:
                message.set_content(content)

            if attachment_path:
                attachment_file = Path(attachment_path)
                if not attachment_file.is_file():
                    return {"success": False, "error": "The requested email attachment was not found."}

                mime_type, _ = mimetypes.guess_type(attachment_file.name)
                maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
                with attachment_file.open("rb") as file_handle:
                    payload = file_handle.read()
                message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=attachment_file.name)

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            sent = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
            logging.info("Gmail API sent email from %s to %s, message_id=%s", CENTRAL_GMAIL_SENDER, recipient_email, sent.get("id"))
            return {"success": True, "error": None, "message_id": sent.get("id")}
        except HttpError as exc:
            self._log_api_error(exc)
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }
        except Exception as exc:
            logging.error("Central Gmail API email send failed (%s).", type(exc).__name__)
            return {
                "success": False,
                "error": "Email delivery failed. The central Gmail sender is not configured or is unavailable.",
            }

    def send_verification_email(
        self,
        recipient_email: str,
        verification_url: str,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
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
            user_id=user_id,
            db=db,
            html_content=render_email_template(
                title=subject,
                paragraphs=["Verify your email address to finish creating your account."],
                action_label="Verify email",
                action_url=verification_url,
                security_notice="This link expires in 24 hours. If you did not create this account, ignore this email.",
            ),
        )

    def send_email_verified_confirmation(
        self,
        recipient_email: str,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        subject = "Your IntelliBusiness email is verified"
        content = "Your email address has been verified. You can now sign in to IntelliBusiness."
        return self.send_email(
            recipient_email=recipient_email,
            subject=subject,
            content=content,
            user_name="IntelliBusiness Security",
            user_id=user_id,
            db=db,
            html_content=render_email_template(
                title=subject,
                paragraphs=["Your email address has been verified. You can now sign in to IntelliBusiness."],
            ),
        )

    def send_password_reset_otp(
        self,
        recipient_email: str,
        otp: str,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
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
            user_id=user_id,
            db=db,
            html_content=render_email_template(
                title=subject,
                paragraphs=["Use this one-time code to reset your password."],
                code=otp,
                security_notice="The code expires in 10 minutes. If you did not request this, ignore this email.",
            ),
        )

    def send_password_reset_confirmation(
        self,
        recipient_email: str,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
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
            user_id=user_id,
            db=db,
            html_content=render_email_template(
                title=subject,
                paragraphs=["Your IntelliBusiness password was changed successfully."],
                security_notice="If you did not make this change, contact support immediately.",
            ),
        )


gmail_service = GmailApiService()
