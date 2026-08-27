import base64
import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, UserSettings
from ..schemas import (
    ChangePasswordRequest,
    MessageResponse,
    SettingsPreferencesResponse,
    SettingsPreferencesUpdate,
    SettingsProfileResponse,
    SettingsProfileUpdate,
)
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/settings", tags=["Settings"])
FIXED_ADMIN_EMAIL = "intellibusiness12@gmail.com"
MAX_PROFILE_PICTURE_BYTES = 2 * 1024 * 1024


def get_or_create_settings(user: User, db: Session) -> UserSettings:
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def validate_profile_picture(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if not re.match(r"^data:image/(png|jpeg|jpg|webp);base64,", value, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Profile picture must be a PNG, JPEG, or WebP image.")
    try:
        encoded = value.split(",", 1)[1]
        if len(base64.b64decode(encoded, validate=True)) > MAX_PROFILE_PICTURE_BYTES:
            raise HTTPException(status_code=400, detail="Profile picture must be 2 MB or smaller.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Profile picture is invalid.") from exc
    return value


@router.get("/profile", response_model=SettingsProfileResponse)
def get_profile_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_or_create_settings(current_user, db)
    return {
        "full_name": current_user.full_name,
        "company_name": current_user.company_name,
        "email": current_user.email,
        "role": current_user.role,
        "profile_picture": settings.profile_picture,
    }


@router.put("/profile", response_model=SettingsProfileResponse)
def update_profile_settings(
    request: SettingsProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.full_name = request.full_name.strip()
    current_user.company_name = request.company_name.strip()
    settings = get_or_create_settings(current_user, db)
    settings.profile_picture = validate_profile_picture(request.profile_picture)
    settings.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return {
        "full_name": current_user.full_name,
        "company_name": current_user.company_name,
        "email": current_user.email,
        "role": current_user.role,
        "profile_picture": settings.profile_picture,
    }


@router.get("/preferences", response_model=SettingsPreferencesResponse)
def get_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_or_create_settings(current_user, db)


@router.put("/preferences", response_model=SettingsPreferencesResponse)
def update_preferences(
    request: SettingsPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(current_user, db)
    for field, value in request.model_dump().items():
        setattr(settings, field, value)
    settings.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings


@router.put("/password", response_model=MessageResponse)
def update_password(
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


@router.delete("/account", response_model=MessageResponse)
def delete_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.email.lower() == FIXED_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="The fixed administrator account cannot be deleted.")
    db.delete(current_user)
    db.commit()
    return MessageResponse(message="Your account and associated data have been deleted.")
