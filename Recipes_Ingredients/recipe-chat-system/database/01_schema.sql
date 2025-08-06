-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 
-- RECIPE TABLES 

-- Recipes table (using standard array syntax)
CREATE TABLE IF NOT EXISTS recipes (
    id SERIAL PRIMARY KEY,
    recipe_id BIGINT,
    name TEXT,
    description TEXT,
    ingredients_raw TEXT,
    steps TEXT,
    servings DOUBLE PRECISION,
    serving_size TEXT,
    tags TEXT[],
    ingredients TEXT[],
    amounts JSONB,
    amount_gram JSONB,
    serving_size_numeric DOUBLE PRECISION,
    total_recipe_weight DOUBLE PRECISION,
    recipe_energy_kcal_per100g DOUBLE PRECISION,
    recipe_energy_kcal_per_serving DOUBLE PRECISION,
    embedding vector(384),
    recipe_fat_per_serving DOUBLE PRECISION,
    recipe_energy_per100g DOUBLE PRECISION,
    recipe_carbohydrates_per100g DOUBLE PRECISION,
    recipe_proteins_per100g DOUBLE PRECISION,
    recipe_fat_per100g DOUBLE PRECISION,
    recipe_energy_per_serving DOUBLE PRECISION,
    recipe_carbohydrates_per_serving DOUBLE PRECISION,
    recipe_proteins_per_serving DOUBLE PRECISION
);

-- Ingredients table
CREATE TABLE IF NOT EXISTS ingredients (
    id SERIAL PRIMARY KEY,
    canonical TEXT NOT NULL UNIQUE,
    embedding vector(384)
);

-- Ingredient variants table
CREATE TABLE IF NOT EXISTS ingredient_variants (
    canonical_id INTEGER NOT NULL,
    variant TEXT NOT NULL,
    PRIMARY KEY (canonical_id, variant),
    FOREIGN KEY (canonical_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

-- Tag groups table
CREATE TABLE IF NOT EXISTS tag_groups (
    group_name TEXT PRIMARY KEY,
    member_count INTEGER NOT NULL,
    embedding vector(384)
);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    tag_name TEXT PRIMARY KEY,
    group_name TEXT NOT NULL,
    embedding vector(384),
    FOREIGN KEY (group_name) REFERENCES tag_groups(group_name)
);

-- 
-- USER MANAGEMENT TABLES
-- 

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Messages table with extracted data storage
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    is_user BOOLEAN NOT NULL,
    extracted_query JSONB,  -- Store RecipeQuery object
    extracted_tags JSONB,   -- Store TagsSemanticSchema object
    search_results JSONB,   -- Store search results metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- 
-- INDEXES FOR PERFORMANCE
-- 

-- Recipe search indexes
-- NOTE: Vector indexes will be created AFTER data is loaded
-- CREATE INDEX IF NOT EXISTS idx_recipes_embedding ON recipes USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_recipes_ingredients ON recipes USING gin (ingredients);
CREATE INDEX IF NOT EXISTS idx_recipes_tags ON recipes USING gin (tags);

-- Ingredient indexes
-- CREATE INDEX IF NOT EXISTS idx_ingredients_embedding ON ingredients USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_ingredient_variants_canonical ON ingredient_variants(canonical_id);
CREATE INDEX IF NOT EXISTS idx_ingredient_variants_variant ON ingredient_variants(variant);

-- Tag indexes
-- CREATE INDEX IF NOT EXISTS idx_tags_embedding ON tags USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_tags_group ON tags(group_name);

-- User management indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 
-- TRIGGERS AND FUNCTIONS
-- 

-- Automatically update conversation timestamp when new message is added
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists before creating
DROP TRIGGER IF EXISTS update_conversation_on_new_message ON messages;

CREATE TRIGGER update_conversation_on_new_message
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION update_conversation_timestamp();