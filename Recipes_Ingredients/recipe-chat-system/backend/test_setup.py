#!/usr/bin/env python3
"""
Quick script to test the core setup
"""
import requests
import sys

def test_api():
    """Test if API is running"""
    try:
        response = requests.get("http://localhost:8001")  # Changed to 8001
        print(f"✓ API is running: {response.json()}")
        
        health = requests.get("http://localhost:8001/health")  # Changed to 8001
        health_data = health.json()
        print(f"✓ Health check: {health_data}")
        
        # Check individual services
        services = health_data.get("services", {})
        for service, status in services.items():
            icon = "✓" if status in ["running", "healthy"] else "✗"
            print(f"  {icon} {service}: {status}")
        
        return True
    except Exception as e:
        print(f"✗ API test failed: {e}")
        return False

def test_ollama():
    """Test if Ollama is accessible"""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        print(f"✓ Ollama is running")
        
        # Check if model is loaded
        models = response.json().get("models", [])
        if any("llama3.2" in model.get("name", "") for model in models):
            print("  ✓ Llama 3.2 model is loaded")
        else:
            print("  ✗ Llama 3.2 model not found - run: docker exec -it recipe_ollama ollama pull llama3.2:3b")
        
        return True
    except Exception as e:
        print(f"✗ Ollama test failed: {e}")
        return False

def test_database():
    """Test if database is accessible"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            "postgresql://postgres:postgres@localhost:5433/recipes_db"  # Changed to 5433
        )
        cur = conn.cursor()
        
        # Check for recipe tables
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('recipes', 'ingredients', 'tags', 'users', 'conversations', 'messages')
        """)
        table_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        print("✓ Database is accessible")
        print(f"  ✓ Found {table_count} tables")
        
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Recipe Chat Backend Setup...\n")
    
    tests = [
        ("API", test_api),
        ("Ollama", test_ollama),
        ("Database", test_database)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nTesting {name}...")
        results.append(test_func())
    
    print("\n" + "="*50)
    if all(results):
        print("✓ All tests passed!")
        print("\nNext step: Initialize database tables")
        print("Run: python backend/init_db.py")
    else:
        print("✗ Some tests failed. Check the output above.")
        sys.exit(1)