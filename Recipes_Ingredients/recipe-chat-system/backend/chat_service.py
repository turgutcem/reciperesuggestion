import json
from ollama import Client
from typing import List, Dict, Optional, Set, Tuple
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from database import get_db_connection, Conversation, ChatMessage
from sqlalchemy.orm import Session
from config import settings
import uuid
from datetime import datetime
from dataclasses import dataclass
from copy import deepcopy
import logging

logger = logging.getLogger(__name__)

# Pydantic models from notebook
class RecipeQuery(BaseModel):
    query: str = Field(
        ..., 
        description="High-level natural language description of the desired recipe(s), excluding specific ingredient information."
    )
    include_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients the user explicitly wants to include in the recipe."
    )
    exclude_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients the user explicitly wants to exclude from the recipe."
    )
    count: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of recipe results to return. If unspecified, defaults to 5."
    )

class TagsSemanticSchema(BaseModel):
    TIME_DURATION: str = Field(default="", description="User's phrasing about how long the recipe takes")
    DIFFICULTY_SCALE: str = Field(default="", description="Phrasing that reflects the ease or complexity of the recipe")
    SCALE: str = Field(default="", description="Phrasing about how many people or the serving size")
    FREE_OF: str = Field(default="", description="What the user wants to avoid: allergens or ingredients")
    DIETS: str = Field(default="", description="Dietary or health style mentioned (e.g. vegan, diabetic)")
    CUISINES_REGIONAL: str = Field(default="", description="Cultural or regional cuisine preference")
    MEAL_COURSES: str = Field(default="", description="Meal type or time (e.g. lunch, snack)")
    PREPARATION_METHOD: str = Field(default="", description="How the food is to be cooked or prepared")

@dataclass
class MergeResult:
    """Result of merging two recipe queries"""
    merged_query: RecipeQuery
    changes: Dict[str, List[str]]
    conflicts: List[str]

# Mapping for database group names
GROUP_NAME_MAPPING = {
    "DIETS": "DIETARY_HEALTH",
    "FREE_OF": "DIETARY_HEALTH",
    "SCALE": "DIFFICULTY_SCALE"
}

QUICK_TIME_TAGS = ["15-minutes-or-less", "30-minutes-or-less", "60-minutes-or-less"]

