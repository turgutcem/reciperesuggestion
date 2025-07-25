# Recipe Suggestion Assistant - Step-by-Step Deployment Plan
*Using Google Cloud Free Trial + Docker Compose*

##  **Goal**: Deploy a working Recipe Suggestion Assistant for learning and demonstration

---

## **Step 1: Understanding What We're Building**

### System Overview
```
User Request → Web Interface → API → LLM Model + Embeddings → Database → Response
```

### Core Components (5 main pieces):
1. **Web Interface** (Simple HTML/CSS/JS or Streamlit or Gradio - not decided yet)
2. **API Server** (FastAPI - handles requests)
3. **Llama 3.2** (Recipe text generation)
4. **Embedding Service** (Recipe similarity search)
5. **Database** (PostgreSQL + pgvector for recipes)

---

## **Step 2: Architecture Diagram**

```
┌─────────────────────────────────────────┐
│         Google Cloud VM                 │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │      Docker Compose             │   │
│  │                                 │   │
│  │  ┌──────────┐  ┌────────────┐  │   │
│  │  │   Web    │  │    API     │  │   │
│  │  │Interface │──│  Server    │  │   │
│  │  │(Port 80) │  │(Port 8000) │  │   │
│  │  └──────────┘  └──────┬─────┘  │   │
│  │                       │         │   │
│  │  ┌──────────┐  ┌──────▼─────┐  │   │
│  │  │  Llama   │  │ Embedding  │  │   │
│  │  │ Service  │◄─┤  Service   │  │   │
│  │  │(Port     │  │(Port 8001) │  │   │
│  │  │ 11434)   │  └────────────┘  │   │
│  │  └──────────┘         │        │   │
│  │                       ▼        │   │
│  │  ┌───────────────────────────┐ │   │
│  │  │    PostgreSQL Database    │ │   │
│  │  │      (Port 5432)          │ │   │
│  │  └───────────────────────────┘ │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## **Step 3: Resource Planning**

### Google Cloud Free Trial
- **Budget**: $300 credits
- **Time**: 90 days
- **Our VM**: e2-standard-4 (4 CPU, 16GB RAM)
- **Cost**: ~$120/month = **2.5 months free**

### Why This VM Size?
- **Llama 3.2:3b**: Needs ~4-6GB RAM
- **Embedding Service**: Needs ~2GB RAM  
- **Database**: Needs ~3GB RAM
- **OS + Docker**: Needs ~2GB RAM
- **Buffer**: ~3GB RAM for safety
- **Total**: 16GB (perfect fit!)

---

## **Step 4: Deployment Steps Overview**

### Phase 1: Infrastructure
1. Set up VM instance
2. Install Docker & Docker Compose
3. Basic security setup

### Phase 2: Services 
1. Set up PostgreSQL database
2. Deploy Llama service
3. Deploy embedding service
4. Test connections

### Phase 3: Application 
1. Build API server
2. Create web interface
3. Connect everything
4. Add sample recipes

### Phase 4: Testing & Monitoring 
1. Load sample data
2. Test recipe suggestions
3. Add basic monitoring
4. Performance optimization

---

## **Step 5: Detailed Breakdown**

###  **Database Layer**
```
PostgreSQL + pgvector Extension
│
├── recipes table
│   ├── id, title, ingredients
│   ├── instructions
│   └── embedding_vector (for similarity)
│
└── user_interactions table
    ├── search_query, selected_recipe
    └── user_rating, timestamp
```

**Why PostgreSQL?**
- Reliable and well-documented
- pgvector extension for AI embeddings
- Good performance for our scale
- Free tier friendly

###  **AI Services Layer**

#### Llama 3.2 Service
```
Purpose: Generate personalized recipe suggestions
Input: User ingredients + preferences
Output: Customized recipe recommendations
Resource: ~6GB RAM, CPU-only (no GPU in free tier)
```

#### Embedding Service  
```
Purpose: Convert recipes to vectors for similarity search
Model: sentence-transformers/all-MiniLM-L6-v2
Input: Recipe text (title + ingredients)
Output: 384-dimensional vector
Resource: ~2GB RAM
```

###  **API Layer**
```
FastAPI Server
│
├── /suggest-recipes (main endpoint)
├── /health (system check)
├── /metrics (monitoring)
└── /admin (recipe management)
```

**Request Flow:**
1. User sends natural language input
2. API generates embeddings
3. Database finds similar recipes
4. Llama generates personalized suggestions
5. Return ranked recommendations

###  **Web Interface**
```
Simple Single Page Application
│
├── Input text about the recipe(ingredients, preferences)
├── Results display (recipe cards)
├── Recipe details (expandable)
└── Feedback system (rating)
```

---

## **Step 6: Docker Compose Structure**

### Container Organization
```yaml
Services:
├── nginx (Web server + reverse proxy)
├── api (FastAPI application)
├── ollama (Llama 3.2 service)
├── embedding (Sentence transformer service)
├── postgres (Database with pgvector)
└── prometheus (Basic monitoring)
```

### Why Docker Compose?
- **Easy to manage**: One command deploys everything
- **Isolated services**: Each component in its own container
- **Development friendly**: Easy to modify and restart
- **Production ready**: Can scale later if needed

---

## **Step 7: Monitoring Strategy**

### Basic Health Checks
```
Every 30 seconds, check:
├── API responds to /health
├── Database accepts connections  
├── Llama service is ready
├── Embedding service responds
└── Disk space < 80%
```

### Key Metrics to Track
```
Performance:
├── Response time per request
├── Number of requests per minute
├── Error rate (should be < 5%)
└── Memory usage per service

Business:
├── Recipes suggested per day
├── User satisfaction (ratings)
├── Most popular ingredients
└── Peak usage times
```

---

## **Step 8: Cost Management**

### Budget Tracking
```
Step 1: ~$120 (Setup + Testing)
Step 2: ~$120 (Full Operation)  
Step 3: ~$60 (Final validation)
Total: around $300 (Perfect fit for free GCP credits)
```

### Cost Optimization
1. **Shut down when not testing** (save ~$4/day)
2. **Use preemptible instances** (50% cost savings)
3. **Monitor daily spend** (set up alerts)
---