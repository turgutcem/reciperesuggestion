# backend/routers/chat.py
"""
Chat router for handling recipe search conversations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import logging
import ast
import re

from database import get_db
from models import Conversation, Message
from schemas import ChatRequest, ChatResponse
from services import get_chat_service, get_recipe_service
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def parse_db_list_string(value):
    """Parse string representation of list from database."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        result = ast.literal_eval(value)
        return result if isinstance(result, list) else [str(result)]
    except (ValueError, SyntaxError):
        # For steps, try to split by common patterns
        if isinstance(value, str):
            # Check for numbered steps
            if re.search(r'\d+\.\s+', value):
                steps = re.split(r'\d+\.\s+', value)
                return [s.strip() for s in steps if s.strip()]
            # Check for newline separation
            elif '\n' in value:
                return [s.strip() for s in value.split('\n') if s.strip()]
        return [str(value)]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process a chat message and return recipe recommendations.
    This is the main endpoint that coordinates everything.
    """
    chat_service = get_chat_service()
    recipe_service = get_recipe_service()
    
    try:
        # 1. Get or create conversation
        if request.conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user_id
            ).first()
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        else:
            # Create new conversation
            conversation = Conversation(
                user_id=user_id,
                title=request.message[:50]  # First 50 chars as title
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            logger.info(f"Created new conversation {conversation.id} for user {user_id}")
        
        # 2. Save user message
        user_message = Message(
            conversation_id=conversation.id,
            content=request.message,
            is_user=True
        )
        db.add(user_message)
        
        # 3. Process message through chat service
        processed = chat_service.process_user_message(
            request.message,
            conversation.id
        )
        
        # Save extracted data
        user_message.extracted_query = processed.query.model_dump()
        user_message.extracted_tags = processed.tags.model_dump()
        
        # 4. Search for recipes
        search_results = chat_service.search_recipes(processed)
        user_message.search_results = {
            'total_found': search_results['total_found'],
            'recipe_ids': search_results['recipe_ids']
        }
        
        # 5. Get recipe details with parsing fixes
        recipe_details = []
        if search_results['recipe_ids']:
            details = recipe_service.get_recipe_details(search_results['recipe_ids'])
            for recipe_id in search_results['recipe_ids']:
                if recipe_id in details:
                    recipe = details[recipe_id]
                    
                    # Parse ingredients and steps
                    parsed_ingredients = parse_db_list_string(recipe['ingredients_raw'])
                    parsed_steps = parse_db_list_string(recipe['steps'])
                    
                    recipe_details.append({
                        'id': recipe['recipe_id'],
                        'name': recipe['name'],
                        'description': recipe['description'][:200] + '...' if len(recipe['description']) > 200 else recipe['description'],
                        'full_description': recipe['description'],
                        'ingredients_raw': parsed_ingredients,  # Now a proper list
                        'steps': parsed_steps,  # Now a proper list
                        'servings': recipe['servings'],
                        'serving_size': recipe['serving_size'],
                        'tags': recipe['tags'],
                        'nutrition': recipe['nutrition'],
                        'score': search_results['embedding_scores'].get(recipe_id, 0)
                    })
        
        # 6. Format response
        if search_results['total_found'] > 0:
            response_text = f"I found {search_results['total_found']} {processed.query.query}. "
            if processed.query.include_ingredients:
                response_text += f"These recipes include {', '.join(processed.query.include_ingredients)}. "
            if processed.query.exclude_ingredients:
                response_text += f"They don't contain {', '.join(processed.query.exclude_ingredients)}. "
            response_text += f"\n\nHere are the top {len(recipe_details)} recipes (click to expand):"
                
            if processed.is_continuation and processed.changes:
                response_text += "\n\n---\n"
                if processed.changes.get('added_includes'):
                    response_text += f"✓ Added ingredients: {', '.join(processed.changes['added_includes'])}\n"
                if processed.changes.get('added_excludes'):
                    response_text += f"✓ Now excluding: {', '.join(processed.changes['added_excludes'])}\n"
                if processed.conflicts:
                    response_text += f"⚠ Resolved conflicts: {'; '.join(processed.conflicts)}\n"
        else:
            response_text = "I couldn't find any recipes matching your criteria. "
            if processed.query.include_ingredients:
                response_text += f"No recipes found with all of: {', '.join(processed.query.include_ingredients)}. "
            response_text += "Try adjusting your requirements or asking for something different."
        
        # 7. Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            content=response_text,
            is_user=False,
            search_results=search_results
        )
        db.add(assistant_message)
        db.commit()
        
        # 8. Return response
        return ChatResponse(
            message=response_text,
            conversation_id=conversation.id,
            recipes=recipe_details,
            query_info={
                'query': processed.query.model_dump(),
                'tags': processed.tags.model_dump(),
                'is_continuation': processed.is_continuation,
                'total_found': search_results['total_found']
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/conversations")
async def get_conversations(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """Get user's conversation history."""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id,
        Conversation.is_active == True
    ).order_by(
        Conversation.updated_at.desc()
    ).limit(limit).offset(offset).all()
    
    return [
        {
            'id': c.id,
            'title': c.title,
            'created_at': c.created_at,
            'updated_at': c.updated_at,
            'message_count': len(c.messages)
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    include_recipes: bool = True  # New parameter
):
    """Get messages for a specific conversation with optional recipe details."""
    # Verify conversation belongs to user
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(
        Message.created_at
    ).limit(limit).offset(offset).all()
    
    recipe_service = get_recipe_service()
    
    result = []
    for m in messages:
        message_data = {
            'id': m.id,
            'content': m.content,
            'is_user': m.is_user,
            'created_at': m.created_at,
            'extracted_query': m.extracted_query,
            'extracted_tags': m.extracted_tags,
            'recipes': []  # Will be populated if available
        }
        
        # If this is an assistant message with search results, fetch recipe details
        if not m.is_user and include_recipes and m.search_results:
            recipe_ids = m.search_results.get('recipe_ids', [])
            if recipe_ids:
                # Re-fetch recipe details
                details = recipe_service.get_recipe_details(recipe_ids)
                recipes = []
                for recipe_id in recipe_ids:
                    if recipe_id in details:
                        recipe = details[recipe_id]
                        # Parse ingredients and steps
                        parsed_ingredients = parse_db_list_string(recipe['ingredients_raw'])
                        parsed_steps = parse_db_list_string(recipe['steps'])
                        
                        recipes.append({
                            'id': recipe['recipe_id'],
                            'name': recipe['name'],
                            'description': recipe['description'] + '...' if len(recipe['description']) > 200 else recipe['description'],
                            'full_description': recipe['description'],
                            'ingredients_raw': parsed_ingredients,
                            'steps': parsed_steps,
                            'servings': recipe['servings'],
                            'serving_size': recipe['serving_size'],
                            'tags': recipe['tags'],
                            'nutrition': recipe['nutrition'],
                            'score': 0  # Score not saved, default to 0
                        })
                message_data['recipes'] = recipes
        
        result.append(message_data)
    
    return result


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete a conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Soft delete
    conversation.is_active = False
    db.commit()
    
    # Clear from chat service cache
    chat_service = get_chat_service()
    chat_service.clear_conversation_state(conversation_id)
    
    return {"message": "Conversation deleted"}


@router.post("/conversations/{conversation_id}/reset")
async def reset_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset conversation state (clear cache)."""
    # Verify conversation belongs to user
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Clear from chat service cache
    chat_service = get_chat_service()
    chat_service.clear_conversation_state(conversation_id)
    
    return {"message": "Conversation state reset"}