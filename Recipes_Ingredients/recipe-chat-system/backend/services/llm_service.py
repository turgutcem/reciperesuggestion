# backend/services/llm_service.py
"""
LLM Service for interacting with Ollama/Llama 3.2.
Ports the extraction functions from the notebook.
"""
import json
from typing import List, Tuple, Union, Dict, Optional
from ollama import Client

from config import settings
from schemas import RecipeQuery, TagsSemanticSchema
from prompts.system_prompts import system_prompt_main, system_prompt_semantic_fields, system_prompt_reset


class LLMService:
    """Service for LLM interactions using Ollama."""
    
    def __init__(self):
        """Initialize Ollama client."""
        self.client = Client(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
        
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
    
    def extract_recipe_query(self, msg: str) -> RecipeQuery:
        """
        Extract structured recipe query from user message.
        Ported from notebook lines ~600.
        """
        resp = self.client.chat(
            model=self.model,
            format=RecipeQuery.model_json_schema(),
            messages=[
                {"role": "system", "content": system_prompt_main},
                {"role": "user", "content": msg},
            ],
            options={'temperature': 0.0},
        )
        return self.coerce_recipe(resp["message"]["content"])
    
    def extract_tags(self, msg: str) -> TagsSemanticSchema:
        """
        Extract semantic tags from user message.
        Ported from notebook lines ~650.
        """
        resp = self.client.chat(
            model=self.model,
            format=TagsSemanticSchema.model_json_schema(),
            messages=[
                {"role": "system", "content": system_prompt_semantic_fields},
                {"role": "user", "content": msg}
            ],
            options={'temperature': 0.0},
        )
        return self.coerce_tags(resp["message"]["content"])
    
    def check_continue(self, conversation_history: List[str], current_message: str) -> Tuple[bool, str]:
        """
        Check if current message continues from conversation history.
        Ported from notebook lines ~250.
        
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
        
        response = self.client.chat(
            model=self.model,
            format='json',
            messages=[
                {"role": "system", "content": system_prompt_reset},
                {"role": "user", "content": prompt}
            ],
            options={'temperature': 0.0}
        )
        
        result = json.loads(response['message']['content'])
        should_continue = result.get("continue", False)
        reason = result.get("reason", "")
        
        return should_continue, reason


# Singleton instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get or create singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service