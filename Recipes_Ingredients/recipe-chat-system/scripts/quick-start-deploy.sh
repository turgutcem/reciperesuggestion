#!/bin/bash
# Quick Start Script for Recipe Chat System on GCP
# Run this after SSHing into your GCP instance

set -e

STATIC_IP="34.134.158.162"

echo "🚀 Recipe Chat System - Quick Start"
echo "==================================="

# Navigate to project directory
cd ~/reciperesuggestion/Recipes_Ingredients/recipe-chat-system

# Create production .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating production .env file..."
    
    # Generate secure tokens
    SESSION_SECRET=$(openssl rand -base64 32)
    NEXTAUTH_SECRET=$(openssl rand -base64 32)
    SALT=$(openssl rand -base64 16)
    ENCRYPTION_KEY=$(openssl rand -hex 32)
    
    cat > .env << EOF
# Recipe Chat System - Production Configuration
POSTGRES_DB=recipes_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/recipes_db

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b

SESSION_STORAGE=memory
SESSION_SECRET=$SESSION_SECRET
SESSION_TTL_HOURS=24

API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false

FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=8501
BACKEND_URL=http://backend:8000

DEBUG=false
LOG_LEVEL=INFO

EXTERNAL_IP=$STATIC_IP

# Langfuse Configuration
LANGFUSE_ENABLED=true
# LANGFUSE_HOST in .env is for host access - Docker will override this
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_ENVIRONMENT=production
LANGFUSE_PUBLIC_KEY=pk-lf-89a63ecb-1147-451c-9f72-bc86ff48e1f5
LANGFUSE_SECRET_KEY=sk-lf-05964e89-a574-40a4-a3dd-4202598d54e0
LANGFUSE_NEXTAUTH_URL=http://$STATIC_IP:3000
LANGFUSE_NEXTAUTH_SECRET=$NEXTAUTH_SECRET
LANGFUSE_SALT=$SALT
LANGFUSE_ENCRYPTION_KEY=$ENCRYPTION_KEY
LANGFUSE_TELEMETRY_ENABLED=false
LANGFUSE_LOG_LEVEL=warn
EOF
    echo "✅ .env file created with secure tokens"
else
    echo "ℹ️  Using existing .env file"
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
sudo docker-compose --profile langfuse down 2>/dev/null || true

# Ensure Langfuse database exists
echo "💾 Setting up databases..."
sudo docker-compose up -d postgres
sleep 10
sudo docker exec recipe_postgres psql -U postgres -c 'CREATE DATABASE langfuse_db;' 2>/dev/null || true

# Start all services with Langfuse
echo "🔧 Starting all services..."
sudo docker-compose --profile langfuse up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start (30 seconds)..."
sleep 30

# Check service status
echo ""
echo "📊 Service Status:"
echo "=================="
for service in postgres ollama langfuse backend frontend; do
    if sudo docker ps | grep -q "recipe_$service"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
    fi
done

# Test endpoints
echo ""
echo "🧪 Testing Endpoints:"
echo "===================="

# Backend health
if curl -s http://localhost:8001/health | grep -q '"status"'; then
    echo "✅ Backend API is healthy"
else
    echo "❌ Backend API not responding"
fi

# Frontend
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep -q "200"; then
    echo "✅ Frontend is accessible"
else
    echo "❌ Frontend not responding"
fi

# Langfuse
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200\|302"; then
    echo "✅ Langfuse is accessible"
else
    echo "❌ Langfuse not responding"
fi

# Show access URLs
echo ""
echo "============================================"
echo "   🎉 Recipe Chat System is Ready!"
echo "============================================"
echo ""
echo "📱 Access your application:"
echo "   Frontend: http://$STATIC_IP:8501"
echo "   API Docs: http://$STATIC_IP:8001/docs"
echo "   Langfuse: http://$STATIC_IP:3000"
echo ""
echo "🔑 Test Accounts:"
echo "   • test@example.com / password"
echo "   • demo@example.com / password"
echo ""
echo "📝 View logs:"
echo "   All: sudo docker-compose logs -f"
echo "   Backend: sudo docker logs -f recipe_backend"
echo "   Langfuse: sudo docker logs -f recipe_langfuse"
echo ""
echo "🛑 To stop all services:"
echo "   sudo docker-compose --profile langfuse down"
echo ""