#!/usr/bin/env python3
"""Test password hashing"""
from auth import get_password_hash, verify_password

# Generate new hash for 'password'
new_hash = get_password_hash("password")
print(f"New hash: {new_hash}")

# Test with SQL hash
sql_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/Lewvfmf0ma/SXfYFu"
print(f"SQL hash: {sql_hash}")

# Test verification
print(f"\nVerify 'password' with new hash: {verify_password('password', new_hash)}")
print(f"Verify 'password' with SQL hash: {verify_password('password', sql_hash)}")

# Show hash format
print(f"\nNew hash format: {new_hash[:7]}")
print(f"SQL hash format: {sql_hash[:7]}")