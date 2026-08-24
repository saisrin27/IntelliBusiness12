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


# ============================================
# AI ASSISTANT SCHEMAS
# ============================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[int] = None


class ChatSource(BaseModel):
    document_id: int
    filename: str


class ChatMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[List[ChatSource]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ChatMessageResponse]] = None

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    conversation_id: int
    title: str
    message: str
    sources: List[ChatSource]


# ============================================
# AI EMAIL GENERATOR SCHEMAS
# ============================================

class EmailGenerateRequest(BaseModel):
    recipient_name: Optional[str] = ""
    recipient_email: Optional[str] = ""
    purpose: str = Field(..., min_length=3)
    tone: str = "Professional"  # Professional, Friendly, Formal, Apologetic
    length: str = "Medium"      # Short, Medium, Detailed


class EmailImproveRequest(BaseModel):
    subject: str
    content: str
    action: str  # make_professional, make_shorter, make_friendlier, fix_grammar


class EmailSaveDraftRequest(BaseModel):
    id: Optional[int] = None
    recipient_name: Optional[str] = ""
    recipient_email: str
    subject: str
    content: str
    tone: Optional[str] = "Professional"
    length: Optional[str] = "Medium"


class EmailSendRequest(BaseModel):
    id: Optional[int] = None
    recipient_name: Optional[str] = ""
    recipient_email: str
    subject: str
    content: str


class EmailResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = ""
    recipient_name: Optional[str] = ""
    recipient_email: str
    subject: str
    content: str
    tone: Optional[str] = ""
    length: Optional[str] = ""
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True



