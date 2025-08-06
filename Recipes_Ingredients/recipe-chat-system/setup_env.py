#!/usr/bin/env python3
"""
Setup script for new users to configure environment variables.
Run this once after cloning the repository.
"""

import os
import secrets
import shutil

def create_env_file():
    """Create .env file from template with user input."""
    
    print("Recipe Chat System - Environment Setup")
    print("-" * 50)
    
    # Check if .env already exists
    if os.path.exists('.env'):
        response = input(".env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return
    
    # Copy template
    if os.path.exists('.env.example'):
        shutil.copy('.env.example', '.env')
        print("Created .env from template")
    else:
        print(".env.example not found")
        return
    
    print("\nConfigure your database settings:")
    print("   (Press Enter to keep default values)")
    
    # Get user inputs
    configs = {}
    
    # Database settings
    configs['DB_HOST'] = input("Database host [postgres]: ") or "postgres"
    configs['DB_PORT'] = input("Database port [5432]: ") or "5432"  
    configs['DB_NAME'] = input("Database name [recipes_db]: ") or "recipes_db"
    configs['DB_USER'] = input("Database user [postgres]: ") or "postgres"
    
    # Password is required
    while True:
        password = input("Database password (required): ")
        if password:
            configs['DB_PASSWORD'] = password
            break
        print("Password is required!")
    
    # Generate secret key
    configs['SECRET_KEY'] = secrets.token_urlsafe(32)
    print("Generated secure secret key")
    
    # Optional configs
    configs['OLLAMA_HOST'] = input("Ollama host [ollama]: ") or "ollama"
    
    # Update .env file
    with open('.env', 'r') as f:
        content = f.read()
    
    for key, value in configs.items():
        content = content.replace(f"{key}=your_database_password_here", f"{key}={value}")
        content = content.replace(f"{key}=change-this-to-a-secure-random-string", f"{key}={value}")
        content = content.replace(f"{key}=postgres", f"{key}={value}")
        content = content.replace(f"{key}=ollama", f"{key}={value}")
        content = content.replace(f"{key}=recipes_db", f"{key}={value}")
        content = content.replace(f"{key}=5432", f"{key}={value}")
    
    with open('.env', 'w') as f:
        f.write(content)
    
    print("\nEnvironment setup complete!")
    print("Your settings are saved in .env file")
    print("You can now run: docker-compose up --build")
    
if __name__ == "__main__":
    create_env_file()