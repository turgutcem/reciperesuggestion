# backend/prompts/__init__.py
"""
Prompts module for the Recipe Chat System.
"""

from prompts.system_prompts import (
    system_prompt_main,
    system_prompt_semantic_fields,
    system_prompt_reset,
    GROUP_NAME_MAPPING,
    QUICK_TIME_TAGS
)

__all__ = [
    'system_prompt_main',
    'system_prompt_semantic_fields', 
    'system_prompt_reset',
    'GROUP_NAME_MAPPING',
    'QUICK_TIME_TAGS'
]