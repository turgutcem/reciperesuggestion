#!/bin/bash
# GCP Deployment Script for Recipe Chat System with GPU
# This script creates and configures a GCP instance with GPU support

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
PROJECT_ID=${1:-""}
ZONE=${2:-"us-central1-a"}
INSTANCE_NAME=${3:-"recipe-gpu"}
GITHUB_REPO="https://github.com/turgutcem/reciperesuggestion.git"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first:"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check project ID
if [ -z "$PROJECT_ID" ]; then
    print_error "Project ID is required!"
    echo "Usage: $0 <PROJECT_ID> [ZONE] [INSTANCE_NAME]"
    echo "Example: $0 my-project-123 us-central1-a recipe-gpu"
    exit 1
fi

echo "=============================================="
echo "   Recipe Chat System - GCP GPU Deployment"
echo "=============================================="
echo ""
print_info "Project ID: $PROJECT_ID"
print_info "Zone: $ZONE"
print_info "Instance Name: $INSTANCE_NAME"
print_info "Machine Type: n1-standard-4 (4 vCPU, 15GB RAM)"
print_info "GPU: Tesla T4 (16GB VRAM)"
print_info "Estimated Cost: ~\$0.35/hour (preemptible)"
echo ""

# Step 1: Set the project
print_status "Setting GCP project..."
gcloud config set project $PROJECT_ID

# Step 2: Enable required APIs
print_status "Enabling required GCP APIs..."
gcloud services enable compute.googleapis.com

# Step 3: Check if instance already exists
if gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE &>/dev/null; then
    print_warning "Instance $INSTANCE_NAME already exists!"
    read -p "Do you want to delete and recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deleting existing instance..."
        gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --quiet
    else
        print_info "Exiting without changes"
        exit 0
    fi
fi

# Step 4: Create the instance with GPU (FIXED MACHINE TYPE)
print_status "Creating n1-standard-4 instance with Tesla T4 GPU..."
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-standard \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --preemptible \
    --maintenance-policy=TERMINATE \
    --metadata=install-nvidia-driver=True \
    --tags=http-server,https-server,recipe-server

print_status "Instance created successfully!"

# Step 5: Create firewall rules
print_status "Setting up firewall rules..."
# Rule for frontend
gcloud compute firewall-rules create allow-recipe-frontend \
    --project=$PROJECT_ID \
    --allow tcp:8501 \
    --source-ranges 0.0.0.0/0 \
    --target-tags recipe-server \
    --description="Allow Recipe Chat Frontend" \
    2>/dev/null || print_info "Frontend firewall rule already exists"

# Rule for API
gcloud compute firewall-rules create allow-recipe-api \
    --project=$PROJECT_ID \
    --allow tcp:8001 \
    --source-ranges 0.0.0.0/0 \
    --target-tags recipe-server \
    --description="Allow Recipe Chat API" \
    2>/dev/null || print_info "API firewall rule already exists"

# Rule for Langfuse (optional)
gcloud compute firewall-rules create allow-langfuse \
    --project=$PROJECT_ID \
    --allow tcp:3000 \
    --source-ranges 0.0.0.0/0 \
    --target-tags recipe-server \
    --description="Allow Langfuse UI" \
    2>/dev/null || print_info "Langfuse firewall rule already exists"

# Step 6: Wait for instance to be ready
print_status "Waiting for instance to be ready..."
sleep 60  # Give GCP time to install NVIDIA drivers

# Check instance status
while true; do
    STATUS=$(gcloud compute instances describe $INSTANCE_NAME \
        --zone=$ZONE --format='get(status)')
    if [ "$STATUS" = "RUNNING" ]; then
        break
    fi
    echo -n "."
    sleep 5
done
echo ""

# Step 7: Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

print_status "Instance is running! External IP: $EXTERNAL_IP"

# Step 8: Install software on the instance
print_status "Installing Docker and application..."

# Create the setup script
cat > /tmp/setup_instance.sh << 'SETUP_SCRIPT'
#!/bin/bash
set -e

echo "=== Starting Recipe Chat System Setup ==="

# Wait for any automatic updates to finish
while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    echo "Waiting for apt lock..."
    sleep 5
done

# Update system
echo "Updating system packages..."
sudo apt-get update

# Check if NVIDIA drivers are installed
if nvidia-smi &>/dev/null; then
    echo "NVIDIA drivers already installed by GCP"
    nvidia-smi
else
    echo "Installing NVIDIA drivers..."
    sudo apt-get install -y nvidia-driver-535-server
    echo "Drivers installed. Reboot required."
    sudo reboot
fi

# Install Docker
echo "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
fi

# Install Docker Compose
echo "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo apt-get install -y docker-compose
fi

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime by default
sudo nvidia-ctk runtime configure --runtime=docker --set-as-default
sudo systemctl restart docker

# Verify GPU is accessible in Docker
echo "Verifying GPU access in Docker..."
sudo docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Install git
sudo apt-get install -y git

