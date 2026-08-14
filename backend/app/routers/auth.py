from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    UserRegister,
    UserLogin,
    ForgotPasswordRequest,
    Token,
    UserResponse,
    MessageResponse,
)
from ..security import hash_password, verify_password
from ..auth import create_access_token, get_current_user

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
    """
    Dummy forgot-password endpoint:
    - Accepts user email.
    - Returns a generic success response without exposing whether the email exists.
    """
    return MessageResponse(
        message="If an account with this email exists, a password reset link has been sent to your inbox."
    )


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
