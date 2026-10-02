import datetime
import base64
import json
import hashlib
import hmac
import logging
import os
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import EmailVerificationToken, PasswordResetToken, User
from ..schemas import (
    ChangePasswordRequest,
    ResetOtpResponse,
    ResetPasswordRequest,
    VerifyResetOtpRequest,
    UserRegister,
    UserLogin,
    ForgotPasswordRequest,
    EmailVerificationRequest,
    Token,
    UserResponse,
    MessageResponse,
)
from ..security import hash_password, verify_password
from ..auth import SECRET_KEY, create_access_token, decode_access_token, get_current_user
from ..services.email_service import email_sender_service
from ..services.admin_automation_service import execute_welcome_automation

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GOOGLE_STATE_COOKIE = "intellibusiness_google_state"
GOOGLE_VERIFIER_COOKIE = "intellibusiness_google_verifier"


def _google_oauth_config(request: Request):
    backend_dir = Path(__file__).resolve().parents[2]
    credentials_candidates = (
        backend_dir / "credentials.json",
        backend_dir / "credentials.json.json",
    )
    credentials_path = next((path for path in credentials_candidates if path.is_file()), None)

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if (not client_id or not client_secret) and not os.getenv("RENDER"):
        for path in credentials_candidates:
            if not path.is_file():
                continue
            try:
                credentials_data = json.loads(path.read_text(encoding="utf-8"))
                web_credentials = credentials_data.get("web", {})
                client_id = client_id or str(web_credentials.get("client_id", "")).strip()
                client_secret = client_secret or str(web_credentials.get("client_secret", "")).strip()
            except (OSError, ValueError, TypeError) as exc:
                logging.error("Local Google credentials could not be loaded from %s (%s).", path, type(exc).__name__)
            if client_id and client_secret:
                break

    logging.info("Google credentials file found: %s", bool(credentials_path))
    logging.info("Google Client ID configured: %s", bool(client_id))
    logging.info("Google Client Secret configured: %s", bool(client_secret))
    if client_id:
        logging.info("Google Client ID prefix: %s", client_id[:12] + "..." if len(client_id) > 12 else client_id)
    if not client_id or not client_secret:
        logging.error("Google sign-in configuration is incomplete.")
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if not redirect_uri:
        redirect_uri = str(request.url_for("google_auth_callback"))
    logging.info("Google redirect URI selected: %s", redirect_uri)

    parsed_redirect = urlsplit(redirect_uri)
    is_local_redirect = parsed_redirect.hostname in {"localhost", "127.0.0.1"}
    if is_local_redirect:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    else:
        os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
    if (
        parsed_redirect.scheme not in {"http", "https"}
        or not parsed_redirect.netloc
        or parsed_redirect.username
        or parsed_redirect.password
        or parsed_redirect.query
        or parsed_redirect.fragment
        or parsed_redirect.path != "/api/auth/google/callback"
        or (parsed_redirect.scheme != "https" and not is_local_redirect)
    ):
        logging.error(
            "Google sign-in redirect URI is invalid. scheme=%s netloc=%s path=%s",
            parsed_redirect.scheme,
            parsed_redirect.netloc,
            parsed_redirect.path,
        )
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return client_id, redirect_uri, client_config


def _google_flow(redirect_uri: str, client_config: dict, state: str, verifier: str) -> Flow:
    return Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
        state=state,
        code_verifier=verifier,
        autogenerate_code_verifier=False,
    )


