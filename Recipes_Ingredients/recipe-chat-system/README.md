# Recipe Chat System 🍳

An intelligent recipe recommendation system that understands natural language queries and provides personalized recipe suggestions using semantic search and multi-turn conversations.

## 🌟 Features

- **Natural Language Understanding**: Chat naturally about what you want to cook
- **Smart Ingredient Matching**: Handles typos and variations (e.g., "tomatos" → "tomatoes")
- **Multi-turn Conversations**: Refine your search with follow-up requests
- **Semantic Search**: 113,000+ recipes with vector embeddings for intelligent matching
- **Dietary Preferences**: Supports various diets, allergies, and restrictions
- **Nutritional Information**: Complete nutrition data for all recipes
- **LLM Observability** (Optional): Integrated Langfuse for tracking AI performance and debugging

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- 8GB+ RAM (for running Llama 3.2 model)
- 10GB+ disk space

### Installation

#### Option 1: Basic Setup (Without Observability)

```bash
# Clone the repository
git clone https://github.com/turgutcem/reciperesuggestion.git
cd reciperesuggestion/Recipes_Ingredients/recipe-chat-system

# Copy environment template / they are identical here so you can skip this part
cp .env.example .env

# Start core services only
docker-compose up
```

#### Option 2: Setup with Langfuse Observability

```bash
# Clone the repository
git clone https://github.com/turgutcem/reciperesuggestion.git
cd reciperesuggestion/Recipes_Ingredients/recipe-chat-system

# Copy environment template / they are identical here so you can skip this part
cp .env.example .env

# Start all services including Langfuse
docker-compose --profile langfuse up
```

First run will take 15-30 minutes to:
1. Download database files (~300MB) from GitHub Releases
2. Load 113,000+ recipes into PostgreSQL
3. Pull Llama 3.2 model (~2GB)
4. Build vector indexes
5. (Optional) Initialize Langfuse for observability

## 📊 Langfuse Observability (Optional)

Langfuse provides detailed insights into your LLM operations, helping you monitor, debug, and optimize the AI components of the system.

### What is Langfuse?

Langfuse is an open-source LLM observability platform that tracks:
- LLM call latency and costs
- Prompt/completion pairs
- User sessions and conversations
- Error rates and performance metrics
- Token usage and model behavior

### Running with Langfuse

#### Step 1: Start Services with Langfuse Profile

```bash
# Start all services including Langfuse
docker-compose --profile langfuse up -d

# Or run in foreground to see logs
docker-compose --profile langfuse up
```

#### Step 2: Initial Langfuse Setup (First Time Only)

1. **Access Langfuse UI**: Navigate to http://localhost:3000
2. **Create Organization**: 
   - Click "Sign up"
   - Create an organization (e.g., "Recipe Chat")
   - Set up your admin account
3. **Generate API Keys**:
   - Go to Settings → API Keys
   - Click "Create new API key"
   - Copy both the Public and Secret keys

#### Step 3: Configure API Keys

Update your `.env` file with the Langfuse keys:

```env
# Enable Langfuse
LANGFUSE_ENABLED=true

# Add your API keys from Langfuse UI
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

#### Step 4: Restart Backend

```bash
# Restart backend to apply new configuration
docker restart recipe_backend

# Verify Langfuse is connected
docker logs recipe_backend | grep -i langfuse
```

You should see:
```
✅ Langfuse observability enabled: http://langfuse:3000
✅ Langfuse connection verified
```

### Running Without Langfuse

The system works perfectly without Langfuse. Simply use the standard docker-compose command:

```bash
# Start without Langfuse (default)
docker-compose up -d

# Or ensure Langfuse is disabled in .env
LANGFUSE_ENABLED=false
```

### Managing Langfuse

```bash
# Stop all services including Langfuse
docker-compose --profile langfuse down

# Stop only Langfuse (keep other services running)
docker stop recipe_langfuse

# View Langfuse logs
docker logs recipe_langfuse

