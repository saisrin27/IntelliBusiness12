from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, example="Jane Doe")
    company_name: str = Field(..., min_length=2, max_length=255, example="Acme Corp")
    email: EmailStr = Field(..., example="jane.doe@example.com")
    password: str = Field(..., min_length=6, max_length=128, example="Secret123!")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., example="jane.doe@example.com")
    password: str = Field(..., example="Secret123!")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., example="jane.doe@example.com")


class UserResponse(BaseModel):
    id: int
    full_name: str
    company_name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    email: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


# ============================================
# DOCUMENT SCHEMAS (PHASE 4)
# ============================================

class DocumentResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    original_filename: str
    file_path: str
    file_type: str
    file_size: int
    upload_date: datetime
    processing_status: str
    processing_error: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentStatsResponse(BaseModel):
    total: int
    processing: int
    completed: int
    failed: int


class DocumentListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[DocumentResponse]


class DocumentSummaryResponse(BaseModel):
    document_id: int
    filename: str
    executive_summary: str
    key_points: List[str]
    important_information: List[str]
    action_items: List[str]
    keywords: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSummaryCreateResponse(BaseModel):
    message: str
    document_id: int
    filename: str
    executive_summary: str
    key_points: List[str]
    important_information: List[str]
    action_items: List[str]
    keywords: List[str]
    created_at: datetime

    class Config:
        from_attributes = True
