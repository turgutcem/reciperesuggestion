#!/usr/bin/env python3
"""
Verify database tables and test user.
Tables should already exist from SQL scripts.
"""
import sys
import logging
from sqlalchemy import text

from database import engine, SessionLocal
from models import User, Conversation, Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_existing_tables():
    """Check which tables already exist."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        
        existing_tables = [row[0] for row in result]
        logger.info(f"Existing tables: {existing_tables}")
        return existing_tables

def verify_all_tables():
    """Verify that all required tables exist."""
    required_tables = {
        'Recipe tables': ['recipes', 'ingredients', 'ingredient_variants', 'tags', 'tag_groups'],
        'User tables': ['users', 'conversations', 'messages']
    }
    
    existing = check_existing_tables()
    all_good = True
    
    for category, tables in required_tables.items():
        logger.info(f"\nChecking {category}:")
        for table in tables:
            if table in existing:
                logger.info(f"  ✓ {table}")
            else:
                logger.error(f"  ✗ {table} - MISSING!")
                all_good = False
    
    return all_good

def check_test_users():
    """Check if test users exist from SQL scripts."""
    db = SessionLocal()
    try:
        # Import auth here to avoid circular imports
        from auth import verify_password
        
        # Check for test users created by 06_test_users.sql
        test_emails = ["test@example.com", "demo@example.com"]
        
        for email in test_emails:
            user = db.query(User).filter(User.email == email).first()
            if user:
                logger.info(f"✓ Test user found: {email}")
                # Verify password works
                if verify_password("password", user.password_hash):
                    logger.info(f"  ✓ Password verification works")
                else:
                    logger.warning(f"  ✗ Password verification failed - hash mismatch")
            else:
                logger.warning(f"✗ Test user not found: {email}")
                logger.info("  Run the SQL scripts in database/ folder to create test users")
        
    except Exception as e:
        logger.error(f"Error checking test users: {e}")
    finally:
        db.close()

def count_recipes():
    """Count recipes to verify data is loaded."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM recipes"))
        count = result.scalar()
        logger.info(f"\n✓ Found {count} recipes in database")

def main():
    """Verify database setup."""
    logger.info("Verifying Recipe Chat database setup...")
    logger.info("=" * 60)
    
    # Check all tables exist
    if not verify_all_tables():
        logger.error("\nSome tables are missing!")
        logger.error("Please ensure all SQL scripts in database/ have been run")
        sys.exit(1)
    
    # Check test users
    logger.info("\nChecking test users...")
    check_test_users()
    
    # Count recipes
    count_recipes()
    
    logger.info("\n" + "="*60)
    logger.info("✓ Database verification complete!")
    logger.info("\nTest users (password for all: 'password'):")
    logger.info("  - test@example.com")
    logger.info("  - demo@example.com")

if __name__ == "__main__":
    main()