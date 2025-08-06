# frontend/app.py
"""
Streamlit frontend for Recipe Chat System.
"""
import streamlit as st
import requests
from typing import Optional, Dict, List
import json
import os
import ast

# Configuration
API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8001")  # Backend API URL

# Page config
st.set_page_config(
    page_title="Recipe Chat Assistant",
    page_icon="🍳",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    /* Custom styles for better appearance */
    .stExpander {
        background-color: #f8f9fa;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    
    /* Make nutrition info stand out */
    .nutrition-info {
        background-color: #e9ecef;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def parse_list_string(list_string):
    """
    Safely parse a string representation of a Python list.
    
    Args:
        list_string: String like "['item1', 'item2']" or regular string
    
    Returns:
        List of items or original string if parsing fails
    """
    if not list_string:
        return []
    
    # If it's already a list, return it
    if isinstance(list_string, list):
        return list_string
    
    # Try to parse as Python literal
    try:
        result = ast.literal_eval(list_string)
        if isinstance(result, list):
            return result
        return [str(result)]
    except (ValueError, SyntaxError):
        # If it fails, return as single item or try to split by common patterns
        # Check if it looks like steps separated by numbers
        if '. ' in list_string and any(f"{i}. " in list_string for i in range(1, 10)):
            # Split by step numbers
            import re
            steps = re.split(r'\d+\.\s+', list_string)
            return [s.strip() for s in steps if s.strip()]
        return [list_string]


class RecipeAPIClient:
    """API client for backend communication."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def login(self, email: str, password: str) -> Optional[Dict]:
        """Login to the API."""
        try:
            response = requests.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Login error: {e}")
            return None
    
    def register(self, email: str, password: str, name: str) -> Optional[Dict]:
        """Register a new user."""
        try:
            response = requests.post(
                f"{self.base_url}/auth/register",
                json={"email": email, "password": password, "name": name}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Registration error: {e}")
            return None
    
    def send_message(self, message: str, conversation_id: Optional[int] = None, token: Optional[str] = None) -> Optional[Dict]:
        """Send a chat message."""
        headers = {}
        if token:
            headers['Authorization'] = f"Bearer {token}"
        
        data = {"message": message}
        if conversation_id:
            data["conversation_id"] = conversation_id
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/",
                json=data,
                headers=headers
            )
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Chat error: {response.text}")
                return None
        except Exception as e:
            st.error(f"Chat error: {e}")
            return None
    
    def get_conversations(self, token: str) -> List[Dict]:
        """Get user's conversations."""
        headers = {'Authorization': f"Bearer {token}"}
        try:
            response = requests.get(
                f"{self.base_url}/chat/conversations",
                headers=headers
            )
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []
    
    def get_conversation_messages(self, conversation_id: int, token: str) -> List[Dict]:
        """Get messages for a specific conversation with recipe details."""
        headers = {'Authorization': f"Bearer {token}"}
        try:
            response = requests.get(
                f"{self.base_url}/chat/conversations/{conversation_id}/messages",
                headers=headers,
                params={'include_recipes': True}  # Request recipe details
            )
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []
    
    def check_health(self) -> bool:
        """Check if API is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False


# Initialize session state
if 'api_client' not in st.session_state:
    st.session_state.api_client = RecipeAPIClient(API_BASE_URL)

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = None

if 'user' not in st.session_state:
    st.session_state.user = None

if 'token' not in st.session_state:
    st.session_state.token = None


def render_sidebar():
    """Render the sidebar with auth and conversation list."""
    with st.sidebar:
        st.title("🍳 Recipe Chat")
        
        # Check API health
        if not st.session_state.api_client.check_health():
            st.error("⚠️ Backend API is not running!")
            st.info("Start it with: `uvicorn main:app --reload --port 8001`")
            return
        
        # Authentication section
        if not st.session_state.user:
            st.subheader("Login")
            
            tab1, tab2 = st.tabs(["Login", "Register"])
            
            with tab1:
                email = st.text_input("Email", value="test@example.com", key="login_email")
                password = st.text_input("Password", type="password", value="password", key="login_password")
                
                if st.button("Login", use_container_width=True):
                    result = st.session_state.api_client.login(email, password)
                    if result:
                        st.session_state.user = result['user']
                        st.session_state.token = result['access_token']
                        st.success(f"Welcome, {result['user']['name'] or result['user']['email']}!")
                        st.rerun()
                    else:
                        st.error("Login failed. Check your credentials.")
            
            with tab2:
                reg_name = st.text_input("Name", key="reg_name")
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input("Password", type="password", key="reg_password")
                
                if st.button("Register", use_container_width=True):
                    if reg_email and reg_password:
                        result = st.session_state.api_client.register(reg_email, reg_password, reg_name)
                        if result:
                            st.success("Registration successful! Please login.")
                        else:
                            st.error("Registration failed. Email might already exist.")
        else:
            # User is logged in
            st.success(f"👤 {st.session_state.user['email']}")
            
            if st.button("Logout", use_container_width=True):
                st.session_state.user = None
                st.session_state.token = None
                st.session_state.messages = []
                st.session_state.conversation_id = None
                st.rerun()
            
            st.divider()
            
            # Conversation controls
            st.subheader("Conversations")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("New Chat", use_container_width=True):
                    st.session_state.messages = []
                    st.session_state.conversation_id = None
                    st.rerun()
            
            with col2:
                if st.button("Clear History", use_container_width=True):
                    st.session_state.messages = []
                    st.rerun()
            
            # Show recent conversations
            if st.session_state.token:
                conversations = st.session_state.api_client.get_conversations(st.session_state.token)
                if conversations:
                    st.caption("Recent chats:")
                    for conv in conversations[:5]:
                        if st.button(f"💬 {conv['title'][:30]}...", key=f"conv_{conv['id']}", use_container_width=True):
                            # Load the conversation messages WITH recipes
                            messages = st.session_state.api_client.get_conversation_messages(
                                conv['id'], 
                                st.session_state.token
                            )
                            
                            # Convert messages to chat format with recipes
                            formatted_messages = []
                            for msg in messages:
                                role = "user" if msg['is_user'] else "assistant"
                                formatted_message = {
                                    "role": role,
                                    "content": msg['content']
                                }
                                
                                # Add recipes if present (for assistant messages)
                                if not msg['is_user'] and msg.get('recipes'):
                                    formatted_message['recipes'] = msg['recipes']
                                else:
                                    formatted_message['recipes'] = []
                                
                                formatted_messages.append(formatted_message)
                            
                            st.session_state.conversation_id = conv['id']
                            st.session_state.messages = formatted_messages
                            st.info(f"Loaded conversation: {conv['title'][:50]}")
                            st.rerun()


def render_recipe_card(recipe):
    """Render an expandable recipe card with full details."""
    with st.expander(f"🍽️ **{recipe['name']}**"):
        # Description
        st.write(recipe.get('full_description', recipe['description']))
        
        # Two columns for details
        col1, col2 = st.columns(2)
        
        with col1:
            # Servings info
            if recipe.get('servings'):
                st.write(f"**Servings:** {recipe['servings']}")
            if recipe.get('serving_size'):
                st.write(f"**Serving Size:** {recipe['serving_size']}")
            
            # Tags
            if recipe.get('tags'):
                tags_text = ", ".join(recipe['tags'][:10])  # Show first 10 tags
                st.write(f"**Tags:** {tags_text}")
        
        with col2:
            # Nutrition info
            if recipe.get('nutrition'):
                st.write("**Nutrition per serving:**")
                nutrition = recipe['nutrition']
                if nutrition.get('calories'):
                    st.write(f"🔥 Calories: {nutrition['calories']} kcal")
                if nutrition.get('protein'):
                    st.write(f"🥩 Protein: {nutrition['protein']}g")
                if nutrition.get('carbs'):
                    st.write(f"🌾 Carbs: {nutrition['carbs']}g")
                if nutrition.get('fat'):
                    st.write(f"🧈 Fat: {nutrition['fat']}g")
        
        # Ingredients - FIXED PARSING
        if recipe.get('ingredients_raw'):
            st.write("**Ingredients:**")
            # Parse the string representation of list
            ingredients_list = parse_list_string(recipe['ingredients_raw'])
            
            # Display as bullet points
            for ingredient in ingredients_list:
                st.write(f"• {ingredient}")
        
        # Steps - FIXED PARSING
        if recipe.get('steps'):
            st.write("**Instructions:**")
            # Parse the steps string
            steps_list = parse_list_string(recipe['steps'])
            
            # Display as numbered list
            for i, step in enumerate(steps_list, 1):
                if step.strip():
                    # Clean up the step text (remove quotes, extra spaces)
                    clean_step = step.strip().strip('"').strip("'")
                    st.write(f"{i}. {clean_step}")
        
        # Match score (for debugging)
        if recipe.get('score'):
            st.caption(f"Match score: {recipe['score']:.3f}")


def render_chat_interface():
    """Render the main chat interface."""
    st.title("Recipe Chat Assistant")
    
    if not st.session_state.user:
        st.info("👈 Please login to start chatting about recipes!")
        return
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Show the main message text
            st.markdown(message["content"])
            
            # Display recipe cards if available
            if message.get("recipes") and message["role"] == "assistant":
                st.divider()
                for recipe in message["recipes"]:
                    render_recipe_card(recipe)
    
    # Chat input
    if prompt := st.chat_input("What would you like to cook today?"):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get response from API
        with st.chat_message("assistant"):
            with st.spinner("Searching for recipes..."):
                response = st.session_state.api_client.send_message(
                    prompt,
                    st.session_state.conversation_id,
                    st.session_state.token
                )
                
                if response:
                    # Update conversation ID
                    st.session_state.conversation_id = response['conversation_id']
                    
                    # Display response
                    st.markdown(response['message'])
                    
                    # Add to messages
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response['message'],
                        "recipes": response.get('recipes', [])
                    })
                    
                    # Display recipe cards
                    if response.get('recipes'):
                        st.divider()
                        for recipe in response['recipes']:
                            render_recipe_card(recipe)
                    
                    # Show debug info in expander
                    if response.get('query_info'):
                        with st.expander("🔍 Debug Info"):
                            st.json(response['query_info'])
                else:
                    st.error("Failed to get response from the API")


def main():
    """Main application."""
    render_sidebar()
    render_chat_interface()


if __name__ == "__main__":
    main()