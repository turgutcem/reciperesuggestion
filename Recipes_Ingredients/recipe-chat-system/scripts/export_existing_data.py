#!/usr/bin/env python3
"""
Export existing recipe database to SQL files for Docker initialization.
Run this ONCE on your current local setup to generate the data files.
"""

import psycopg2
import psycopg2.extras
import json
import os
import math
from datetime import datetime
import sys

# Set UTF-8 encoding for output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configure your CURRENT database connection
# This connects to YOUR EXISTING local PostgreSQL on port 5432
CURRENT_DB_CONFIG = {
    "dbname": "recipes_db",
    "user": "postgres",
    "password": "turgutcem",  # Your current password
    "host": "localhost",
    "port": 5432,  # Your existing PostgreSQL
    "options": "-c client_encoding=utf8"  # Force UTF-8 encoding
}

OUTPUT_DIR = "database"  # This will be created relative to script location

def create_output_dir():
    """Create output directory if it doesn't exist."""
    output_path = os.path.join('..', OUTPUT_DIR)  # Go up one level to find database/
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    return output_path

def escape_string(value):
    """Properly escape strings for SQL."""
    if value is None:
        return 'NULL'
    # Convert to string if not already
    if not isinstance(value, str):
        value = str(value)
    # Replace single quotes with double quotes
    value = value.replace("'", "''")
    # Handle any backslashes
    value = value.replace("\\", "\\\\")
    return f"'{value}'"

def array_to_sql(arr):
    """Convert Python array to PostgreSQL array literal."""
    if arr is None or len(arr) == 0:
        return 'NULL'
    # Format as PostgreSQL array
    escaped_items = [escape_string(item).strip("'") for item in arr]
    return "ARRAY[" + ",".join([f"'{item}'" for item in escaped_items]) + "]::text[]"

def jsonb_to_sql(data):
    """Convert Python dict/list to PostgreSQL JSONB literal."""
    if data is None:
        return 'NULL'
    # Convert to JSON string and escape for SQL
    json_str = json.dumps(data)
    return escape_string(json_str) + "::jsonb"

def vector_to_sql(vector_bytes, dimension=384):
    """Convert pgvector bytes to SQL format with proper dimensions."""
    if vector_bytes is None:
        return 'NULL'
    # pgvector stores as string representation
    # Handle potential encoding issues
    try:
        if isinstance(vector_bytes, str):
            return f"'{vector_bytes}'::vector({dimension})"
        else:
            # If it's bytes, decode it
            vector_str = vector_bytes.decode('utf-8') if isinstance(vector_bytes, bytes) else str(vector_bytes)
            return f"'{vector_str}'::vector({dimension})"
    except:
        # If all else fails, return NULL
        return 'NULL'

def export_recipes(conn, limit=None, output_path='database'):
    """Export recipes table to SQL."""
    print("Exporting recipes...")
    cur = conn.cursor()
    
    # Get total count
    cur.execute("SELECT COUNT(*) FROM recipes")
    total_count = cur.fetchone()[0]
    print(f"Total recipes: {total_count}")
    
    # Fetch recipes
    query = "SELECT * FROM recipes"
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    
    output_file = os.path.join(output_path, '03_recipes_data.sql')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- Recipe data export\n")
        f.write(f"-- Exported on: {datetime.now()}\n")
        f.write(f"-- Total recipes: {total_count}\n\n")
        
        # Write INSERT statements in batches
        batch_size = 100
        batch_count = 0
        
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
                
            for row in rows:
                values = []
                for i, value in enumerate(row):
                    col_name = columns[i]
                    
                    # Handle different column types based on your actual schema
                    if col_name == 'embedding':
                        values.append(vector_to_sql(value, 384))  # Specify dimension
                    elif col_name in ['amounts', 'amount_gram']:  # JSONB columns
                        values.append(jsonb_to_sql(value))
                    elif col_name in ['tags', 'ingredients']:  # Array columns
                        values.append(array_to_sql(value))
                    elif isinstance(value, str):
                        values.append(escape_string(value))
                    elif value is None:
                        values.append('NULL')
                    elif isinstance(value, float):
                        # Handle NaN values
                        if math.isnan(value):
                            values.append('NULL')
                        else:
                            values.append(str(value))
                    else:
                        values.append(str(value))
                
                insert_sql = f"INSERT INTO recipes ({','.join(columns)}) VALUES ({','.join(values)}) ON CONFLICT (id) DO NOTHING;"
                f.write(insert_sql + "\n")
            
            batch_count += 1
            print(f"  Exported batch {batch_count} ({batch_count * batch_size} recipes)")
    
    cur.close()
    print(f"✓ Exported {min(limit or total_count, total_count)} recipes")

