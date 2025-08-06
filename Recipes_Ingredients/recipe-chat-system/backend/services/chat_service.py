# backend/services/chat_service.py
"""
Chat Service for managing conversations and orchestrating the recipe search.
Ports the conversation management logic from the notebook.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from copy import deepcopy
import logging

from schemas import RecipeQuery, TagsSemanticSchema
from services.llm_service import get_llm_service
from services.recipe_service import get_recipe_service

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of merging two recipe queries"""
    merged_query: RecipeQuery
    changes: Dict[str, List[str]]
    conflicts: List[str]


@dataclass
class ConversationState:
    """Current state of a conversation"""
    conversation_id: int
    turn_counter: int
    current_recipe_query: Optional[RecipeQuery]
    current_tags: Optional[TagsSemanticSchema]
    history: List[str]


@dataclass
class ProcessedMessage:
    """Result of processing a user message"""
    query: RecipeQuery
    tags: TagsSemanticSchema
    is_continuation: bool
    changes: Optional[Dict] = None
    conflicts: Optional[List[str]] = None


class ChatService:
    """Service for managing chat conversations and recipe searches."""
    
    def __init__(self):
        """Initialize the chat service."""
        self.llm_service = get_llm_service()
        self.recipe_service = get_recipe_service()
        # In-memory conversation states (for MVP)
        # In production, this would be Redis or database
        self.conversation_states: Dict[int, ConversationState] = {}
    
    def merge_recipe_query_v2(self, base: RecipeQuery, patch: RecipeQuery) -> MergeResult:
        """
        Merge patch into base with change tracking.
        Ported from notebook lines ~400.
        
        Returns:
            MergeResult containing merged query, changes made, and any conflicts
        """
        updated = deepcopy(base)
        changes = {
            "added_includes": [],
            "removed_includes": [],
            "added_excludes": [],
            "removed_excludes": [],
            "count_changed": None
        }
        conflicts = []
        
        # Convert to sets for operations
        inc = set(updated.include_ingredients)
        exc = set(updated.exclude_ingredients)
        p_inc = set(patch.include_ingredients)
        p_exc = set(patch.exclude_ingredients)
        
        # Track new includes
        new_includes = p_inc - inc
        changes["added_includes"] = list(new_includes)
        
        # Track new excludes
        new_excludes = p_exc - exc
        changes["added_excludes"] = list(new_excludes)
        
        # Find conflicts: ingredients moving from include to exclude
        moving_to_exclude = inc.intersection(p_exc)
        if moving_to_exclude:
            conflicts.extend([f"'{ing}' moved from include to exclude" for ing in moving_to_exclude])
            changes["removed_includes"].extend(list(moving_to_exclude))
        
        # Find reverse conflicts: ingredients moving from exclude to include
        moving_to_include = exc.intersection(p_inc)
        if moving_to_include:
            conflicts.extend([f"'{ing}' moved from exclude to include" for ing in moving_to_include])
            changes["removed_excludes"].extend(list(moving_to_include))
        
        # Apply changes
        inc.update(p_inc)
        inc.difference_update(p_exc)  # Remove newly excluded
        exc.update(p_exc)
        exc.difference_update(p_inc)  # Remove newly included
        
        updated.include_ingredients = sorted(inc)
        updated.exclude_ingredients = sorted(exc)
        
        # Track count change
        if patch.count != 5 and patch.count != base.count:
            changes["count_changed"] = f"{base.count} → {patch.count}"
            updated.count = patch.count
        
        # Keep original query (as in notebook)
        # updated.query stays the same
        
        return MergeResult(
            merged_query=updated,
            changes=changes,
            conflicts=conflicts
        )
    
    def get_or_create_state(self, conversation_id: int) -> ConversationState:
        """Get existing conversation state or create new one."""
        if conversation_id not in self.conversation_states:
            self.conversation_states[conversation_id] = ConversationState(
                conversation_id=conversation_id,
                turn_counter=0,
                current_recipe_query=None,
                current_tags=None,
                history=[]
            )
        return self.conversation_states[conversation_id]
    
    def process_user_message(self, user_message: str, conversation_id: int) -> ProcessedMessage:
        """
        Process a user message in the context of a conversation.
        Ported from notebook lines ~600-750.
        
        Returns:
            ProcessedMessage with extracted query, tags, and state info
        """
        state = self.get_or_create_state(conversation_id)
        
        # FIRST TURN – extract everything and store
        if state.turn_counter == 0:
            state.history.append(user_message)
            state.current_recipe_query = self.llm_service.extract_recipe_query(user_message)
            state.current_tags = self.llm_service.extract_tags(user_message)
            state.turn_counter = 1
            
            logger.info(f"INITIAL STATE for conversation {conversation_id}")
            logger.info(f"Query: {state.current_recipe_query.model_dump()}")
            logger.info(f"Tags: {state.current_tags.model_dump()}")
            
            return ProcessedMessage(
                query=state.current_recipe_query,
                tags=state.current_tags,
                is_continuation=False
            )
        
        # CONTINUATION / RESET decision using full history
        is_cont, reason = self.llm_service.check_continue(state.history, user_message)
        logger.info(f"Continue decision: {is_cont} - Reason: {reason}")
        
        if is_cont:
            # CONTINUATION: Only merge ingredients and count, keep original query and tags
            state.history.append(user_message)
            
            # Extract patch (only ingredients and count matter)
            patch_query = self.llm_service.extract_recipe_query(user_message)
            
            # Merge with tracking
            merge_result = self.merge_recipe_query_v2(state.current_recipe_query, patch_query)
            state.current_recipe_query = merge_result.merged_query
            
            logger.info(f"CONTINUATION STATE for conversation {conversation_id}")
            logger.info(f"Query: {state.current_recipe_query.model_dump()}")
            logger.info(f"Changes: {merge_result.changes}")
            if merge_result.conflicts:
                logger.info(f"Conflicts: {merge_result.conflicts}")
            
            state.turn_counter += 1
            
            return ProcessedMessage(
                query=state.current_recipe_query,
                tags=state.current_tags,  # Tags unchanged
                is_continuation=True,
                changes=merge_result.changes,
                conflicts=merge_result.conflicts
            )
        
        else:
            # RESET: Start fresh with new query and tags
            state.history = [user_message]  # Reset history
            state.current_recipe_query = self.llm_service.extract_recipe_query(user_message)
            state.current_tags = self.llm_service.extract_tags(user_message)
            state.turn_counter = 1
            
            logger.info(f"RESET STATE for conversation {conversation_id}")
            logger.info(f"Query: {state.current_recipe_query.model_dump()}")
            logger.info(f"Tags: {state.current_tags.model_dump()}")
            
            return ProcessedMessage(
                query=state.current_recipe_query,
                tags=state.current_tags,
                is_continuation=False
            )
    
    def search_recipes(self, processed_message: ProcessedMessage) -> Dict:
        """
        Search for recipes based on processed message.
        
        Returns:
            Search results from recipe service
        """
        return self.recipe_service.search_recipes_ingredients_first(
            processed_message.query,
            processed_message.tags
        )
    
    def clear_conversation_state(self, conversation_id: int):
        """Clear the state for a conversation."""
        if conversation_id in self.conversation_states:
            del self.conversation_states[conversation_id]
            logger.info(f"Cleared state for conversation {conversation_id}")


# Singleton instance
_chat_service = None

def get_chat_service() -> ChatService:
    """Get or create singleton chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service