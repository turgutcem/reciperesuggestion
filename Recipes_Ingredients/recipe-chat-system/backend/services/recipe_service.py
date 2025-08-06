# backend/services/recipe_service.py
"""
Recipe Service for database operations.
Ports all recipe search functions from the notebook.
"""
from typing import List, Dict, Optional, Tuple
import logging

from database import get_recipe_connection
from schemas import RecipeQuery, TagsSemanticSchema
from prompts.system_prompts import GROUP_NAME_MAPPING, QUICK_TIME_TAGS
from services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class RecipeService:
    """Service for recipe database operations."""
    
    def __init__(self):
        """Initialize the service."""
        self.embedding_service = get_embedding_service()
    
    def resolve_ingredient_to_canonical(self, ingredient_name: str, confidence_threshold: float = 0.65) -> Optional[Dict]:
        """
        Find canonical ingredient from user input using exact match or embedding search.
        Ported from notebook lines ~850.
        
        Returns:
            Dict with canonical_id, canonical_name, and confidence
        """
        conn = get_recipe_connection()
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
            ingredient_embedding = self.embedding_service.encode(ingredient_name)
            
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
        """
        Get all variants of a canonical ingredient.
        Ported from notebook lines ~900.
        """
        conn = get_recipe_connection()
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
        """
        Find matching tag using exact match or embedding search.
        Ported from notebook lines ~1100.
        """
        conn = get_recipe_connection()
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
            tag_embedding = self.embedding_service.encode(tag_text)
            
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
        """Map extracted tags to database format. From notebook ~1200."""
        mapped = {}
        
        for group, value in tags_dict.items():
            if not value:
                continue
                
            # Map group name
            db_group = GROUP_NAME_MAPPING.get(group, group)
            mapped[db_group] = value
        
        return mapped
    
    def search_recipes_ingredients_first(self, recipe_query: RecipeQuery, tags: TagsSemanticSchema) -> Dict:
        """
        Search strategy: Ingredients + Critical Tags first, then rank by embedding.
        This is the main search function from notebook lines ~1500.
        """
        conn = get_recipe_connection()
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
            
            # Resolve ingredients
            include_variants = []
            exclude_variants = []
            
            for ing in recipe_query.include_ingredients:
                resolved = self.resolve_ingredient_to_canonical(ing)
                if resolved:
                    variants = self.get_all_ingredient_variants(resolved['canonical_id'])
                    include_variants.extend([v.lower() for v in variants])
            
            for ing in recipe_query.exclude_ingredients:
                resolved = self.resolve_ingredient_to_canonical(ing)
                if resolved:
                    variants = self.get_all_ingredient_variants(resolved['canonical_id'])
                    exclude_variants.extend([v.lower() for v in variants])
            
            # Build query: Start with ingredients and critical tags
            query_parts = ["SELECT id FROM recipes WHERE 1=1"]
            params = []
            
            # Must have ALL included ingredients
            for ing_group in recipe_query.include_ingredients:
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
            
            query = '\n'.join(query_parts)
            cur.execute(query, params)
            
            # Get all matching recipe IDs
            matching_ids = [row[0] for row in cur.fetchall()]
            
            if not matching_ids:
                return {
                    'recipe_ids': [],
                    'embedding_scores': {},
                    'total_found': 0
                }
            
            # Now get embedding scores for these recipes
            query_embedding = self.embedding_service.encode(recipe_query.query)
            
            # Get embeddings and calculate scores
            placeholders = ','.join(['%s'] * len(matching_ids))
            cur.execute(f"""
                SELECT id, 1 - (embedding <=> %s::vector) as similarity
                FROM recipes
                WHERE id IN ({placeholders})
                ORDER BY similarity DESC
            """, [query_embedding] + matching_ids)
            
            # Collect results
            results = []
            embedding_scores = {}
            for row in cur.fetchall():
                results.append(row[0])
                embedding_scores[row[0]] = float(row[1])
            
            # Return top N
            return {
                'recipe_ids': results[:recipe_query.count],
                'embedding_scores': embedding_scores,
                'total_found': len(results)
            }
            
        finally:
            cur.close()
            conn.close()
    
    def get_recipe_details(self, recipe_ids: List[int]) -> Dict[int, Dict]:
        """Get recipe details for display. From notebook ~1600."""
        if not recipe_ids:
            return {}
            
        conn = get_recipe_connection()
        cur = conn.cursor()
        try:
            placeholders = ','.join(['%s'] * len(recipe_ids))
            cur.execute(f"""
                SELECT 
                    id, name, description, ingredients, tags,
                    ingredients_raw, steps, servings, serving_size,
                    recipe_energy_kcal_per_serving,
                    recipe_fat_per_serving,
                    recipe_carbohydrates_per_serving,
                    recipe_proteins_per_serving
                FROM recipes
                WHERE id IN ({placeholders})
            """, recipe_ids)
            
            details = {}
            for row in cur.fetchall():
                details[row[0]] = {
                    'recipe_id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'ingredients': row[3],
                    'tags': row[4],
                    'ingredients_raw': row[5],
                    'steps': row[6],
                    'servings': row[7],
                    'serving_size': row[8],
                    'nutrition': {
                        'calories': round(row[9]) if row[9] else None,
                        'fat': round(row[10], 1) if row[10] else None,
                        'carbs': round(row[11], 1) if row[11] else None,
                        'protein': round(row[12], 1) if row[12] else None
                    }
                }
            return details
        finally:
            cur.close()
            conn.close()


# Singleton instance
_recipe_service = None

def get_recipe_service() -> RecipeService:
    """Get or create singleton recipe service instance."""
    global _recipe_service
    if _recipe_service is None:
        _recipe_service = RecipeService()
    return _recipe_service