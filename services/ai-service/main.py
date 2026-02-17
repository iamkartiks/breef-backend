"""AI Service - Paper chat functionality."""
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from typing import List
import openai
from datetime import datetime

import sys
from pathlib import Path
import importlib.util

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.database import get_db
from shared.config import settings
from shared.models import ChatRequest, ChatResponse, Conversation, ChatMessage, ErrorResponse

# Import get_current_user from user-service (handles hyphenated directory name)
def load_get_current_user():
    """Load get_current_user function from user-service."""
    backend_dir = Path(__file__).parent.parent.parent
    user_service_path = backend_dir / "services" / "user-service" / "main.py"
    
    spec = importlib.util.spec_from_file_location("user_service_main", user_service_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load user-service from {user_service_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_current_user

get_current_user = load_get_current_user()

router = APIRouter()


def get_ai_client():
    """Get AI client based on configuration."""
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        return openai.OpenAI(api_key=settings.openai_api_key)
    elif settings.ai_provider == "grok":
        # Grok API integration would go here
        raise NotImplementedError("Grok API integration not yet implemented")
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_paper(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Send a message to AI about a paper."""
    try:
        # Get or create conversation
        conversation_id = request.conversation_id
        
        if conversation_id:
            # Get existing conversation
            conv_response = db.table("ai_conversations").select("*").eq("id", conversation_id).eq("user_id", current_user["id"]).execute()
            if not conv_response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            conversation_data = conv_response.data[0]
            messages = conversation_data["messages"]
        else:
            # Create new conversation
            conversation_data = {
                "user_id": current_user["id"],
                "paper_id": request.paper_id,
                "messages": []
            }
            insert_response = db.table("ai_conversations").insert(conversation_data).execute()
            conversation_id = insert_response.data[0]["id"]
            messages = []
        
        # Get paper details
        paper_response = db.table("papers").select("*").eq("arxiv_id", request.paper_id).execute()
        if not paper_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        paper = paper_response.data[0]
        
        # Add user message
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat()
        }
        messages.append(user_message)
        
        # Prepare context for AI
        system_prompt = f"""You are an AI assistant helping users understand research papers from arXiv.
        
Paper Title: {paper['title']}
Abstract: {paper['abstract']}
Authors: {', '.join([a['name'] for a in paper['authors']])}
Category: {paper['primary_category']}

Answer questions about this paper based on the abstract and your knowledge. Be concise and helpful."""
        
        # Call AI API
        ai_client = get_ai_client()
        
        # Prepare messages for OpenAI
        openai_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history (last 10 messages for context)
        for msg in messages[-10:]:
            openai_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        response = ai_client.chat.completions.create(
            model=settings.ai_model,
            messages=openai_messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_message_content = response.choices[0].message.content
        
        # Add AI response
        ai_message = {
            "role": "assistant",
            "content": ai_message_content,
            "timestamp": datetime.utcnow().isoformat()
        }
        messages.append(ai_message)
        
        # Update conversation
        db.table("ai_conversations").update({
            "messages": messages,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", conversation_id).execute()
        
        return ChatResponse(
            message=ai_message_content,
            conversation_id=conversation_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )


@router.get("/conversations/{paper_id}", response_model=Conversation)
async def get_conversation(
    paper_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Get conversation history for a paper."""
    try:
        response = db.table("ai_conversations").select("*").eq("user_id", current_user["id"]).eq("paper_id", paper_id).execute()
        
        if not response.data:
            # Return empty conversation
            return Conversation(
                id="",
                user_id=current_user["id"],
                paper_id=paper_id,
                messages=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        conv_data = response.data[0]
        return Conversation(**conv_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching conversation: {str(e)}"
        )

