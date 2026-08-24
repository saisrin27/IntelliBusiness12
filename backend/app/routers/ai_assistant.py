import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import ChatConversation, ChatMessage, User
from ..schemas import ChatConversationResponse, ChatMessageResponse, ChatRequest, ChatResponse
from ..services.rag_service import rag_service

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message_text = req.message.strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="Please enter a question.")

    # 1. Get existing or create new conversation
    conversation = None
    if req.conversation_id:
        conversation = (
            db.query(ChatConversation)
            .filter(ChatConversation.id == req.conversation_id, ChatConversation.user_id == current_user.id)
            .first()
        )

    if not conversation:
        title = message_text[:35] + ("..." if len(message_text) > 35 else "")
        conversation = ChatConversation(
            user_id=current_user.id,
            title=title,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 2. Retrieve recent conversation history (last 10 messages)
    existing_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    history = [{"role": msg.role, "content": msg.content} for msg in existing_messages[-10:]]

    # 3. Generate RAG Answer across ALL documents belonging to current_user
    rag_result = rag_service.generate_rag_answer(
        user_id=current_user.id,
        question=message_text,
        conversation_history=history,
        db=db,
    )

    # 4. Save User question and Assistant answer to chat history
    user_msg = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=message_text,
        sources=None,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(user_msg)

    assistant_msg = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=rag_result["answer"],
        sources=rag_result["sources"],
        created_at=datetime.datetime.utcnow(),
    )
    db.add(assistant_msg)

    conversation.updated_at = datetime.datetime.utcnow()
    db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        message=rag_result["answer"],
        sources=rag_result["sources"],
    )


@router.get("/conversations", response_model=List[ChatConversationResponse])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == current_user.id)
        .order_by(ChatConversation.updated_at.desc())
        .all()
    )
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ChatConversationResponse)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(ChatConversation)
        .filter(ChatConversation.id == conversation_id, ChatConversation.user_id == current_user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(ChatConversation)
        .filter(ChatConversation.id == conversation_id, ChatConversation.user_id == current_user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully."}
