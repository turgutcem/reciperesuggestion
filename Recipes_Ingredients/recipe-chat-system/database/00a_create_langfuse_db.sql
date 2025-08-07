-- database/00a_create_langfuse_db.sql
-- Creates Langfuse database for observability (optional feature)
-- This runs before the main init script

-- Create the Langfuse database if it doesn't exist
-- Note: CREATE DATABASE cannot be executed in a transaction block,
-- so this might fail if the database already exists, which is fine
CREATE DATABASE langfuse_db;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE langfuse_db TO postgres;