def export_ingredients(conn, output_path='database'):
    """Export ingredients and variants."""
    print("\nExporting ingredients...")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Export ingredients
    cur.execute("SELECT * FROM ingredients ORDER BY id")
    ingredients = cur.fetchall()
    
    output_file = os.path.join(output_path, '04_ingredients_data.sql')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- Ingredients data export\n")
        f.write(f"-- Exported on: {datetime.now()}\n\n")
        
        for ing in ingredients:
            values = [
                str(ing['id']),
                escape_string(ing['canonical']),
                vector_to_sql(ing['embedding'], 384)  # Specify dimension
            ]
            f.write(f"INSERT INTO ingredients (id, canonical, embedding) VALUES ({','.join(values)}) ON CONFLICT (id) DO NOTHING;\n")
        
        # Reset sequence
        f.write("\n-- Reset ingredient ID sequence\n")
        f.write("SELECT setval('ingredients_id_seq', (SELECT MAX(id) FROM ingredients));\n\n")
        
        # Export variants
        f.write("\n-- Ingredient variants\n")
        cur.execute("SELECT * FROM ingredient_variants ORDER BY canonical_id, variant")
        variants = cur.fetchall()
        
        for var in variants:
            f.write(f"INSERT INTO ingredient_variants (canonical_id, variant) VALUES ({var['canonical_id']}, {escape_string(var['variant'])}) ON CONFLICT (canonical_id, variant) DO NOTHING;\n")
    
    cur.close()
    print(f"✓ Exported {len(ingredients)} ingredients with variants")

def export_tags(conn, output_path='database'):
    """Export tags and tag groups."""
    print("\nExporting tags...")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Export tag groups first
    cur.execute("SELECT * FROM tag_groups ORDER BY group_name")
    groups = cur.fetchall()
    
    output_file = os.path.join(output_path, '05_tags_data.sql')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- Tags data export\n")
        f.write(f"-- Exported on: {datetime.now()}\n\n")
        
        f.write("-- Tag groups\n")
        for group in groups:
            values = [
                escape_string(group['group_name']),
                str(group['member_count']),
                vector_to_sql(group['embedding'], 384)  # Specify dimension
            ]
            f.write(f"INSERT INTO tag_groups (group_name, member_count, embedding) VALUES ({','.join(values)}) ON CONFLICT (group_name) DO NOTHING;\n")
        
        # Export tags
        f.write("\n-- Tags\n")
        cur.execute("SELECT * FROM tags ORDER BY group_name, tag_name")
        tags = cur.fetchall()
        
        for tag in tags:
            values = [
                escape_string(tag['tag_name']),
                escape_string(tag['group_name']),
                vector_to_sql(tag['embedding'], 384)  # Specify dimension
            ]
            f.write(f"INSERT INTO tags (tag_name, group_name, embedding) VALUES ({','.join(values)}) ON CONFLICT (tag_name) DO NOTHING;\n")
    
    cur.close()
    print(f"✓ Exported {len(groups)} tag groups and {len(tags)} tags")

def create_test_user_data(output_path='database'):
    """Create sample user data for testing."""
    print("\nCreating test user data...")
    
    output_file = os.path.join(output_path, '06_test_users.sql')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- Test user data\n")
        f.write(f"-- Generated on: {datetime.now()}\n\n")
        
        # Create test users (password is 'password' for all)
        # Using bcrypt hash for 'password'
        test_password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/Lewvfmf0ma/SXfYFu'
        
        test_users = [
            ('test@example.com', 'Test User'),
            ('demo@example.com', 'Demo User'),
        ]
        
        for email, name in test_users:
            f.write(f"INSERT INTO users (email, password_hash, name) VALUES ({escape_string(email)}, {escape_string(test_password_hash)}, {escape_string(name)}) ON CONFLICT (email) DO NOTHING;\n")
    
    print("✓ Created test user data (password: 'password' for all test users)")

def main():
    """Main export function."""
    print("Recipe Database Export Tool")
    print("=" * 50)
    
    # Get the output path (go up one directory to find database/)
    output_path = create_output_dir()
    
    try:
        # Connect to current database
        print(f"Connecting to database at {CURRENT_DB_CONFIG['host']}:{CURRENT_DB_CONFIG['port']}")
        conn = psycopg2.connect(**CURRENT_DB_CONFIG)
        conn.set_client_encoding('UTF8')  # Ensure UTF-8 encoding
        
        # Ask user about recipe limit for testing
        response = input("\nExport ALL recipes? (y/n, default=n, exports 1000 for testing): ").strip().lower()
        recipe_limit = None if response == 'y' else 1000
        
        # Export all data
        export_recipes(conn, limit=recipe_limit, output_path=output_path)
        export_ingredients(conn, output_path=output_path)
        export_tags(conn, output_path=output_path)
        create_test_user_data(output_path=output_path)
        
        print("\n✓ Export complete!")
        print(f"Files created in '{output_path}' directory")
        print("\nNext steps:")
        print("1. Go back to recipe-chat-system directory")
        print("2. Run: docker-compose up")
        print("3. Database will be automatically initialized")
        
    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running")
        print("2. Database credentials are correct")
        print("3. The recipes_db database exists")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()