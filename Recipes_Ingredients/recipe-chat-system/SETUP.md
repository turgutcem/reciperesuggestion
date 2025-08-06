# Quick Setup Guide

## 1. Clone and Configure

\`\`\`bash
git clone <your-repo>
cd recipe-chat-system

# Option A: Interactive setup (recommended for beginners)
cd backend
python setup_env.py

# Option B: Manual setup (for experienced users)
cp backend/.env.example backend/.env
# Edit backend/.env with your database credentials
\`\`\`

## 2. Run the System

\`\`\`bash
# Start everything with Docker
docker-compose up --build

# Access the application
# - Frontend: http://localhost:7860
# - Backend API: http://localhost:8000
# - Health Check: http://localhost:8000/health
\`\`\`

## 3. Default Configuration

If you just want to test quickly:
- Database: PostgreSQL (auto-created in Docker)
- Username: postgres  
- Password: (set during setup)
- Everything else uses defaults

## 4. Troubleshooting

### Database Connection Issues
- Check your .env file has correct DB_PASSWORD
- Make sure Docker containers are running
- Check logs: \`docker-compose logs postgres\`

### Ollama Model Issues  
- First run takes time to download Llama model
- Check logs: \`docker-compose logs ollama\`
- Model loads automatically on first chat message
\`\`\`

---

##  **Implementation Steps**

### **Step 1: Basic FastAPI Setup (20 minutes)**

#### **requirements.txt**