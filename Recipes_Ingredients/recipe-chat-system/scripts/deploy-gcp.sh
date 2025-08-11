#!/bin/bash
# Production Deployment Script for Recipe Chat System on GCP
# This script deploys with proper authentication and Langfuse configuration

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
ZONE=${GCP_ZONE:-"us-central1-a"}
INSTANCE_NAME=${GCP_INSTANCE_NAME:-"recipe-gpu"}
STATIC_IP="34.134.158.162"
GITHUB_REPO="https://github.com/turgutcem/reciperesuggestion.git"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper functions
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo "=============================================="
echo "   Recipe Chat System - Production Deployment"
echo "=============================================="
echo ""
print_info "Instance: $INSTANCE_NAME"
print_info "Static IP: $STATIC_IP"
print_info "Langfuse: Enabled with API keys"
echo ""

# Step 1: Connect to instance
print_status "Connecting to GCP instance..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="

set -e

echo '=== Starting Production Deployment ==='

# Step 2: Update repository
echo 'Updating repository...'
cd ~/reciperesuggestion
git fetch --all
git checkout gcp-gpu-deployment
git pull origin gcp-gpu-deployment

cd Recipes_Ingredients/recipe-chat-system

# Step 3: Backup existing .env if exists
if [ -f .env ]; then
    echo 'Backing up existing .env...'
    cp .env .env.backup.\$(date +%Y%m%d_%H%M%S)
fi

# Step 4: Create production .env file with Langfuse keys
echo 'Creating production .env file...'
cat > .env << 'EOF'
# Recipe Chat System - Production Environment Configuration

# Database Configuration
POSTGRES_DB=recipes_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/recipes_db

# Ollama Configuration
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b

# Session Configuration
SESSION_STORAGE=memory
SESSION_SECRET=\$(openssl rand -base64 32)
SESSION_TTL_HOURS=24

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false

# Frontend Configuration
FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=8501
BACKEND_URL=http://backend:8000

# Production Settings
DEBUG=false
LOG_LEVEL=INFO

# Static IP Configuration
EXTERNAL_IP=$STATIC_IP

# Langfuse Observability Configuration
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_ENVIRONMENT=production

# Langfuse API Keys
LANGFUSE_PUBLIC_KEY=pk-lf-89a63ecb-1147-451c-9f72-bc86ff48e1f5
LANGFUSE_SECRET_KEY=sk-lf-05964e89-a574-40a4-a3dd-4202598d54e0

# Langfuse URLs with Static IP
LANGFUSE_NEXTAUTH_URL=http://$STATIC_IP:3000
LANGFUSE_NEXTAUTH_SECRET=\$(openssl rand -base64 32)
LANGFUSE_SALT=\$(openssl rand -base64 16)

# Langfuse Security
LANGFUSE_ENCRYPTION_KEY=\$(openssl rand -hex 32)

# Langfuse Settings
LANGFUSE_TELEMETRY_ENABLED=false
LANGFUSE_LOG_LEVEL=warn
LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=false
LANGFUSE_CACHE_API_KEY_ENABLED=true

# CORS Configuration
ALLOWED_ORIGINS=[\"http://$STATIC_IP:8501\", \"http://$STATIC_IP:3000\", \"http://localhost:8501\"]
EOF

echo '✓ Created production .env file'

# Step 5: Stop existing containers
echo 'Stopping existing containers...'
sudo docker-compose down 2>/dev/null || true

# Step 6: Pull latest images
echo 'Pulling latest Docker images...'
sudo docker pull ollama/ollama:latest
sudo docker pull langfuse/langfuse:2.74.0

# Step 7: Build and start services with Langfuse
echo 'Building and starting services...'
sudo docker-compose --profile langfuse build --no-cache backend frontend
sudo docker-compose --profile langfuse up -d

# Step 8: Wait for services to be ready
echo 'Waiting for services to start...'
sleep 30

# Step 9: Verify all services are running
echo 'Verifying services...'
sudo docker ps

# Step 10: Check service health
echo 'Checking service health...'
for service in recipe_postgres recipe_ollama recipe_backend recipe_frontend recipe_langfuse; do
    if sudo docker ps | grep -q \$service; then
        echo \"✓ \$service is running\"
    else
        echo \"✗ \$service is not running\"
    fi
done

# Step 11: Initialize Langfuse database
echo 'Ensuring Langfuse database exists...'
sudo docker exec recipe_postgres psql -U postgres -c 'CREATE DATABASE langfuse_db;' 2>/dev/null || echo 'Langfuse database already exists'

# Step 12: Test API endpoints
echo 'Testing API endpoints...'
sleep 10

# Test health endpoint
if curl -s http://localhost:8001/health | grep -q 'healthy'; then
    echo '✓ Backend API is healthy'
else
    echo '✗ Backend API health check failed'
fi

# Test Langfuse
if curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 | grep -q '200\\|302'; then
    echo '✓ Langfuse is accessible'
else
    echo '✗ Langfuse is not accessible'
fi

# Step 13: Show logs
echo ''
echo '=== Recent Backend Logs ==='
sudo docker logs recipe_backend --tail=20 2>&1 | grep -E 'Langfuse|Started|Error' || true

echo ''
echo '=== Deployment Complete ==='
echo 'Services are starting up. It may take 2-3 minutes for everything to be ready.'
"

# Final status
echo ""
echo "=============================================="
echo -e "${GREEN}   🎉 PRODUCTION DEPLOYMENT COMPLETE! 🎉${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}📱 Access your application:${NC}"
echo -e "   Frontend: ${YELLOW}http://$STATIC_IP:8501${NC}"
echo -e "   API Docs: ${YELLOW}http://$STATIC_IP:8001/docs${NC}"
echo -e "   Langfuse: ${YELLOW}http://$STATIC_IP:3000${NC}"
echo ""
echo -e "${GREEN}✅ Features Enabled:${NC}"
echo "   • User Authentication (no shared sessions)"
echo "   • Langfuse Observability (with your API keys)"
echo "   • GPU Acceleration (Tesla T4)"
echo "   • Session Management (24-hour TTL)"
echo ""
echo -e "${BLUE}🔑 Default Test Accounts:${NC}"
echo "   • test@example.com / password"
echo "   • demo@example.com / password"
echo ""
echo -e "${YELLOW}⚠️  Security Notes:${NC}"
echo "   1. Change SESSION_SECRET in .env for production"
echo "   2. Update database passwords"
echo "   3. Consider using HTTPS with a domain"
echo "   4. Langfuse is now tracking all LLM operations"
echo ""
echo -e "${BLUE}🔧 Management Commands:${NC}"
echo "   View logs: ./scripts/manage-instance.sh logs"
echo "   Monitor: ./scripts/monitor-performance.sh"
echo "   Stop: ./scripts/manage-instance.sh stop"
echo ""