def _frontend_origin() -> str:
    configured = os.getenv("FRONTEND_BASE_URL", "").strip().rstrip("/")
    allowed = {
        origin.strip().rstrip("/")
        for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
        if origin.strip() and origin.strip() != "*"
    }
    if not configured:
        configured = next((origin for origin in allowed if origin.startswith("https://")), "")
        if not configured and not os.getenv("RENDER"):
            configured = "http://127.0.0.1:3000"
    parsed = urlsplit(configured)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    is_local_origin = parsed.hostname in {"localhost", "127.0.0.1"}
    if (
        not origin
        or parsed.path not in {"", "/"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or origin not in allowed
        or (parsed.scheme != "https" and not is_local_origin)
    ):
        logging.error("Frontend redirect origin is missing or not allowlisted.")
        raise HTTPException(status_code=503, detail="Authentication redirect is not configured.")
    return origin


def _google_result_redirect(error: Optional[str] = None, access_token: Optional[str] = None) -> RedirectResponse:
    frontend = _frontend_origin()
    if access_token:
        location = f"{frontend}/auth-callback.html#access_token={quote(access_token, safe='')}"
    else:
        location = f"{frontend}/login.html?google_error={quote(error or 'failed', safe='')}"
    response = RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(GOOGLE_STATE_COOKIE, path="/api/auth/google")
    response.delete_cookie(GOOGLE_VERIFIER_COOKIE, path="/api/auth/google")
    return response


def _issue_email_verification(user: User, db: Session) -> bool:
    now = datetime.datetime.utcnow()
    latest = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    if latest and (now - latest.created_at).total_seconds() < 60:
        return False

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used == False,
    ).update({"used": True}, synchronize_session=False)

    token_value = secrets.token_urlsafe(32)
    token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hashlib.sha256(token_value.encode("utf-8")).hexdigest(),
        expires_at=now + datetime.timedelta(hours=24),
        created_at=now,
    )
    db.add(token)
    db.commit()

    verification_url = f"{_frontend_origin()}/verify-email.html#token={quote(token_value, safe='')}"
    result = email_sender_service.send_verification_email(user.email, verification_url, user_id=user.id, db=db)
    if not result.get("success"):
        logging.error("Verification email delivery failed for user %s.", user.id)
        return False
    return True


def _create_user_access_token(user: User) -> str:
    return create_access_token(
        data={
            "sub": user.email,
            "id": user.id,
            "role": user.role,
            "name": user.full_name,
        }
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new user:
    - Validates Full Name, Company Name, Email, and Password.
    - Rejects duplicate email addresses.
    - Hashes password using bcrypt.
    - Saves user to MySQL database.
    """
    # Normalize email to lower case
    email_clean = user_in.email.strip().lower()

    # Check duplicate email
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # Hash password
    hashed_pwd = hash_password(user_in.password)

    # Create new User model instance
    new_user = User(
        full_name=user_in.full_name.strip(),
        company_name=user_in.company_name.strip(),
        email=email_clean,
        password_hash=hashed_pwd,
        email_verified=False,
        role="user"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        _issue_email_verification(new_user, db)
    except Exception as exc:
        db.rollback()
        logging.error("Verification email setup failed for user %s (%s).", new_user.id, type(exc).__name__)

    # Trigger admin automations (non-blocking) - e.g., welcome email
    try:
        execute_welcome_automation(db, new_user)
    except Exception as exc:
        # Log the error but don't fail the registration process
        print(f"[Auth] Admin automation failed for user {new_user.id}: {exc}")

    return new_user


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate user and return JWT token"
)
def login_user(user_in: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user:
    - Validates email and password against database.
    - Generates and returns JWT Access Token on success.
    """
    email_clean = user_in.email.strip().lower()

    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not user.password_hash or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email address before signing in.",
        )

    # Generate JWT token
    access_token = _create_user_access_token(user)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.get("/google", summary="Start Google sign-in")
def start_google_sign_in(request: Request):
    _, redirect_uri, client_config = _google_oauth_config(request)
    logging.info("Starting Google OAuth flow with redirect_uri=%s", redirect_uri)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    flow = _google_flow(redirect_uri, client_config, state, verifier)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    authorization_url, _ = flow.authorization_url(
        prompt="select_account",
        access_type="online",
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    response = RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)
    secure_cookie = request.url.scheme == "https" or bool(os.getenv("RENDER"))
    for cookie_name, cookie_value in (
        (GOOGLE_STATE_COOKIE, state),
        (GOOGLE_VERIFIER_COOKIE, verifier),
    ):
        response.set_cookie(
            cookie_name,
            cookie_value,
            max_age=600,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/api/auth/google",
        )
    return response