# Restart Langfuse
docker restart recipe_langfuse
```

### Langfuse Features in Recipe Chat

When enabled, Langfuse tracks:
- **Recipe Query Extraction**: How user messages are parsed
- **Tag Extraction**: Dietary preferences and cuisine detection
- **Conversation Flow**: Multi-turn conversation decisions
- **Search Performance**: Recipe retrieval latency
- **Token Usage**: LLM token consumption per request

Access the Langfuse dashboard at http://localhost:3000 to:
- View real-time traces of all LLM operations
- Analyze prompt effectiveness
- Monitor system performance
- Debug conversation issues
- Track user satisfaction metrics

### Langfuse Security Notes

- **API Keys**: Keep your Langfuse API keys secure and never commit them to Git
- **Data Privacy**: All observability data stays on your local Langfuse instance
- **Network**: Langfuse runs in an isolated Docker network with the backend
- **Encryption**: For production, configure proper encryption keys in `.env`:
  ```env
  LANGFUSE_ENCRYPTION_KEY=<64-character-hex-string>
  LANGFUSE_NEXTAUTH_SECRET=<secure-random-string>
  LANGFUSE_SALT=<secure-random-salt>
  ```

### Generating Secure Keys

For production deployment, generate secure keys:

```bash
# Generate encryption key (64 hex characters)
openssl rand -hex 32

# Generate NextAuth secret
openssl rand -base64 32

# Generate salt
openssl rand -base64 16
```

## 📁 Project Structure

```
recipe-chat-system/
├── backend/              # FastAPI backend
│   ├── main.py          # Application entry point
│   ├── routers/         # API endpoints
│   │   ├── auth.py      # Authentication
│   │   └── chat.py      # Chat & recipe search
│   ├── services/        # Core business logic
│   │   ├── llm_service.py       # Ollama/Llama integration
│   │   ├── langfuse_service.py  # Observability service
│   │   ├── embedding_service.py # Sentence transformers
│   │   ├── recipe_service.py    # Recipe search & retrieval
│   │   └── chat_service.py      # Conversation management
│   ├── prompts/         # System prompts
│   └── models.py        # Database models
├── frontend/            # Streamlit UI
│   └── app.py          # Web interface
├── database/           # PostgreSQL setup
│   ├── 00_init_db.sh  # Auto-downloads data
│   ├── 01_schema.sql  # Database schema
│   └── 07_vector_indexes.sql # pgvector indexes
└── docker-compose.yml  # Service orchestration
```

## 🏗️ Architecture

### System Components

```mermaid
graph TD
    A[Streamlit Frontend :8501] -->|REST API| B[FastAPI Backend :8001]
    B --> C[PostgreSQL + pgvector :5433]
    B --> D[Ollama + Llama 3.2 :11434]
    B --> E[SentenceTransformers]
    B -.->|Optional| F[Langfuse :3000]
    
    C -->|Vector Search| G[113k Recipes]
    C -->|Ingredients| H[Canonical Forms]
    C -->|Tags| I[Dietary/Cuisine]
    F -.->|Observability| J[LLM Metrics]
```

### Build Process Flow

1. **PostgreSQL Initialization**
   - Creates database schema
   - Downloads recipe data from GitHub Release
   - Loads recipes, ingredients, tags
   - Creates vector indexes for similarity search
   - (Optional) Creates Langfuse database

2. **Ollama Setup**
   - Pulls Llama 3.2:3b model
   - Configures for structured output

3. **Backend Startup**
   - Initializes FastAPI server
   - Loads embedding model (all-MiniLM-L6-v2)
   - Connects to PostgreSQL and Ollama
   - (Optional) Connects to Langfuse for observability

4. **Frontend Launch**
   - Streamlit interface on port 8501

5. **Langfuse Initialization** (Optional)
   - Sets up observability database
   - Initializes tracing infrastructure

## 💬 How It Works

### Query Processing Pipeline

1. **User Input**: "I want Italian vegetarian pasta with tomatoes"

2. **LLM Extraction** (Llama 3.2):
   ```json
   {
     "query": "Italian vegetarian pasta recipes",
     "include_ingredients": ["tomatoes"],
     "exclude_ingredients": [],
     "tags": {
       "CUISINES_REGIONAL": "Italian",
       "DIETS": "vegetarian",
       "MEAL_COURSES": "main dish"
     }
   }
   ```

3. **Ingredient Resolution**:
   - "tomatoes" → canonical: "tomato"
   - Finds all variants: ["tomato", "tomatoes", "roma tomatoes", ...]

4. **Search Strategy**:
   - Filter by ingredients (must have tomatoes)
   - Filter by critical tags (Italian, vegetarian)
   - Rank by embedding similarity
   - Return top 5 results

5. **Observability** (if Langfuse enabled):
   - Tracks extraction latency
   - Records prompt/completion pairs
   - Monitors search performance

### Multi-turn Conversation Example

```
User: "I want pasta with tomatoes"
Assistant: Found 93 pasta recipes with tomatoes...

