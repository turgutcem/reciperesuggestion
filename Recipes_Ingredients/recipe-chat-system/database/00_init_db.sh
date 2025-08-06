#!/bin/bash
# Database initialization script
# This runs automatically when PostgreSQL container starts

set -e

echo "Starting database initialization..."

# Function to run SQL file
run_sql_file() {
    local file=$1
    if [ -f "$file" ]; then
        echo "Running $file..."
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$file"
        echo "✓ Completed $file"
    else
        echo "⚠ Warning: $file not found, skipping..."
    fi
}

# Function to run SQL file that might have duplicates
run_sql_file_allow_duplicates() {
    local file=$1
    if [ -f "$file" ]; then
        echo "Running $file (ignoring duplicates)..."
        psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$file" || true
        echo "✓ Completed $file (with possible duplicates ignored)"
    else
        echo "⚠ Warning: $file not found, skipping..."
    fi
}

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
    echo "Waiting for PostgreSQL to be ready..."
    sleep 2
done

echo "PostgreSQL is ready. Checking if database is already initialized..."

# Check if the database is already initialized
TABLES_EXIST=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('recipes', 'ingredients', 'tags', 'users');" 2>/dev/null || echo "0")

if [ "$TABLES_EXIST" -gt 0 ]; then
    echo "Database already initialized. Checking data..."
    
    # Check if data exists
    RECIPE_COUNT=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM recipes;" 2>/dev/null || echo "0")
    
    if [ "$RECIPE_COUNT" -gt 0 ]; then
        echo "✓ Database already contains data:"
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t <<-EOSQL
            SELECT 
                'Recipes: ' || COUNT(*) FROM recipes
            UNION ALL
            SELECT 'Ingredients: ' || COUNT(*) FROM ingredients
            UNION ALL
            SELECT 'Tags: ' || COUNT(*) FROM tags
            UNION ALL
            SELECT 'Users: ' || COUNT(*) FROM users;
EOSQL
        echo "✓ Skipping re-initialization to avoid duplicates."
        exit 0
    else
        echo "Tables exist but no data found. Loading data..."
    fi
else
    echo "Fresh database detected. Running full initialization..."
fi

# Run initialization scripts in order
cd /docker-entrypoint-initdb.d

# 1. Create schema and tables
run_sql_file "01_schema.sql"

# 2. Create indexes (if separate)
run_sql_file "02_indexes.sql"

# For data files, we need to handle potential duplicates differently
# since Docker might restart the container and re-run these

# 3. Load recipe data (allow duplicates to be ignored)
if [ -f "03_recipes_data.sql" ]; then
    echo "Loading recipe data..."
    # First, check if recipes already exist
    EXISTING_RECIPES=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM recipes;" 2>/dev/null || echo "0")
    if [ "$EXISTING_RECIPES" -eq 0 ]; then
        run_sql_file "03_recipes_data.sql"
    else
        echo "⚠ Recipes already exist, skipping to avoid duplicates"
    fi
fi

# 4. Load ingredients and variants
if [ -f "04_ingredients_data.sql" ]; then
    echo "Loading ingredients data..."
    EXISTING_INGREDIENTS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM ingredients;" 2>/dev/null || echo "0")
    if [ "$EXISTING_INGREDIENTS" -eq 0 ]; then
        run_sql_file "04_ingredients_data.sql"
    else
        echo "⚠ Ingredients already exist, skipping to avoid duplicates"
    fi
fi

# 5. Load tags
if [ -f "05_tags_data.sql" ]; then
    echo "Loading tags data..."
    EXISTING_TAGS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM tags;" 2>/dev/null || echo "0")
    if [ "$EXISTING_TAGS" -eq 0 ]; then
        run_sql_file "05_tags_data.sql"
    else
        echo "⚠ Tags already exist, skipping to avoid duplicates"
    fi
fi

# 6. Load test users (check for existing users first)
if [ -f "06_test_users.sql" ]; then
    echo "Loading test users..."
    EXISTING_USERS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM users WHERE email IN ('test@example.com', 'demo@example.com');" 2>/dev/null || echo "0")
    if [ "$EXISTING_USERS" -eq 0 ]; then
        run_sql_file "06_test_users.sql"
    else
        echo "⚠ Test users already exist, skipping"
    fi
fi

# 7. Create vector indexes AFTER data is loaded
run_sql_file "07_vector_indexes.sql"

# Verify data was loaded
echo ""
echo "Verifying data load..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 
        (SELECT COUNT(*) FROM recipes) as recipe_count,
        (SELECT COUNT(*) FROM ingredients) as ingredient_count,
        (SELECT COUNT(*) FROM tags) as tag_count,
        (SELECT COUNT(*) FROM users) as user_count;
EOSQL

echo ""
echo "✓ Database initialization complete!"