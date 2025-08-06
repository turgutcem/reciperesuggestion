-- Vector indexes - created AFTER data is loaded
-- This file should run last to avoid "column does not have dimensions" error

-- Create vector indexes for similarity search
-- Using lists parameter for better performance on larger datasets
CREATE INDEX IF NOT EXISTS idx_recipes_embedding 
    ON recipes USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_ingredients_embedding 
    ON ingredients USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_tags_embedding 
    ON tags USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Also create index for tag_groups since it has embeddings too
CREATE INDEX IF NOT EXISTS idx_tag_groups_embedding 
    ON tag_groups USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Verify indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('recipes', 'ingredients', 'tags', 'tag_groups')
    AND indexname LIKE '%embedding%'
ORDER BY tablename, indexname;

-- Show index sizes for monitoring
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE tablename IN ('recipes', 'ingredients', 'tags', 'tag_groups')
    AND indexname LIKE '%embedding%'
ORDER BY pg_relation_size(indexname::regclass) DESC;