User: "Add basil and make it quick"  
Assistant: Found 12 recipes (added basil, under 30 minutes)...

User: "Actually exclude nuts"
Assistant: Found 1 recipe (no nuts)...

User: "Show me Mexican food instead"  [RESET]
Assistant: Found 1,547 Mexican recipes...
```

## 🖥️ Usage

### Access Points

- **Frontend**: http://localhost:8501
- **API Docs**: http://localhost:8001/docs
- **Database**: `localhost:5433` (postgres/postgres)
- **Langfuse** (if enabled): http://localhost:3000

### Default Test Accounts

- Email: `test@example.com` / Password: `password`
- Email: `demo@example.com` / Password: `password`

### API Endpoints

```bash
# Authentication
POST /auth/login
POST /auth/register

# Chat
POST /chat/              # Send message
GET  /chat/conversations # List conversations
GET  /chat/conversations/{id}/messages

# Health Check
GET  /health
```

## 🔧 Development

### Local Development Setup

```bash
# Backend development
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend development  
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### Environment Variables (.env)

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/recipes_db

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

# Session
SESSION_SECRET=your-secret-key-change-in-production

# Development
DEBUG=true

# Langfuse (Optional)
LANGFUSE_ENABLED=false  # Set to true to enable
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=    # Get from Langfuse UI
LANGFUSE_SECRET_KEY=    # Get from Langfuse UI
```

### Database Management

```bash
# Connect to database
docker exec -it recipe_postgres psql -U postgres -d recipes_db

# Useful queries
SELECT COUNT(*) FROM recipes;  -- Check recipe count
SELECT COUNT(*) FROM ingredients;  -- Check ingredients
SELECT COUNT(*) FROM tags;  -- Check tags

# Reset database
docker-compose down -v
docker-compose --profile langfuse up  # With Langfuse
# OR
docker-compose up  # Without Langfuse
```

### Adding New Recipes

1. Update `database/export_existing_data.py` with your data source
2. Generate new SQL files
3. Create new GitHub Release
4. Update `00_init_db.sh` with new release URL

## 🐛 Troubleshooting

### Common Issues

**Issue**: "relation 'users' does not exist"
- **Cause**: Database initialization failed
- **Fix**: Ensure `00_init_db.sh` has LF line endings (not CRLF)

**Issue**: Slow first startup
- **Cause**: Downloading 300MB data + 2GB model
- **Normal**: First run takes 15-30 minutes

**Issue**: "Cannot connect to Ollama"
- **Fix**: Wait for model download to complete
- **Check**: `docker logs recipe_ollama`

**Issue**: Out of memory
- **Fix**: Increase Docker memory to 8GB+
- **Alternative**: Use smaller model in `.env`

**Issue**: Langfuse not tracking data
- **Check**: Verify `LANGFUSE_ENABLED=true` in `.env`
- **Fix**: Restart backend after adding API keys
- **Debug**: Check logs with `docker logs recipe_backend | grep -i langfuse`

### Logs

```bash
# Check specific service logs
docker logs recipe_postgres
docker logs recipe_backend
docker logs recipe_frontend
docker logs recipe_ollama
docker logs recipe_langfuse  # If using Langfuse

# Follow logs
docker-compose logs -f backend
docker-compose --profile langfuse logs -f  # All services with Langfuse
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

### Code Style

- Python: Black formatter, PEP 8
- SQL: Uppercase keywords
- Git: Conventional commits

### Before Committing

1. Copy `.env` to `.env.example` and remove sensitive keys
2. Ensure no API keys or passwords in code
3. Test both with and without Langfuse
4. Update documentation for new features

## 🙏 Acknowledgments

- Recipe data from variety of sources but mostly Kaggle datasets
- Llama 3.2 by Meta
- Sentence Transformers by UKPLab
- pgvector extension for PostgreSQL
- Langfuse for LLM observability

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/turgutcem/reciperesuggestion/issues)
- **Discussions**: [GitHub Discussions](https://github.com/turgutcem/reciperesuggestion/discussions)

---

**Built with ❤️ for food lovers who can't decide what to cook**