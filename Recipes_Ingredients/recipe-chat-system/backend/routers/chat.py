# backend/routers/chat.py
"""
Chat router for handling recipe search conversations.
FIXED: Proper authentication and null handling.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional
import logging
import ast
import re
import time

from database import get_db
from models import Conversation, Message
from schemas import ChatRequest, ChatResponse
from services import get_chat_service, get_recipe_service
from services.langfuse_service import get_langfuse_service
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def parse_db_list_string(value):
    """
    Parse string representation of list from database.
    FIXED: Proper null handling
    """
    # Handle None and empty values
    if value is None:
        return []
    if not value:
        return []
    if isinstance(value, list):
        return value
    
    try:
        # Try to parse as Python literal
        result = ast.literal_eval(value)
        return result if isinstance(result, list) else [str(result)]
    except (ValueError, SyntaxError, TypeError):
        # Handle as string
        if isinstance(value, str):
            # Check for numbered steps
            if re.search(r'\d+\.\s+', value):
                steps = re.split(r'\d+\.\s+', value)
                return [s.strip() for s in steps if s.strip()]
            # Check for newline separation
            elif '\n' in value:
                return [s.strip() for s in value.split('\n') if s.strip()]
            # Return as single item
            return [value.strip()] if value.strip() else []
        return []


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authorization: str = Header(None),  # FIXED: Require auth header
    db: Session = Depends(get_db)
):
    """
    Process a chat message and return recipe recommendations.
    FIXED: Proper authentication required
    """
    # Get authenticated user ID
    try:
        user_id = get_current_user(authorization)
    except HTTPException as e:
        logger.warning(f"Unauthorized chat attempt: {e.detail}")
        raise
    
    chat_service = get_chat_service()
    recipe_service = get_recipe_service()
    langfuse = get_langfuse_service()
    
    # Start timing
    start_time = time.time()
    
    # Start Langfuse trace for the entire request
    trace = langfuse.start_trace(
        name="chat_request",
        user_id=user_id,
        conversation_id=request.conversation_id,
        metadata={
            "message_length": len(request.message),
            "has_conversation": request.conversation_id is not None,
            "authenticated_user": user_id
        }
    )
    
    try:
        # 1. Get or create conversation (tracked as span)
        with langfuse.span_context("conversation_management") as span:
            if request.conversation_id:
                # Verify conversation belongs to the authenticated user
                conversation = db.query(Conversation).filter(
                    Conversation.id == request.conversation_id,
                    Conversation.user_id == user_id  # FIXED: Use authenticated user_id
                ).first()
                
                if not conversation:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Conversation not found or access denied"
                    )
                    
                if span:
                    span.update(output={"action": "loaded_existing", "id": conversation.id})
            else:
                # Create new conversation for authenticated user
                conversation = Conversation(
                    user_id=user_id,  # FIXED: Use authenticated user_id
                    title=request.message[:50] if request.message else "New Chat"
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
                logger.info(f"Created new conversation {conversation.id} for user {user_id}")
                
                if span:
                    span.update(output={"action": "created_new", "id": conversation.id})
        
        # 2. Save user message
        user_message = Message(
            conversation_id=conversation.id,
            content=request.message,
            is_user=True
        )
        db.add(user_message)
        
        # 3. Process message through chat service
        with langfuse.span_context("message_processing", 
                                 metadata={"conversation_id": conversation.id}) as span:
            processed = chat_service.process_user_message(
                request.message,
                conversation.id
            )
            
            if span:
                span.update(output={
                    "is_continuation": processed.is_continuation,
                    "include_ingredients": processed.query.include_ingredients,
                    "exclude_ingredients": processed.query.exclude_ingredients,
                    "tags_found": sum(1 for v in processed.tags.model_dump().values() if v)
                })
        
        # Save extracted data
        user_message.extracted_query = processed.query.model_dump()
        user_message.extracted_tags = processed.tags.model_dump()
        
        # 4. Search for recipes
        with langfuse.span_context("recipe_search",
                                 metadata={"query": processed.query.query}) as span:
            search_results = chat_service.search_recipes(processed)
            
            if span:
                span.update(output={
                    "total_found": search_results.get('total_found', 0),
                    "returned_count": len(search_results.get('recipe_ids', [])),
                    "top_scores": list(search_results.get('embedding_scores', {}).values())[:3]
                })
        
        user_message.search_results = {
            'total_found': search_results.get('total_found', 0),
            'recipe_ids': search_results.get('recipe_ids', [])
        }
        
        # 5. Get recipe details with proper null handling
        recipe_details = []
        recipe_ids = search_results.get('recipe_ids', [])
        
        if recipe_ids:
            with langfuse.span_context("fetch_recipe_details",
                                     metadata={"count": len(recipe_ids)}) as span:
                details = recipe_service.get_recipe_details(recipe_ids)
                
                for recipe_id in recipe_ids:
                    if recipe_id in details:
                        recipe = details[recipe_id]
                        
                        # FIXED: Safe parsing with null checks
                        try:
                            parsed_ingredients = parse_db_list_string(
                                recipe.get('ingredients_raw')
                            )
                            parsed_steps = parse_db_list_string(
                                recipe.get('steps')
                            )
                            
                            # Build recipe detail with safe gets
                            recipe_detail = {
                                'id': recipe.get('recipe_id', recipe_id),
                                'name': recipe.get('name', 'Unknown Recipe'),
                                'description': '',
                                'full_description': recipe.get('description', ''),
                                'ingredients_raw': parsed_ingredients,
                                'steps': parsed_steps,
                                'servings': recipe.get('servings'),
                                'serving_size': recipe.get('serving_size'),
                                'tags': recipe.get('tags', []),
                                'nutrition': recipe.get('nutrition', {}),
                                'score': search_results.get('embedding_scores', {}).get(recipe_id, 0)
                            }
                            
                            # Handle description safely
                            desc = recipe.get('description', '')
                            if desc and len(desc) > 200:
                                recipe_detail['description'] = desc[:200] + '...'
                            else:
                                recipe_detail['description'] = desc
                            
                            recipe_details.append(recipe_detail)
                            
                        except Exception as e:
                            logger.error(f"Error parsing recipe {recipe_id}: {e}")
                            continue
                
                if span:
                    span.update(output={"recipes_fetched": len(recipe_details)})
        
        # Track recipe relevance scores in Langfuse
        if langfuse.enabled and recipe_details:
            for i, recipe in enumerate(recipe_details[:3]):  # Top 3 recipes
                langfuse.track_score(
                    name="recipe_relevance",
                    value=recipe.get('score', 0),
                    comment=f"Recipe: {recipe.get('name', 'Unknown')}, Position: {i+1}"
                )
        
        # 6. Format response
        total_found = search_results.get('total_found', 0)
        
        if total_found > 0:
            response_text = f"I found {total_found} {processed.query.query}. "
            
            if processed.query.include_ingredients:
                response_text += f"These recipes include {', '.join(processed.query.include_ingredients)}. "
            
            if processed.query.exclude_ingredients:
                response_text += f"They don't contain {', '.join(processed.query.exclude_ingredients)}. "
            
            response_text += f"\n\nHere are the top {len(recipe_details)} recipes (click to expand):"
            
            # Add change info for continuations
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
        
        # Calculate total latency
        total_latency = time.time() - start_time
        
        # Update trace with final metadata
        if trace:
            trace.update(
                metadata={
                    "total_latency_seconds": total_latency,
                    "recipes_found": total_found,
                    "recipes_returned": len(recipe_details),
                    "is_continuation": processed.is_continuation,
                    "success": True
                }
            )
        
        # Track overall request success
        if langfuse.enabled:
            langfuse.track_score(
                name="request_success",
                value=1.0,
                comment=f"Found {total_found} recipes in {total_latency:.2f}s"
            )
        
        logger.info(f"Chat request completed in {total_latency:.2f}s for user {user_id}")
        
        # 8. Return response
        return ChatResponse(
            message=response_text,
            conversation_id=conversation.id,
            recipes=recipe_details,
            query_info={
                'query': processed.query.model_dump(),
                'tags': processed.tags.model_dump(),
                'is_continuation': processed.is_continuation,
                'total_found': total_found
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error for user {user_id}: {e}", exc_info=True)
        db.rollback()
        
        # Track error in Langfuse
        if trace:
            trace.update(
                metadata={
                    "error": str(e),
                    "success": False,
                    "user_id": user_id
                },
                level="ERROR"
            )
        
        # Track failure score
        if langfuse.enabled:
            langfuse.track_score(
                name="request_success",
                value=0.0,
                comment=f"Error: {str(e)}"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )
    finally:
        # Ensure Langfuse data is sent
        langfuse.flush()


@router.get("/conversations")
async def get_conversations(
    authorization: str = Header(None),  # FIXED: Require auth
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """Get user's conversation history."""
    # Get authenticated user ID
    user_id = get_current_user(authorization)
    
    langfuse = get_langfuse_service()
    
    with langfuse.span_context("get_conversations", 
                              metadata={"user_id": user_id, "limit": limit}) as span:
        # FIXED: Only get conversations for authenticated user
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.is_active == True
        ).order_by(
            Conversation.updated_at.desc()
        ).limit(limit).offset(offset).all()
        
        result = [
            {
                'id': c.id,
                'title': c.title or "Untitled Chat",
                'created_at': c.created_at,
                'updated_at': c.updated_at,
                'message_count': len(c.messages)
            }
            for c in conversations
        ]
        
        if span:
            span.update(output={"count": len(result)})
        
        return result


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    authorization: str = Header(None),  # FIXED: Require auth
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    include_recipes: bool = True
):
    """Get messages for a specific conversation with optional recipe details."""
    # Get authenticated user ID
    user_id = get_current_user(authorization)
    
    langfuse = get_langfuse_service()
    
    with langfuse.span_context("get_messages",
                              metadata={"conversation_id": conversation_id,
                                      "include_recipes": include_recipes}) as span:
        # FIXED: Verify conversation belongs to authenticated user
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied"
            )
        
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(
            Message.created_at
        ).limit(limit).offset(offset).all()
        
        recipe_service = get_recipe_service()
        
        result = []
        recipes_loaded = 0
        
        for m in messages:
            message_data = {
                'id': m.id,
                'content': m.content,
                'is_user': m.is_user,
                'created_at': m.created_at,
                'extracted_query': m.extracted_query,
                'extracted_tags': m.extracted_tags,
                'recipes': []
            }
            
            # If this is an assistant message with search results, fetch recipe details
            if not m.is_user and include_recipes and m.search_results:
                recipe_ids = m.search_results.get('recipe_ids', [])
                if recipe_ids:
                    try:
                        # Re-fetch recipe details
                        details = recipe_service.get_recipe_details(recipe_ids)
                        recipes = []
                        
                        for recipe_id in recipe_ids:
                            if recipe_id in details:
                                recipe = details[recipe_id]
                                
                                # Parse with null safety
                                parsed_ingredients = parse_db_list_string(
                                    recipe.get('ingredients_raw')
                                )
                                parsed_steps = parse_db_list_string(
                                    recipe.get('steps')
                                )
                                
                                # Handle description
                                desc = recipe.get('description', '')
                                short_desc = desc[:200] + '...' if desc and len(desc) > 200 else desc
                                
                                recipes.append({
                                    'id': recipe.get('recipe_id', recipe_id),
                                    'name': recipe.get('name', 'Unknown Recipe'),
                                    'description': short_desc,
                                    'full_description': desc,
                                    'ingredients_raw': parsed_ingredients,
                                    'steps': parsed_steps,
                                    'servings': recipe.get('servings'),
                                    'serving_size': recipe.get('serving_size'),
                                    'tags': recipe.get('tags', []),
                                    'nutrition': recipe.get('nutrition', {}),
                                    'score': 0  # Score not saved, default to 0
                                })
                        
                        message_data['recipes'] = recipes
                        recipes_loaded += len(recipes)
                        
                    except Exception as e:
                        logger.error(f"Error loading recipes for message {m.id}: {e}")
            
            result.append(message_data)
        
        if span:
            span.update(output={
                "messages_count": len(result),
                "recipes_loaded": recipes_loaded
            })
        
        return result


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    authorization: str = Header(None),  # FIXED: Require auth
    db: Session = Depends(get_db)
):
    """Soft delete a conversation."""
    # Get authenticated user ID
    user_id = get_current_user(authorization)
    
    langfuse = get_langfuse_service()
    
    with langfuse.span_context("delete_conversation",
                              metadata={"conversation_id": conversation_id}) as span:
        # FIXED: Verify ownership
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied"
            )
        
        # Soft delete
        conversation.is_active = False
        db.commit()
        
        # Clear from chat service cache
        chat_service = get_chat_service()
        chat_service.clear_conversation_state(conversation_id)
        
        if span:
            span.update(output={"deleted": True})
        
        logger.info(f"User {user_id} deleted conversation {conversation_id}")
        
        return {"message": "Conversation deleted"}


@router.post("/conversations/{conversation_id}/reset")
async def reset_conversation(
    conversation_id: int,
    authorization: str = Header(None),  # FIXED: Require auth
    db: Session = Depends(get_db)
):
    """Reset conversation state (clear cache)."""
    # Get authenticated user ID
    user_id = get_current_user(authorization)
    
    langfuse = get_langfuse_service()
    
    with langfuse.span_context("reset_conversation",
                              metadata={"conversation_id": conversation_id}) as span:
        # FIXED: Verify ownership
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied"
            )
        
        # Clear from chat service cache
        chat_service = get_chat_service()
        chat_service.clear_conversation_state(conversation_id)
        
        if span:
            span.update(output={"reset": True})
        
        logger.info(f"User {user_id} reset conversation {conversation_id}")
        
        return {"message": "Conversation state reset"}