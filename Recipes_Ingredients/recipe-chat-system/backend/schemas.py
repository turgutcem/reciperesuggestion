from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Conversation schemas
class ConversationBase(BaseModel):
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    pass

class Conversation(ConversationBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    message_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

# Message schemas
class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    conversation_id: int
    is_user: bool
    created_at: datetime
    extracted_query: Optional[Dict[str, Any]] = None
    extracted_tags: Optional[Dict[str, Any]] = None
    search_results: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

# Chat request/response schemas
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None

class ChatResponse(BaseModel):
    message: str
    conversation_id: int
    recipes: Optional[List[Dict[str, Any]]] = None
    query_info: Optional[Dict[str, Any]] = None  # For debugging

# Recipe schemas (from notebook)
class RecipeQuery(BaseModel):
    query: str = Field(
        ..., 
        description="High-level natural language description of the desired recipe(s)"
    )
    include_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients to include"
    )
    exclude_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients to exclude"
    )
    count: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of results"
    )

class TagsSemanticSchema(BaseModel):
    TIME_DURATION: str = Field(default="", description="How long the recipe takes")
    DIFFICULTY_SCALE: str = Field(default="", description="Recipe difficulty")
    SCALE: str = Field(default="", description="Serving size")
    FREE_OF: str = Field(default="", description="Allergens to avoid")
    DIETS: str = Field(default="", description="Dietary restrictions")
    CUISINES_REGIONAL: str = Field(default="", description="Cuisine type")
    MEAL_COURSES: str = Field(default="", description="Meal type")
    PREPARATION_METHOD: str = Field(default="", description="Cooking method")