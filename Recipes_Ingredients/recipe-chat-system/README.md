# Recipe Chat System 🍳

An intelligent recipe recommendation system that understands natural language queries and provides personalized recipe suggestions using semantic search and multi-turn conversations.

## 🌟 Features

- **Natural Language Understanding**: Chat naturally about what you want to cook
- **Smart Ingredient Matching**: Handles typos and variations (e.g., "tomatos" → "tomatoes")
- **Multi-turn Conversations**: Refine your search with follow-up requests
- **Semantic Search**: 113,000+ recipes with vector embeddings for intelligent matching
- **Dietary Preferences**: Supports various diets, allergies, and restrictions
- **Nutritional Information**: Complete nutrition data for all recipes

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- 8GB+ RAM (for running Llama 3.2 model)
- 10GB+ disk space

### Installation

```bash
# Clone the repository
git clone https://github.com/turgutcem/reciperesuggestion.git
cd reciperesuggestion/Recipes_Ingredients/recipe-chat-system

# Start all services
docker-compose up
```

First run will take 15-30 minutes to:
1. Download database files (~300MB) from GitHub Releases
2. Load 113,000+ recipes into PostgreSQL
3. Pull Llama 3.2 model (~2GB)
4. Build vector indexes

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
    
    C -->|Vector Search| F[113k Recipes]
    C -->|Ingredients| G[Canonical Forms]
    C -->|Tags| H[Dietary/Cuisine]
```

### Build Process Flow

1. **PostgreSQL Initialization**
   - Creates database schema
   - Downloads recipe data from GitHub Release
   - Loads recipes, ingredients, tags
   - Creates vector indexes for similarity search

2. **Ollama Setup**
   - Pulls Llama 3.2:3b model
   - Configures for structured output

3. **Backend Startup**
   - Initializes FastAPI server
   - Loads embedding model (all-MiniLM-L6-v2)
   - Connects to PostgreSQL and Ollama

4. **Frontend Launch**
   - Streamlit interface on port 8501

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

### Access the Application

- **Frontend**: http://localhost:8501
- **API Docs**: http://localhost:8001/docs
- **Database**: `localhost:5433` (postgres/postgres)

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
docker-compose up
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

### Logs

```bash
# Check specific service logs
docker logs recipe_postgres
docker logs recipe_backend
docker logs recipe_frontend
docker logs recipe_ollama

# Follow logs
docker-compose logs -f backend
```

## 📊 Performance

- **Recipe Search**: <500ms for typical queries
- **Embedding Generation**: ~100ms per query
- **LLM Extraction**: ~2-3 seconds
- **Database Size**: ~5GB with all indexes
- **Memory Usage**: 
  - Ollama: ~4GB
  - PostgreSQL: ~1GB
  - Backend: ~500MB

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

## 🙏 Acknowledgments

- Recipe data from RecipeNLG dataset
- Llama 3.2 by Meta
- Sentence Transformers by UKPLab
- pgvector extension for PostgreSQL

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/turgutcem/reciperesuggestion/issues)
- **Discussions**: [GitHub Discussions](https://github.com/turgutcem/reciperesuggestion/discussions)

---

**Built with ❤️ for food lovers who can't decide what to cook**