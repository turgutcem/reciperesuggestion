from fastapi import FastAPI, HTTPException, Depends, Session
from fastapi.middleware.cors import CORSMiddleware
from database import get_db
from chat_service import ChatService
from auth import get_current_user, create_user, authenticate_user
from pydantic import BaseModel
from typing import List, Optional
import logging

app = FastAPI(title="Recipe Chat API")

# Enable CORS for Gradio frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7860", "http://frontend:7860"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
chat_service = ChatService()

# Request/Response models
class LoginRequest(BaseModel):
    email: str
    password: str

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    recipes: List[dict] = []

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Authentication endpoints
@app.post("/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"user_id": user.id, "email": user.email}

@app.post("/auth/register")
async def register(request: LoginRequest, db: Session = Depends(get_db)):
    user = create_user(db, request.email, request.password)
    return {"user_id": user.id, "email": user.email}

# Chat endpoints
@app.post("/chat/send", response_model=ChatResponse)
async def send_message(
    request: ChatMessage,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    response = await chat_service.process_message(
        user_id=current_user["user_id"],
        message=request.message,
        conversation_id=request.conversation_id,
        db=db
    )
    return response

@app.get("/chat/conversations")
async def get_conversations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return chat_service.get_user_conversations(current_user["user_id"], db)

@app.get("/chat/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return chat_service.get_conversation_messages(conversation_id, db)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)