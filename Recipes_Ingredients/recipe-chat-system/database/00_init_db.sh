#!/bin/bash
# Database initialization script with automatic file download
# This runs automatically when PostgreSQL container starts

set -e

echo "Starting database initialization..."

# Configuration - GitHub Release URL for turgutcem/reciperesuggestion
GITHUB_ARCHIVE_URL="https://github.com/turgutcem/reciperesuggestion/releases/download/v1.0-data/recipe_database_files.zip"
ARCHIVE_NAME="recipe_database_files.zip"
DATA_FILES=(
    "03_recipes_data.sql"
    "04_ingredients_data.sql" 
    "05_tags_data.sql"
    "06_test_users.sql"
)

# Function to download and extract archive if files are missing
download_and_extract_if_missing() {
    local need_download=false
    
    # Check if any data file is missing
    for file in "${DATA_FILES[@]}"; do
        if [ ! -f "/docker-entrypoint-initdb.d/$file" ]; then
            need_download=true
            echo "Missing file: $file"
            break
        fi
    done
    
    if [ "$need_download" = true ]; then
        echo "📥 Data files missing. Downloading archive from GitHub..."
        cd /docker-entrypoint-initdb.d
        
        # Download archive
        echo "Downloading from: $GITHUB_ARCHIVE_URL"
        wget -q --show-progress -O "$ARCHIVE_NAME" "$GITHUB_ARCHIVE_URL" || {
            echo "❌ Failed to download archive from $GITHUB_ARCHIVE_URL"
            echo "Please check if the release exists at: https://github.com/turgutcem/reciperesuggestion/releases"
            return 1
        }
        echo "✅ Downloaded archive successfully"
        
        # Extract ZIP archive
        echo "📦 Extracting ZIP archive..."
        unzip -o "$ARCHIVE_NAME"
        echo "✅ Extracted data files successfully"
        
        # Remove archive after extraction to save space
        rm "$ARCHIVE_NAME"
        echo "🗑️ Cleaned up archive file"
    else
        echo "✓ All data files already exist, skipping download"
    fi
}

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

# Download and extract data files if missing
echo ""
echo "Checking for data files..."
download_and_extract_if_missing

# Change to the init directory for running SQL files
cd /docker-entrypoint-initdb.d

echo ""
echo "Starting database initialization..."

# 1. Create schema and tables
run_sql_file "01_schema.sql"

# 2. Create indexes (if separate file exists)
if [ -f "02_indexes.sql" ]; then
    run_sql_file "02_indexes.sql"
fi

# 3. Load recipe data
if [ -f "03_recipes_data.sql" ]; then
    echo "Loading recipe data (this may take a few minutes)..."
    EXISTING_RECIPES=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM recipes;" 2>/dev/null || echo "0")
    if [ "$EXISTING_RECIPES" -eq 0 ]; then
        run_sql_file "03_recipes_data.sql"
        echo "✓ Loaded recipes successfully"
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
        echo "✓ Loaded ingredients successfully"
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
        echo "✓ Loaded tags successfully"
    else
        echo "⚠ Tags already exist, skipping to avoid duplicates"
    fi
fi

# 6. Load test users
if [ -f "06_test_users.sql" ]; then
    echo "Loading test users..."
    EXISTING_USERS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM users WHERE email IN ('test@example.com', 'demo@example.com');" 2>/dev/null || echo "0")
    if [ "$EXISTING_USERS" -eq 0 ]; then
        run_sql_file "06_test_users.sql"
        echo "✓ Loaded test users (password: 'password' for all)"
    else
        echo "⚠ Test users already exist, skipping"
    fi
fi

# 7. Create vector indexes AFTER data is loaded
echo "Creating vector indexes..."
run_sql_file "07_vector_indexes.sql"

# Verify data was loaded
echo ""
echo "==============================================="
echo "Verifying database initialization..."
echo "==============================================="
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 
        'Recipes: ' || COUNT(*) as count FROM recipes
    UNION ALL
    SELECT 'Ingredients: ' || COUNT(*) FROM ingredients
    UNION ALL
    SELECT 'Tags: ' || COUNT(*) FROM tags
    UNION ALL
    SELECT 'Users: ' || COUNT(*) FROM users;
EOSQL

echo ""
echo "==============================================="
echo "✅ Database initialization complete!"
echo "==============================================="
echo ""
echo "Test users created:"
echo "  - Email: test@example.com"
echo "  - Password: password"
echo ""
echo "You can now access the application!"
echo "==============================================="