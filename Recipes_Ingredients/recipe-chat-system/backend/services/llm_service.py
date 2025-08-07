# backend/services/llm_service.py
"""
LLM Service for interacting with Ollama/Llama 3.2.
Now with Langfuse observability for all LLM operations.
"""
import json
import time
from typing import List, Tuple, Union, Dict, Optional
from ollama import Client

from config import settings
from schemas import RecipeQuery, TagsSemanticSchema
from prompts.system_prompts import system_prompt_main, system_prompt_semantic_fields, system_prompt_reset
from services.langfuse_service import get_langfuse_service, langfuse_trace

import logging
logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM interactions using Ollama with Langfuse tracking."""
    
    def __init__(self):
        """Initialize Ollama client and Langfuse."""
        self.client = Client(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
        self.langfuse = get_langfuse_service()
        
    def coerce_recipe(self, obj: Union[str, dict, RecipeQuery]) -> RecipeQuery:
        """Always return a RecipeQuery instance."""
        if isinstance(obj, RecipeQuery):
            return obj
        if isinstance(obj, str):
            return RecipeQuery.model_validate_json(obj)
        if isinstance(obj, dict):
            return RecipeQuery.model_validate(obj)
        raise TypeError(f"Cannot coerce {type(obj)} to RecipeQuery")
    
    def coerce_tags(self, obj: Union[str, dict, TagsSemanticSchema]) -> TagsSemanticSchema:
        """Always return a TagsSemanticSchema instance."""
        if isinstance(obj, TagsSemanticSchema):
            return obj
        if isinstance(obj, str):
            return TagsSemanticSchema.model_validate_json(obj)
        if isinstance(obj, dict):
            return TagsSemanticSchema.model_validate(obj)
        raise TypeError(f"Cannot coerce {type(obj)} to TagsSemanticSchema")
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Rough approximation: 1 token ≈ 4 characters for English text.
        """
        return len(text) // 4
    
    @langfuse_trace(name="extract_recipe_query")
    def extract_recipe_query(self, msg: str) -> RecipeQuery:
        """
        Extract structured recipe query from user message.
        Tracked with Langfuse for observability.
        """
        # Prepare the prompt
        prompt = msg
        
        # Track timing
        start_time = time.time()
        
        try:
            # Make the Ollama call
            resp = self.client.chat(
                model=self.model,
                format=RecipeQuery.model_json_schema(),
                messages=[
                    {"role": "system", "content": system_prompt_main},
                    {"role": "user", "content": msg},
                ],
                options={'temperature': 0.0},
            )
            
            # Calculate latency
            latency = time.time() - start_time
            
            # Parse response
            result = self.coerce_recipe(resp["message"]["content"])
            
            # Track with Langfuse
            if self.langfuse.enabled:
                self.langfuse.track_generation(
                    name="extract_recipe_query",
                    model=self.model,
                    prompt=f"System: {system_prompt_main[:200]}...\n\nUser: {msg}",
                    completion=resp["message"]["content"],
                    metadata={
                        "extraction_type": "recipe_query",
                        "temperature": 0.0,
                        "format": "json_schema",
                        "include_count": len(result.include_ingredients),
                        "exclude_count": len(result.exclude_ingredients),
                        "result_count": result.count
                    },
                    usage={
                        "prompt_tokens": self.estimate_tokens(system_prompt_main + msg),
                        "completion_tokens": self.estimate_tokens(resp["message"]["content"]),
                        "total_tokens": self.estimate_tokens(system_prompt_main + msg + resp["message"]["content"])
                    },
                    latency=latency
                )
            
            logger.info(f"Extracted recipe query in {latency:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract recipe query: {e}")
            # Track error in Langfuse
            if self.langfuse.enabled:
                self.langfuse.track_span(
                    name="extract_recipe_query_error",
                    metadata={"error": str(e), "input": msg},
                    level="ERROR"
                )
            raise
    
    @langfuse_trace(name="extract_tags")
    def extract_tags(self, msg: str) -> TagsSemanticSchema:
        """
        Extract semantic tags from user message.
        Tracked with Langfuse for observability.
        """
        start_time = time.time()
        
        try:
            resp = self.client.chat(
                model=self.model,
                format=TagsSemanticSchema.model_json_schema(),
                messages=[
                    {"role": "system", "content": system_prompt_semantic_fields},
                    {"role": "user", "content": msg}
                ],
                options={'temperature': 0.0},
            )
            
            latency = time.time() - start_time
            result = self.coerce_tags(resp["message"]["content"])
            
            # Count how many tags were extracted
            tags_found = sum(1 for v in result.model_dump().values() if v)
            
            # Track with Langfuse
            if self.langfuse.enabled:
                self.langfuse.track_generation(
                    name="extract_tags",
                    model=self.model,
                    prompt=f"System: {system_prompt_semantic_fields[:200]}...\n\nUser: {msg}",
                    completion=resp["message"]["content"],
                    metadata={
                        "extraction_type": "semantic_tags",
                        "temperature": 0.0,
                        "format": "json_schema",
                        "tags_found": tags_found,
                        "tags": result.model_dump()
                    },
                    usage={
                        "prompt_tokens": self.estimate_tokens(system_prompt_semantic_fields + msg),
                        "completion_tokens": self.estimate_tokens(resp["message"]["content"]),
                        "total_tokens": self.estimate_tokens(system_prompt_semantic_fields + msg + resp["message"]["content"])
                    },
                    latency=latency
                )
            
            logger.info(f"Extracted {tags_found} tags in {latency:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract tags: {e}")
            if self.langfuse.enabled:
                self.langfuse.track_span(
                    name="extract_tags_error",
                    metadata={"error": str(e), "input": msg},
                    level="ERROR"
                )
            raise
    
    @langfuse_trace(name="check_continuation")
    def check_continue(self, conversation_history: List[str], current_message: str) -> Tuple[bool, str]:
        """
        Check if current message continues from conversation history.
        Tracked with Langfuse for observability.
        
        Args:
            conversation_history: List of all previous messages in order
            current_message: The new message to evaluate
            
        Returns:
            tuple: (should_continue, reason)
        """
        # Format history for the prompt
        history_text = "\n".join([f"Message {i+1}: {msg}" for i, msg in enumerate(conversation_history)])
        
        prompt = f"""Conversation history:
{history_text}

Current message: {current_message}"""
        
        start_time = time.time()
        
        try:
            response = self.client.chat(
                model=self.model,
                format='json',
                messages=[
                    {"role": "system", "content": system_prompt_reset},
                    {"role": "user", "content": prompt}
                ],
                options={'temperature': 0.0}
            )
            
            latency = time.time() - start_time
            result = json.loads(response['message']['content'])
            should_continue = result.get("continue", False)
            reason = result.get("reason", "")
            
            # Track with Langfuse
            if self.langfuse.enabled:
                self.langfuse.track_generation(
                    name="check_continuation",
                    model=self.model,
                    prompt=f"System: {system_prompt_reset[:200]}...\n\nUser: {prompt[:500]}...",
                    completion=response['message']['content'],
                    metadata={
                        "extraction_type": "continuation_check",
                        "temperature": 0.0,
                        "format": "json",
                        "should_continue": should_continue,
                        "reason": reason,
                        "history_length": len(conversation_history),
                        "message_length": len(current_message)
                    },
                    usage={
                        "prompt_tokens": self.estimate_tokens(system_prompt_reset + prompt),
                        "completion_tokens": self.estimate_tokens(response['message']['content']),
                        "total_tokens": self.estimate_tokens(system_prompt_reset + prompt + response['message']['content'])
                    },
                    latency=latency
                )
            
            logger.info(f"Continuation check: {should_continue} - {reason[:50]}...")
            return should_continue, reason
            
        except Exception as e:
            logger.error(f"Failed to check continuation: {e}")
            if self.langfuse.enabled:
                self.langfuse.track_span(
                    name="check_continuation_error",
                    metadata={"error": str(e), "history_length": len(conversation_history)},
                    level="ERROR"
                )
            # Default to not continuing on error
            return False, "Error in continuation check"


# Singleton instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get or create singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service