class ChatService:
    def __init__(self):
        """Initialize the chat service."""
        self.client = Client(host=settings.ollama_url)
        self.model = SentenceTransformer(settings.embedding_model)
        
        # Prompts from notebook
        self.system_prompt_main = """
You are a structured recipe query extractor. Convert natural language into a structured format.

OUTPUT FORMAT:
{
  "query": string,               // Natural language summary WITHOUT ingredients
  "include_ingredients": [list], // ONLY explicitly mentioned ingredients to include
  "exclude_ingredients": [list], // ONLY explicitly mentioned ingredients to exclude  
  "count": integer              // 1-10, default 5 if not specified
}

EXTRACTION RULES:

1. QUERY FIELD:
   - Summarize the recipe type, cuisine, meal, or style
   - NEVER include specific ingredients in the query
   - Keep it concise and descriptive
   
2. INGREDIENTS:
   - ONLY add ingredients that are EXPLICITLY mentioned
   - Never infer, assume, or add related ingredients
   - "Vegan" ≠ exclude meat (unless user says "no meat")
   - "Healthy" ≠ exclude sugar (unless user says "no sugar")

3. DECISION FLOW:
   ```
   User mentions ingredient?
   ├─ YES → Says "with/include"? → include_ingredients
   │        Says "without/no/exclude"? → exclude_ingredients
   └─ NO → Leave empty
   ```

4. COUNT:
   - Look for numbers + "recipes/dishes/options"
   - Default: 5, Min: 1, Max: 10

REMEMBER: When in doubt, be conservative. Only extract what is EXPLICITLY stated.
""".strip()

        self.system_prompt_semantic_fields = """
Extract recipe-related attributes from user messages. Return ONLY what is explicitly mentioned.

OUTPUT FORMAT:
{
  "TIME_DURATION": "",
  "DIFFICULTY_SCALE": "",
  "SCALE": "",
  "FREE_OF": "",
  "DIETS": "",
  "CUISINES_REGIONAL": "",
  "MEAL_COURSES": "",
  "PREPARATION_METHOD": ""
}

EXTRACTION RULES:
- Extract EXACT user phrases, not standardized terms
- Leave empty ("") if not mentioned
- Do NOT infer or add related concepts
- Keep user's original wording

FIELD DEFINITIONS:

TIME_DURATION: Cooking/prep time mentions
- "quick", "30 minutes", "overnight", "fast"
- NOT ingredients or methods

DIFFICULTY_SCALE: Skill level or simplicity
- "easy", "simple", "beginner", "few ingredients"
- NOT time-related terms

SCALE: Serving size or portions
- "for 2", "family dinner", "meal prep", "party"
- NOT difficulty or method

FREE_OF: Explicit exclusions for allergies/intolerances
- "gluten-free", "nut-free", "no dairy"
- NOT general dietary preferences (those go in DIETS)

DIETS: Named dietary patterns
- "vegan", "keto", "paleo", "vegetarian"
- NOT individual exclusions (those go in FREE_OF)

CUISINES_REGIONAL: Geographic or cultural origins
- "Italian", "Thai", "Southern", "Mediterranean"
- NOT meal types or methods

MEAL_COURSES: When/what type of meal
- "breakfast", "appetizer", "dessert", "lunch"
- NOT cuisines or ingredients

PREPARATION_METHOD: How it's cooked
- "grilled", "baked", "no-cook", "slow cooker"
- NOT difficulty or time

PRIORITY RULES:
1. "vegan" → DIETS (not FREE_OF)
2. "quick" → TIME_DURATION (not DIFFICULTY_SCALE)
3. "gluten-free" → FREE_OF (not DIETS)
4. Time + difficulty mentioned → assign each appropriately
""".strip()

        self.system_prompt_reset = """
You are a conversation continuity analyzer for a recipe assistant.

You will receive:
1. Conversation history (all previous messages)
2. Current message

Determine if the current message continues the existing conversation or starts a completely new recipe search.

OUTPUT FORMAT:
{
  "continue": boolean,
  "reason": string
}

CONTINUE = true when:
- User modifies/refines the existing search (add/remove ingredients, change count)
- User asks about variations of the same recipe theme
- User references previous messages ("that", "those", "the previous")
- User corrects themselves ("sorry, I meant...")

CONTINUE = false when:
- User asks about completely different cuisine/meal type
- User uses reset phrases ("forget that", "let's start over", "new search")
- User switches to unrelated recipe category (breakfast → dinner, dessert → main course)
- Topic has no connection to previous messages

Return only the JSON object.
""".strip()
        
        # Conversation state tracking
        self.conversation_states = {}
        
    def coerce_recipe(self, obj) -> RecipeQuery:
        """Always return a RecipeQuery instance."""
        if isinstance(obj, RecipeQuery):
            return obj
        if isinstance(obj, str):
            return RecipeQuery.model_validate_json(obj)
        if isinstance(obj, dict):
            return RecipeQuery.model_validate(obj)
        raise TypeError(f"Cannot coerce {type(obj)} to RecipeQuery")

    def coerce_tags(self, obj) -> TagsSemanticSchema:
        """Always return a TagsSemanticSchema instance."""
        if isinstance(obj, TagsSemanticSchema):
            return obj
        if isinstance(obj, str):
            return TagsSemanticSchema.model_validate_json(obj)
        if isinstance(obj, dict):
            return TagsSemanticSchema.model_validate(obj)
        raise TypeError(f"Cannot coerce {type(obj)} to TagsSemanticSchema")
    
    def extract_recipe_query(self, message: str) -> RecipeQuery:
        """Extract structured recipe query from user message."""
        response = self.client.chat(
            model=settings.llama_model,
            messages=[
                {"role": "system", "content": self.system_prompt_main},
                {"role": "user", "content": message}
            ],
            options={'temperature': 0.0},
            format=RecipeQuery.model_json_schema()
        )
        return self.coerce_recipe(response['message']['content'])
    
    def extract_tags(self, message: str) -> TagsSemanticSchema:
        """Extract semantic tags from user message."""
        response = self.client.chat(
            model=settings.llama_model,
            format=TagsSemanticSchema.model_json_schema(),
            messages=[
                {"role": "system", "content": self.system_prompt_semantic_fields},
                {"role": "user", "content": message}
            ],
            options={'temperature': 0.0}
        )
        return self.coerce_tags(response['message']['content'])
    
    def check_continue(self, history: List[str], current: str) -> Tuple[bool, str]:
        """Check if current message continues from conversation history."""
        history_text = "\n".join([f"Message {i+1}: {msg}" for i, msg in enumerate(history)])
        prompt = f"Conversation history:\n{history_text}\n\nCurrent message: {current}"
        
        response = self.client.chat(
            model=settings.llama_model,
            format='json',
            messages=[
                {"role": "system", "content": self.system_prompt_reset},
                {"role": "user", "content": prompt}
            ],
            options={'temperature': 0.0}
        )
        
        result = json.loads(response['message']['content'])
        return result.get("continue", False), result.get("reason", "")
    
    def merge_recipe_query(self, base: RecipeQuery, patch: RecipeQuery) -> MergeResult:
        """Merge patch into base with change tracking."""
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
        
        return MergeResult(
            merged_query=updated,
            changes=changes,
            conflicts=conflicts
        )
    
    async def process_message(self, user_id: str, message: str, conversation_id: Optional[str], db: Session) -> Dict:
        """Process user message and return response."""
        
        # Get or create conversation
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title=message[:50] + "..." if len(message) > 50 else message
            )
            db.add(conversation)
            db.commit()
        
        # Get conversation state
        state_key = f"{user_id}_{conversation_id}"
        if state_key not in self.conversation_states:
            self.conversation_states[state_key] = {
                'turn_counter': 0,
                'current_recipe_query': None,
                'current_tags': None,
                'conversation_history': []
            }
        
        state = self.conversation_states[state_key]
        
        # Process based on turn
        if state['turn_counter'] == 0:
            # First turn - extract everything
            state['current_recipe_query'] = self.extract_recipe_query(message)
            state['current_tags'] = self.extract_tags(message)
            state['conversation_history'].append(message)
            state['turn_counter'] = 1
        else:
            # Check continuation vs reset
            is_cont, reason = self.check_continue(state['conversation_history'], message)
            
            if is_cont:
                # Merge queries
                patch_query = self.extract_recipe_query(message)
                merge_result = self.merge_recipe_query(state['current_recipe_query'], patch_query)
                state['current_recipe_query'] = merge_result.merged_query
                state['conversation_history'].append(message)
            else:
                # Reset conversation
                state['conversation_history'] = [message]
                state['current_recipe_query'] = self.extract_recipe_query(message)
                state['current_tags'] = self.extract_tags(message)
                state['turn_counter'] = 1
        
        # Search for recipes
        search_results = self.search_recipes_ingredients_first(
            state['current_recipe_query'], 
            state['current_tags']
        )
        
        # Format response
        response_text = self.format_response(search_results, state['current_recipe_query'])
        
        # Save messages to database
        user_msg = ChatMessage(
            conversation_id=conversation_id,
            content=message,
            is_user=True,
            extracted_query=json.dumps(state['current_recipe_query'].model_dump()),
            search_results=json.dumps(search_results)
        )
        bot_msg = ChatMessage(
            conversation_id=conversation_id,
            content=response_text,
            is_user=False
        )
        
        db.add(user_msg)
        db.add(bot_msg)
        db.commit()
        
        # Update conversation updated_at
        conversation = db.query(Conversation).filter_by(id=conversation_id).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()
            db.commit()
        
        state['turn_counter'] += 1
        
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "recipes": search_results.get('recipe_details', [])
        }
    
    def search_recipes_ingredients_first(self, query: RecipeQuery, tags: TagsSemanticSchema) -> Dict:
        """Search using ingredients-first algorithm."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Convert tags to dict and map
            tags_dict = {k: v for k, v in tags.model_dump().items() if v}
            mapped_tags = self.map_tags_for_db(tags_dict)
            
            # Extract critical tags (DIETARY_HEALTH and CUISINES_REGIONAL)
            critical_tags = []
            if mapped_tags.get('DIETARY_HEALTH'):
                resolved = self.resolve_tag(mapped_tags['DIETARY_HEALTH'], 'DIETARY_HEALTH')
                if resolved:
                    critical_tags.append(resolved['tag_name'])
            
            if mapped_tags.get('CUISINES_REGIONAL'):
                resolved = self.resolve_tag(mapped_tags['CUISINES_REGIONAL'], 'CUISINES_REGIONAL')
                if resolved:
                    critical_tags.append(resolved['tag_name'])
            
            # Build query: Start with ingredients and critical tags
            query_parts = ["SELECT id FROM recipes WHERE 1=1"]
            params = []
            
            # Must have ALL included ingredients
            for ing_group in query.include_ingredients:
                resolved = self.resolve_ingredient_to_canonical(ing_group)
                if resolved:
                    variants = [v.lower() for v in self.get_all_ingredient_variants(resolved['canonical_id'])]
                    query_parts.append("""
                        AND EXISTS (
                            SELECT 1 FROM unnest(ingredients) AS ing
                            WHERE LOWER(ing) = ANY(%s::text[])
                        )
                    """)
                    params.append(variants)
            
            # Must NOT have any excluded ingredients
            exclude_variants = []
            for ing in query.exclude_ingredients:
                resolved = self.resolve_ingredient_to_canonical(ing)
                if resolved:
                    variants = self.get_all_ingredient_variants(resolved['canonical_id'])
                    exclude_variants.extend([v.lower() for v in variants])
            
            if exclude_variants:
                query_parts.append("""
                    AND NOT EXISTS (
                        SELECT 1 FROM unnest(ingredients) AS ing
                        WHERE LOWER(ing) = ANY(%s::text[])
                    )
                """)
                params.append(exclude_variants)
            
            # Must have ALL critical tags
            for tag in critical_tags:
                query_parts.append("""
                    AND %s = ANY(tags)
                """)
                params.append(tag.lower())
            
            # Execute query
            sql_query = '\n'.join(query_parts)
            cur.execute(sql_query, params)
            
            # Get all matching recipe IDs
            matching_ids = [row[0] for row in cur.fetchall()]
            
            if not matching_ids:
                return {
                    'recipe_ids': [],
                    'embedding_scores': {},
                    'total_found': 0,
                    'recipe_details': []
                }
            
            # Get embedding scores for these recipes
            query_embedding = self.model.encode(query.query).tolist()
            
            # Get embeddings and calculate scores
            placeholders = ','.join(['%s'] * len(matching_ids))
            cur.execute(f"""
                SELECT id, name, description, 
                       1 - (embedding <=> %s::vector) as similarity
                FROM recipes
                WHERE id IN ({placeholders})
                ORDER BY similarity DESC
            """, [query_embedding] + matching_ids)
            
            # Collect results
            results = []
            embedding_scores = {}
            recipe_details = []
            
            for row in cur.fetchall():
                recipe_id = row[0]
                results.append(recipe_id)
                embedding_scores[recipe_id] = float(row[3])
                
                # Add to details if in top N
                if len(recipe_details) < query.count:
                    recipe_details.append({
                        'id': recipe_id,
                        'name': row[1],
                        'description': row[2][:200] + '...' if len(row[2]) > 200 else row[2]
                    })
            
            return {
                'recipe_ids': results[:query.count],
                'embedding_scores': embedding_scores,
                'total_found': len(results),
                'recipe_details': recipe_details
            }
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                'recipe_ids': [],
                'embedding_scores': {},
                'total_found': 0,
                'recipe_details': []
            }
        finally:
            cur.close()
            conn.close()
    
    def format_response(self, search_results: Dict, query: RecipeQuery) -> str:
        """Format the response for the user."""
        if not search_results.get('recipe_ids'):
            return "I couldn't find any recipes matching your requirements. Try adjusting your ingredients or preferences."
        
        count = len(search_results['recipe_ids'])
        total = search_results.get('total_found', count)
        
        response = f"I found {total} recipes matching your requirements. "
        if total > count:
            response += f"Here are the top {count}:\n\n"
        else:
            response += "\n\n"
        
        for i, recipe in enumerate(search_results.get('recipe_details', []), 1):
            response += f"{i}. **{recipe['name']}**\n"
            response += f"   {recipe['description']}\n\n"
        
        return response
    
    def get_user_conversations(self, user_id: str, db: Session) -> List[Dict]:
        """Get user's conversation list."""
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).all()
        
        return [
            {
                "id": str(conv.id),
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat()
            }
            for conv in conversations
        ]
    
    def get_conversation_messages(self, conversation_id: str, db: Session) -> List[Dict]:
        """Get messages in a conversation."""
        messages = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        
        return [
            {
                "content": msg.content,
                "is_user": msg.is_user,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ]
    
    # Helper methods for ingredients and tags
    def resolve_ingredient_to_canonical(self, ingredient_name: str, confidence_threshold: float = 0.65) -> Optional[Dict]:
        """Find canonical ingredient from user input."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # First try exact match in variants
            cur.execute("""
                SELECT DISTINCT i.id, i.canonical
                FROM ingredients i
                JOIN ingredient_variants iv ON i.id = iv.canonical_id
                WHERE LOWER(iv.variant) = LOWER(%s)
            """, (ingredient_name,))
            
            result = cur.fetchone()
            if result:
                return {
                    'canonical_id': result[0],
                    'canonical_name': result[1],
                    'confidence': 1.0,
                    'method': 'exact_match'
                }
            
            # If no exact match, use embedding search
            ingredient_embedding = self.model.encode(ingredient_name).tolist()
            
            cur.execute("""
                SELECT 
                    i.id,
                    i.canonical,
                    iv.variant,
                    1 - (i.embedding <=> %s::vector) as similarity
                FROM ingredients i
                JOIN ingredient_variants iv ON i.id = iv.canonical_id
                WHERE 1 - (i.embedding <=> %s::vector) > %s
                ORDER BY i.embedding <=> %s::vector
                LIMIT 1
            """, (ingredient_embedding, ingredient_embedding, confidence_threshold, ingredient_embedding))
            
            result = cur.fetchone()
            if result:
                return {
                    'canonical_id': result[0],
                    'canonical_name': result[1],
                    'matched_variant': result[2],
                    'confidence': float(result[3]),
                    'method': 'embedding_match'
                }
            
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def get_all_ingredient_variants(self, canonical_id: int) -> List[str]:
        """Get all variants of a canonical ingredient."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT variant 
                FROM ingredient_variants 
                WHERE canonical_id = %s
            """, (canonical_id,))
            
            return [row[0] for row in cur.fetchall()]
            
        finally:
            cur.close()
            conn.close()
    
    def resolve_tag(self, tag_text: str, tag_group: Optional[str] = None, confidence_threshold: float = 0.7) -> Optional[Dict]:
        """Find matching tag using exact match or embedding search."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # First try exact match
            if tag_group:
                cur.execute("""
                    SELECT t.tag_name, t.group_name
                    FROM tags t
                    WHERE LOWER(t.tag_name) = LOWER(%s) AND t.group_name = %s
                """, (tag_text, tag_group))
            else:
                cur.execute("""
                    SELECT t.tag_name, t.group_name
                    FROM tags t
                    WHERE LOWER(t.tag_name) = LOWER(%s)
                """, (tag_text,))
            
            result = cur.fetchone()
            if result:
                return {
                    'tag_name': result[0],
                    'group_name': result[1],
                    'confidence': 1.0,
                    'method': 'exact_match'
                }
            
            # If no exact match, use embedding search
            tag_embedding = self.model.encode(tag_text).tolist()
            
            if tag_group:
                cur.execute("""
                    SELECT 
                        t.tag_name,
                        t.group_name,
                        1 - (t.embedding <=> %s::vector) as similarity
                    FROM tags t
                    WHERE t.group_name = %s
                        AND 1 - (t.embedding <=> %s::vector) > %s
                    ORDER BY t.embedding <=> %s::vector
                    LIMIT 1
                """, (tag_embedding, tag_group, tag_embedding, confidence_threshold, tag_embedding))
            else:
                cur.execute("""
                    SELECT 
                        t.tag_name,
                        t.group_name,
                        1 - (t.embedding <=> %s::vector) as similarity
                    FROM tags t
                    WHERE 1 - (t.embedding <=> %s::vector) > %s
                    ORDER BY t.embedding <=> %s::vector
                    LIMIT 1
                """, (tag_embedding, tag_embedding, confidence_threshold, tag_embedding))
            
            result = cur.fetchone()
            if result:
                return {
                    'tag_name': result[0],
                    'group_name': result[1],
                    'confidence': float(result[2]),
                    'method': 'embedding_match'
                }
            
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def map_tags_for_db(self, tags_dict: Dict[str, str]) -> Dict[str, str]:
        """Map extracted tags to database format."""
        mapped = {}
        
        for group, value in tags_dict.items():
            if not value:
                continue
                
            # Map group name
            db_group = GROUP_NAME_MAPPING.get(group, group)
            mapped[db_group] = value
        
        return mapped