#!/usr/bin/env python3
"""Update test users with working password hash"""
from sqlalchemy import text
from database import engine
from auth import get_password_hash

# Generate working hash for 'password'
new_hash = get_password_hash("password")
print(f"Updating test users with new password hash...")

with engine.connect() as conn:
    # Update test users
    result = conn.execute(
        text("UPDATE users SET password_hash = :hash WHERE email IN ('test@example.com', 'demo@example.com')"),
        {"hash": new_hash}
    )
    conn.commit()
    
    print(f"✓ Updated {result.rowcount} test users")
    
    # Verify
    result = conn.execute(
        text("SELECT email, password_hash FROM users WHERE email IN ('test@example.com', 'demo@example.com')")
    )
    for row in result:
        print(f"  - {row[0]}: {row[1][:20]}...")

print("\nNow run 'python init_db.py' again to verify password works!")