@router.get("/google/callback", name="google_auth_callback", summary="Complete Google sign-in")
def google_auth_callback(request: Request, db: Session = Depends(get_db)):
    google_error = request.query_params.get("error")
    google_error_description = request.query_params.get("error_description", "")
    if google_error:
        logging.warning(
            "Google OAuth callback returned error=%s description=%s",
            google_error,
            google_error_description[:200] if google_error_description else "no description",
        )
        return _google_result_redirect("cancelled")

    state = request.query_params.get("state", "")
    state_cookie = request.cookies.get(GOOGLE_STATE_COOKIE, "")
    verifier = request.cookies.get(GOOGLE_VERIFIER_COOKIE, "")
    if not state or not state_cookie or not hmac.compare_digest(state, state_cookie) or not verifier:
        logging.warning("Google OAuth callback state validation failed. state_present=%s state_match=%s verifier_present=%s",
                        bool(state), hmac.compare_digest(state, state_cookie) if state and state_cookie else False, bool(verifier))
        return _google_result_redirect("state")

    code = request.query_params.get("code")
    if not code:
        logging.warning("Google OAuth callback did not include an authorization code.")
        return _google_result_redirect("failed")

    try:
        client_id, redirect_uri, client_config = _google_oauth_config(request)
        flow = _google_flow(redirect_uri, client_config, state, verifier)
        logging.info("Exchanging Google authorization code for tokens using callback=%s", redirect_uri)
        flow.fetch_token(authorization_response=str(request.url))
        try:
            identity = google_id_token.verify_oauth2_token(
                flow.credentials.id_token,
                GoogleRequest(),
                audience=client_id,
            )
        except Exception as exc:
            logging.exception("Google ID token verification failed.")
            return _google_result_redirect("failed")

        email = str(identity.get("email") or "").strip().lower()
        google_sub = str(identity.get("sub") or "").strip()
        email_verified = identity.get("email_verified") is True or str(
            identity.get("email_verified", "")
        ).lower() == "true"
        if not email or not google_sub or not email_verified:
            logging.warning(
                "Google sign-in returned incomplete identity: email_present=%s google_sub_present=%s email_verified=%s",
                bool(email),
                bool(google_sub),
                email_verified,
            )
            return _google_result_redirect("unverified")

        user = db.query(User).filter(User.google_sub == google_sub).first()
        is_new_user = False
        if user is None:
            user = db.query(User).filter(User.email == email).first()
            if user is not None and user.google_sub and user.google_sub != google_sub:
                return _google_result_redirect("account_conflict")
            if user is None:
                is_new_user = True
        if user is not None:
            if not user.google_sub:
                user.google_sub = google_sub
            user.email_verified = True
        else:
            user = User(
                full_name=(str(identity.get("name") or email.split("@", 1)[0]).strip()[:255]),
                company_name="",
                email=email,
                password_hash=None,
                google_sub=google_sub,
                email_verified=True,
                role="user",
            )
            db.add(user)

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(
                (User.google_sub == google_sub) | (User.email == email)
            ).first()
            if not user or (user.google_sub and user.google_sub != google_sub):
                return _google_result_redirect("account_conflict")
            if user.google_sub != google_sub and user.email.strip().lower() != email:
                return _google_result_redirect("account_conflict")
            if not user.google_sub:
                user.google_sub = google_sub
            if not user.email_verified:
                user.email_verified = True
            if user.google_sub == google_sub:
                db.commit()
                db.refresh(user)

        if is_new_user:
            try:
                execute_welcome_automation(db, user)
            except Exception as exc:
                logging.error("Google user welcome automation failed (%s).", type(exc).__name__)

        return _google_result_redirect(access_token=_create_user_access_token(user))
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.exception("Google sign-in failed during callback processing.")
        return _google_result_redirect("failed")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(request: EmailVerificationRequest, db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    token_hash = hashlib.sha256(request.token.encode("utf-8")).hexdigest()
    verification_token = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used == False,
            EmailVerificationToken.expires_at > now,
        )
        .first()
    )
    if not verification_token:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired.")

    user = db.query(User).filter(User.id == verification_token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired.")
    verification_token.used = True
    user.email_verified = True
    db.commit()

    try:
        email_sender_service.send_email_verified_confirmation(user.email, user_id=user.id, db=db)
    except Exception as exc:
        logging.error("Post-verification notification failed for user %s (%s).", user.id, type(exc).__name__)
    return MessageResponse(message="Email verified. You can now sign in.")


@router.post("/send-verification-again", response_model=MessageResponse)
def send_verification_again(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email.strip().lower()).first()
    if user and user.password_hash and not user.email_verified:
        try:
            _issue_email_verification(user, db)
        except Exception as exc:
            db.rollback()
            logging.error("Verification email request failed for user %s (%s).", user.id, type(exc).__name__)
    return MessageResponse(
        message=(
            "If a password-based account needs verification, a link has been sent. "
            "Google sign-in accounts do not need email verification."
        )
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link"
)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    _issue_reset_otp(request.email, db)
    return MessageResponse(
        message=(
            "If a password-based account exists with this email, a reset code has been sent. "
            "For Google-only accounts, use Sign in with Google."
        )
    )


@router.post("/send-otp-again", response_model=MessageResponse)
def send_otp_again(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    _issue_reset_otp(request.email, db)
    return MessageResponse(
        message=(
            "If a password-based account exists with this email, a reset code has been sent. "
            "For Google-only accounts, use Sign in with Google."
        )
    )


@router.post("/verify-reset-otp", response_model=ResetOtpResponse)
def verify_reset_otp(request: VerifyResetOtpRequest, db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    token = None
    if user:
        token = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > now,
            )
            .order_by(PasswordResetToken.created_at.desc())
            .first()
        )

    if not token or token.attempts >= 5:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

    submitted_hash = hmac.new(
        SECRET_KEY.encode("utf-8"), request.otp.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    legacy_submitted_hash = hashlib.sha256(request.otp.encode("utf-8")).hexdigest()
    if not (
        hmac.compare_digest(submitted_hash, token.otp_hash)
        or hmac.compare_digest(legacy_submitted_hash, token.otp_hash)
    ):
        token.attempts += 1
        if token.attempts >= 5:
            token.used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

    token.otp_hash = submitted_hash
    token.verified_at = now
    db.commit()
    reset_token = create_access_token(
        {"sub": user.email, "reset_token_id": token.id, "token_type": "password_reset"},
        expires_delta=datetime.timedelta(minutes=10),
    )
    return ResetOtpResponse(message="Code verified. You may now set a new password.", reset_token=reset_token)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match.")

    try:
        payload = decode_access_token(request.reset_token)
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset session.") from exc

    if payload.get("token_type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset session.")

    token_id = payload.get("reset_token_id")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.id == token_id).first()
    now = datetime.datetime.utcnow()
    if (
        not user or not reset_token or reset_token.user_id != user.id
        or not user.password_hash or reset_token.used or not reset_token.verified_at
        or reset_token.expires_at <= now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset session.")

    user.password_hash = hash_password(request.new_password)
    reset_token.used = True
    db.commit()
    try:
        result = email_sender_service.send_password_reset_confirmation(user.email, user_id=user.id, db=db)
        if not result.get("success"):
            logging.error("Password reset confirmation delivery failed for user %s.", user.id)
    except Exception as exc:
        logging.error("Password reset confirmation failed for user %s (%s).", user.id, type(exc).__name__)
    return MessageResponse(message="Password reset successfully. Please log in with your new password.")


def _issue_reset_otp(email: str, db: Session) -> None:
    """Create and send an OTP without revealing whether the account exists."""
    now = datetime.datetime.utcnow()
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not user.password_hash:
        return

    latest = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if latest and (now - latest.created_at).total_seconds() < 60:
        return

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,
    ).update({"used": True}, synchronize_session=False)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    token = PasswordResetToken(
        user_id=user.id,
        otp_hash=hmac.new(
            SECRET_KEY.encode("utf-8"), otp.encode("utf-8"), hashlib.sha256
        ).hexdigest(),
        expires_at=now + datetime.timedelta(minutes=10),
        created_at=now,
    )
    db.add(token)
    db.commit()

    result = email_sender_service.send_password_reset_otp(user.email, otp, user_id=user.id, db=db)
    if not result.get("success"):
        logging.error("Password reset email delivery failed for user %s.", user.id)


@router.get(
    "/profile",
    response_model=UserResponse,
    summary="Get authenticated user profile"
)
def get_profile(current_user: User = Depends(get_current_user)):
    """
    Protected Route:
    - Requires valid JWT Authorization Bearer header.
    - Returns details of the logged-in user.
    """
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match.")
    if not current_user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="This account uses Google sign-in. Use Google to access your account.",
        )
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    try:
        result = email_sender_service.send_password_reset_confirmation(current_user.email, user_id=current_user.id, db=db)
        if not result.get("success"):
            logging.error("Password change confirmation delivery failed for user %s.", current_user.id)
    except Exception as exc:
        logging.error("Password change confirmation failed for user %s (%s).", current_user.id, type(exc).__name__)
    return MessageResponse(message="Password changed successfully.")