echo "=== Setup Complete ==="
SETUP_SCRIPT

# Copy and run the setup script
gcloud compute scp /tmp/setup_instance.sh $INSTANCE_NAME:/tmp/setup_instance.sh --zone=$ZONE
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="chmod +x /tmp/setup_instance.sh && /tmp/setup_instance.sh"

# Step 9: Clone repository and start services
print_status "Cloning repository and starting services..."

gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="
set -e

# Clone the repository
echo 'Cloning repository...'
cd ~
if [ -d 'reciperesuggestion' ]; then
    echo 'Repository already exists, pulling latest changes...'
    cd reciperesuggestion
    git fetch --all
    git pull origin master
else
    git clone $GITHUB_REPO
    cd reciperesuggestion
fi

cd Recipes_Ingredients/recipe-chat-system

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo 'Creating .env file...'
    cat > .env << 'EOF'
POSTGRES_DB=recipes_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/recipes_db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
SESSION_SECRET=gpu-deployment-secret-change-in-production
DEBUG=true
LANGFUSE_ENABLED=false
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_ENVIRONMENT=production
EOF
fi

# Create docker-compose.gpu.yml if it doesn't exist
echo 'Creating GPU docker-compose file...'
cat > docker-compose.gpu.yml << 'EOF'
$(cat <<'DOCKER_COMPOSE'
version: '3.8'

services:
  postgres:
    build: ./database
    container_name: recipe_postgres
    environment:
      POSTGRES_DB: recipes_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - ./database:/docker-entrypoint-initdb.d
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    container_name: recipe_ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    healthcheck:
      test: ["CMD-SHELL", "ollama list || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  langfuse:
    image: langfuse/langfuse:2.74.0
    container_name: recipe_langfuse
    profiles: ["langfuse"]
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/langfuse_db
      NEXTAUTH_URL: http://localhost:3000
      NEXTAUTH_SECRET: recipe-chat-secret-change-in-production
      SALT: recipe-chat-salt-change-in-production
      ENCRYPTION_KEY: 0000000000000000000000000000000000000000000000000000000000000000
      TELEMETRY_ENABLED: false
      LANGFUSE_LOG_LEVEL: warn
    ports:
      - "3000:3000"

  backend:
    build: ./backend
    container_name: recipe_backend
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/recipes_db
      OLLAMA_BASE_URL: http://ollama:11434
      LANGFUSE_HOST: http://langfuse:3000
      PYTHONUNBUFFERED: 1
    ports:
      - "8001:8000"
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    container_name: recipe_frontend
    restart: unless-stopped
    env_file: .env
    environment:
      BACKEND_URL: http://backend:8000
      STREAMLIT_SERVER_ADDRESS: 0.0.0.0
      STREAMLIT_SERVER_PORT: 8501
    ports:
      - "8501:8501"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app

  model_loader:
    image: ollama/ollama:latest
    container_name: recipe_model_loader
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ollama_data:/root/.ollama
    network_mode: "service:ollama"
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        echo "Waiting for Ollama to be ready..."
        sleep 20
        export OLLAMA_HOST=http://localhost:11434
        echo "Pulling Llama 3.2:3b model with GPU..."
        ollama pull llama3.2:3b
        echo "Model ready!"
        ollama list

volumes:
  postgres_data:
  ollama_data:
DOCKER_COMPOSE
)
EOF

# Start Docker services
echo 'Starting Docker services with GPU support...'
sudo docker-compose -f docker-compose.gpu.yml down 2>/dev/null || true
sudo docker-compose -f docker-compose.gpu.yml up -d

# Wait for services to be ready
echo 'Waiting for services to start (this may take 5-10 minutes for first run)...'
sleep 30

# Show running containers
echo 'Running containers:'
sudo docker ps

echo 'Deployment complete!'
"

# Step 10: Final verification
print_status "Verifying deployment..."
sleep 10

# Print summary
echo ""
echo "=============================================="
echo -e "${GREEN}   🎉 DEPLOYMENT COMPLETE! 🎉${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}📱 Access your application:${NC}"
echo -e "   Frontend: ${YELLOW}http://$EXTERNAL_IP:8501${NC}"
echo -e "   API Docs: ${YELLOW}http://$EXTERNAL_IP:8001/docs${NC}"
echo -e "   Langfuse: ${YELLOW}http://$EXTERNAL_IP:3000${NC} (if enabled)"
echo ""
echo -e "${BLUE}💰 Cost Information:${NC}"
echo "   Running: ~\$0.35/hour (n1-standard-4 + T4 GPU preemptible)"
echo "   Stopped: \$0/hour (only pay for 50GB disk ~\$2/month)"
echo ""
echo -e "${BLUE}🔧 Management Commands:${NC}"
echo "   SSH: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "   Stop: gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE"
echo "   Start: gcloud compute instances start $INSTANCE_NAME --zone=$ZONE"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Stop the instance when not in use!${NC}"