import datetime
import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PasswordResetToken, User
from ..schemas import (
    ChangePasswordRequest,
    ResetOtpResponse,
    ResetPasswordRequest,
    VerifyResetOtpRequest,
    UserRegister,
    UserLogin,
    ForgotPasswordRequest,
    Token,
    UserResponse,
    MessageResponse,
)
from ..security import hash_password, verify_password
from ..auth import create_access_token, decode_access_token, get_current_user
from ..services.email_service import smtp_sender_service
from ..services.admin_automation_service import execute_welcome_automation

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


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
        role="user"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

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
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "id": user.id,
            "role": user.role,
            "name": user.full_name
        }
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link"
)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    _issue_reset_otp(request.email, db)
    return MessageResponse(
        message="If an account exists with this email, a reset code has been sent."
    )


@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    _issue_reset_otp(request.email, db)
    return MessageResponse(
        message="If an account exists with this email, a reset code has been sent."
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

    submitted_hash = hashlib.sha256(request.otp.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(submitted_hash, token.otp_hash):
        token.attempts += 1
        if token.attempts >= 5:
            token.used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

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
        or reset_token.used or not reset_token.verified_at
        or reset_token.expires_at <= now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset session.")

    user.password_hash = hash_password(request.new_password)
    reset_token.used = True
    db.commit()
    return MessageResponse(message="Password reset successfully. Please log in with your new password.")


def _issue_reset_otp(email: str, db: Session) -> None:
    """Create and send an OTP without revealing whether the account exists."""
    now = datetime.datetime.utcnow()
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
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
        otp_hash=hashlib.sha256(otp.encode("utf-8")).hexdigest(),
        expires_at=now + datetime.timedelta(minutes=10),
        created_at=now,
    )
    db.add(token)
    db.commit()

    result = smtp_sender_service.send_password_reset_otp(user.email, otp)
    if not result.get("success"):
        print(f"Password reset email delivery failed for user {user.id}: {result.get('error')}")


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
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return MessageResponse(message="Password changed successfully.")
