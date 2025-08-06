# backend/test_api.py
"""
Test script to verify the API is working correctly.
Run this after starting the server with: python test_api.py
"""
import requests
import json
from time import sleep

# Configuration
BASE_URL = "http://localhost:8001"  # Adjust if needed
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password"


def test_health():
    """Test health endpoint."""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_login():
    """Test login with test user."""
    print("\n=== Testing Login ===")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Logged in as: {data['user']['email']}")
        return data.get('access_token')
    else:
        print(f"Login failed: {response.text}")
        return None


def test_chat(token=None, conversation_id=None):
    """Test chat endpoint."""
    print("\n=== Testing Chat ===")
    
    headers = {}
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    # Test messages
    messages = [
        "I want Italian vegetarian pasta with tomatoes",
        "Add basil and make it quick",
        "Actually exclude nuts too",
        "Show me Mexican tacos instead"
    ]
    
    current_conversation_id = conversation_id
    
    for message in messages:
        print(f"\n>>> User: {message}")
        
        request_data = {"message": message}
        if current_conversation_id:
            request_data["conversation_id"] = current_conversation_id
        
        response = requests.post(
            f"{BASE_URL}/chat/",
            json=request_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            current_conversation_id = data['conversation_id']
            
            print(f"<<< Assistant: {data['message'][:200]}...")
            print(f"    Conversation ID: {current_conversation_id}")
            print(f"    Recipes found: {len(data.get('recipes', []))}")
            
            if data.get('query_info'):
                info = data['query_info']
                print(f"    Query: {info['query']['query']}")
                print(f"    Include: {info['query']['include_ingredients']}")
                print(f"    Exclude: {info['query']['exclude_ingredients']}")
                print(f"    Is continuation: {info['is_continuation']}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            break
        
        # Small delay between messages
        sleep(1)
    
    return current_conversation_id


def test_conversations(token=None):
    """Test getting conversations."""
    print("\n=== Testing Get Conversations ===")
    
    headers = {}
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    response = requests.get(f"{BASE_URL}/chat/conversations", headers=headers)
    
    if response.status_code == 200:
        conversations = response.json()
        print(f"Found {len(conversations)} conversations")
        for conv in conversations[:3]:  # Show first 3
            print(f"  - ID: {conv['id']}, Title: {conv['title'][:50]}...")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Recipe Chat API Test Suite")
    print("=" * 60)
    
    # 1. Test health
    if not test_health():
        print("\n⚠️  Health check failed. Is the server running?")
        print("Start it with: uvicorn main:app --reload --port 8001")
        return
    
    # 2. Test login
    token = test_login()
    if not token:
        print("\n⚠️  Login failed. Check if test users are loaded in database.")
        print("The test user should be: test@example.com / password")
    
    # 3. Test chat
    conversation_id = test_chat(token)
    
    # 4. Test getting conversations
    if token:
        test_conversations(token)
    
    print("\n" + "=" * 60)
    print("✅ Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()