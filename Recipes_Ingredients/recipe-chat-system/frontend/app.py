# frontend/app.py
"""
Streamlit frontend for Recipe Chat System.
FIXED: Properly passes authentication tokens in all API requests.
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
    """API client for backend communication with proper authentication."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def _get_auth_headers(self, token: Optional[str] = None) -> Dict:
        """Get authorization headers for requests."""
        headers = {"Content-Type": "application/json"}
        if token:
            headers['Authorization'] = f"Bearer {token}"
        return headers
    
    def login(self, email: str, password: str) -> Optional[Dict]:
        """Login to the API."""
        try:
            response = requests.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password}
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("Invalid email or password")
            else:
                st.error(f"Login failed: {response.text}")
            return None
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to backend. Please ensure the server is running.")
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
            elif response.status_code == 400:
                st.error("Email already exists")
            else:
                st.error(f"Registration failed: {response.text}")
            return None
        except Exception as e:
            st.error(f"Registration error: {e}")
            return None
    
    def verify_token(self, token: str) -> bool:
        """Verify if token is still valid."""
        try:
            response = requests.get(
                f"{self.base_url}/auth/verify",
                headers=self._get_auth_headers(token)
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('valid', False)
            return False
        except:
            return False
    
    def logout(self, token: str) -> bool:
        """Logout and invalidate session."""
        try:
            response = requests.post(
                f"{self.base_url}/auth/logout",
                headers=self._get_auth_headers(token)
            )
            return response.status_code == 200
        except:
            return False
    
    def send_message(self, message: str, conversation_id: Optional[int] = None, token: Optional[str] = None) -> Optional[Dict]:
        """Send a chat message with authentication."""
        if not token:
            st.error("Please login to use the chat")
            return None
        
        data = {"message": message}
        if conversation_id:
            data["conversation_id"] = conversation_id
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/",
                json=data,
                headers=self._get_auth_headers(token)
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("Session expired. Please login again.")
                # Clear session state
                st.session_state.user = None
                st.session_state.token = None
                st.rerun()
            else:
                st.error(f"Chat error: {response.text}")
                return None
        except Exception as e:
            st.error(f"Chat error: {e}")
            return None
    
    def get_conversations(self, token: str) -> List[Dict]:
        """Get user's conversations with authentication."""
        if not token:
            return []
        
        try:
            response = requests.get(
                f"{self.base_url}/chat/conversations",
                headers=self._get_auth_headers(token)
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Session expired
                st.session_state.user = None
                st.session_state.token = None
                return []
            return []
        except:
            return []
    
    def get_conversation_messages(self, conversation_id: int, token: str) -> List[Dict]:
        """Get messages for a specific conversation with recipe details."""
        if not token:
            return []
        
        try:
            response = requests.get(
                f"{self.base_url}/chat/conversations/{conversation_id}/messages",
                headers=self._get_auth_headers(token),
                params={'include_recipes': True}
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Session expired
                st.session_state.user = None
                st.session_state.token = None
                return []
            return []
        except:
            return []
    
    def delete_conversation(self, conversation_id: int, token: str) -> bool:
        """Delete a conversation."""
        if not token:
            return False
        
        try:
            response = requests.delete(
                f"{self.base_url}/chat/conversations/{conversation_id}",
                headers=self._get_auth_headers(token)
            )
            return response.status_code == 200
        except:
            return False
    
    def check_health(self) -> bool:
        """Check if API is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
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
            st.error("⚠️ Backend API is not available!")
            st.info("Please check if the server is running.")
            return
        
        # Authentication section
        if not st.session_state.user:
            st.subheader("Login")
            
            tab1, tab2 = st.tabs(["Login", "Register"])
            
            with tab1:
                with st.form("login_form"):
                    email = st.text_input("Email", value="test@example.com")
                    password = st.text_input("Password", type="password", value="password")
                    submit = st.form_submit_button("Login", use_container_width=True)
                    
                    if submit:
                        result = st.session_state.api_client.login(email, password)
                        if result:
                            st.session_state.user = result['user']
                            st.session_state.token = result['access_token']
                            st.success(f"Welcome, {result['user']['name'] or result['user']['email']}!")
                            st.rerun()
            
            with tab2:
                with st.form("register_form"):
                    reg_name = st.text_input("Name")
                    reg_email = st.text_input("Email")
                    reg_password = st.text_input("Password", type="password")  
                    reg_password_confirm = st.text_input("Confirm Password", type="password")  
                    submit = st.form_submit_button("Register", use_container_width=True)
                    
                    if submit:
                        if not reg_email or not reg_password:
                            st.error("Email and password are required")
                        elif reg_password != reg_password_confirm:
                            st.error("Passwords do not match")
                        elif len(reg_password) < 6:  # Validation is done here instead
                            st.error("Password must be at least 6 characters")
                        else:
                            result = st.session_state.api_client.register(reg_email, reg_password, reg_name)
                            if result:
                                st.success("Registration successful! Please login.")
                                st.rerun()
        else:
            # User is logged in - verify token is still valid
            if st.session_state.token:
                if not st.session_state.api_client.verify_token(st.session_state.token):
                    st.warning("Session expired. Please login again.")
                    st.session_state.user = None
                    st.session_state.token = None
                    st.rerun()
            
            # Show user info
            st.success(f"👤 {st.session_state.user['email']}")
            if st.session_state.user.get('name'):
                st.caption(f"Name: {st.session_state.user['name']}")
            
            if st.button("Logout", use_container_width=True):
                if st.session_state.token:
                    st.session_state.api_client.logout(st.session_state.token)
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
                if st.button("Refresh", use_container_width=True):
                    st.rerun()
            
            # Show recent conversations
            if st.session_state.token:
                conversations = st.session_state.api_client.get_conversations(st.session_state.token)
                if conversations:
                    st.caption(f"Recent chats ({len(conversations)}):")
                    for conv in conversations[:10]:  # Show up to 10 recent
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            title = conv.get('title', 'Untitled')[:30]
                            if st.button(f"💬 {title}...", key=f"conv_{conv['id']}", use_container_width=True):
                                # Load the conversation messages
                                messages = st.session_state.api_client.get_conversation_messages(
                                    conv['id'], 
                                    st.session_state.token
                                )
                                
                                # Convert messages to chat format
                                formatted_messages = []
                                for msg in messages:
                                    role = "user" if msg['is_user'] else "assistant"
                                    formatted_message = {
                                        "role": role,
                                        "content": msg['content']
                                    }
                                    
                                    # Add recipes if present
                                    if not msg['is_user'] and msg.get('recipes'):
                                        formatted_message['recipes'] = msg['recipes']
                                    else:
                                        formatted_message['recipes'] = []
                                    
                                    formatted_messages.append(formatted_message)
                                
                                st.session_state.conversation_id = conv['id']
                                st.session_state.messages = formatted_messages
                                st.rerun()
                        
                        with col2:
                            if st.button("🗑", key=f"del_{conv['id']}", help="Delete conversation"):
                                if st.session_state.api_client.delete_conversation(conv['id'], st.session_state.token):
                                    if st.session_state.conversation_id == conv['id']:
                                        st.session_state.conversation_id = None
                                        st.session_state.messages = []
                                    st.rerun()
                else:
                    st.info("No conversations yet. Start chatting!")


def render_recipe_card(recipe):
    """Render an expandable recipe card with full details."""
    with st.expander(f"🍽️ **{recipe.get('name', 'Unknown Recipe')}**"):
        # Description
        full_desc = recipe.get('full_description', recipe.get('description', ''))
        if full_desc:
            st.write(full_desc)
        
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
                tags = recipe['tags'] if isinstance(recipe['tags'], list) else []
                if tags:
                    tags_text = ", ".join(tags[:10])  # Show first 10 tags
                    st.write(f"**Tags:** {tags_text}")
        
        with col2:
            # Nutrition info
            nutrition = recipe.get('nutrition', {})
            if nutrition and any(nutrition.values()):
                st.write("**Nutrition per serving:**")
                if nutrition.get('calories'):
                    st.write(f"🔥 Calories: {nutrition['calories']} kcal")
                if nutrition.get('protein'):
                    st.write(f"🥩 Protein: {nutrition['protein']}g")
                if nutrition.get('carbs'):
                    st.write(f"🌾 Carbs: {nutrition['carbs']}g")
                if nutrition.get('fat'):
                    st.write(f"🧈 Fat: {nutrition['fat']}g")
        
        # Ingredients
        if recipe.get('ingredients_raw'):
            st.write("**Ingredients:**")
            ingredients_list = recipe['ingredients_raw'] if isinstance(recipe['ingredients_raw'], list) else parse_list_string(recipe['ingredients_raw'])
            
            # Display as bullet points
            for ingredient in ingredients_list:
                if ingredient:
                    st.write(f"• {ingredient}")
        
        # Steps
        if recipe.get('steps'):
            st.write("**Instructions:**")
            steps_list = recipe['steps'] if isinstance(recipe['steps'], list) else parse_list_string(recipe['steps'])
            
            # Display as numbered list
            for i, step in enumerate(steps_list, 1):
                if step and step.strip():
                    # Clean up the step text
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
        st.markdown("""
        ### Welcome to Recipe Chat System!
        
        This intelligent assistant helps you discover recipes based on:
        - 🥗 **Ingredients** you have or want to use
        - 🚫 **Dietary restrictions** and allergies
        - 🌍 **Cuisines** from around the world
        - ⏱️ **Cooking time** and difficulty
        
        **Get started:**
        1. Login or register using the sidebar
        2. Ask for any recipe you'd like
        3. Refine your search with follow-up requests
        """)
        return
    
    # Show current conversation ID if exists
    if st.session_state.conversation_id:
        st.caption(f"Conversation ID: {st.session_state.conversation_id}")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Show the main message text
            st.markdown(message["content"])
            
            # Display recipe cards if available
            if message.get("recipes") and message["role"] == "assistant":
                recipes = message["recipes"]
                if recipes:
                    st.divider()
                    for recipe in recipes:
                        render_recipe_card(recipe)
    
    # Chat input
    if prompt := st.chat_input("What would you like to cook today?"):
        # Check if user is still logged in
        if not st.session_state.token:
            st.error("Please login to continue")
            return
        
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
                    assistant_message = {
                        "role": "assistant",
                        "content": response['message'],
                        "recipes": response.get('recipes', [])
                    }
                    st.session_state.messages.append(assistant_message)
                    
                    # Display recipe cards
                    if response.get('recipes'):
                        st.divider()
                        for recipe in response['recipes']:
                            render_recipe_card(recipe)
                    
                    # Show debug info in expander (only in debug mode)
                    if os.getenv('DEBUG', 'false').lower() == 'true' and response.get('query_info'):
                        with st.expander("🔍 Debug Info"):
                            st.json(response['query_info'])
                else:
                    st.error("Failed to get response. Please try again.")


def main():
    """Main application."""
    render_sidebar()
    render_chat_interface()


if __name__ == "__main__":
    main()