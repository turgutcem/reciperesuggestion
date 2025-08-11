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

# Configuration variables (can be overridden by command line arguments)
PROJECT_ID=${1:-""}
ZONE=${2:-"us-central1-a"}
INSTANCE_NAME=${3:-"recipe-gpu"}
GITHUB_REPO="https://github.com/turgutcem/reciperesuggestion.git"
BRANCH="gcp-gpu-deployment"

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
print_info "Machine Type: e2-standard-4 (4 vCPU, 16GB RAM)"
print_info "GPU: Tesla T4 (16GB VRAM)"
print_info "Estimated Cost: \$0.137/hour (preemptible)"
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
        print_info "Using existing instance"
    fi
fi

# Step 4: Create the instance with GPU
print_status "Creating e2-standard-4 instance with Tesla T4 GPU..."
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=e2-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-standard \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --preemptible \
    --max-run-duration=24h \
    --maintenance-policy=TERMINATE \
    --tags=http-server,https-server,recipe-server \
    --metadata=startup-script='#!/bin/bash
echo "Starting initial setup..." > /var/log/startup.log
apt-get update >> /var/log/startup.log 2>&1'

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

# Step 6: Wait for instance to be ready
print_status "Waiting for instance to be ready (this takes 1-2 minutes)..."
sleep 30

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
print_status "Installing NVIDIA drivers, Docker, and application..."
print_info "This will take 5-10 minutes. Please be patient..."

# Create the setup script
cat > /tmp/setup_instance.sh << 'SETUP_SCRIPT'
#!/bin/bash
set -e

echo "=== Starting Recipe Chat System Setup ==="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install NVIDIA drivers
echo "Installing NVIDIA drivers..."
sudo apt-get install -y linux-headers-$(uname -r)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID | sed -e 's/\.//g')
wget https://developer.download.nvidia.com/compute/cuda/repos/$distribution/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-drivers

# Install Docker
echo "Installing Docker..."
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Add user to docker group
sudo usermod -aG docker $USER

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
    git checkout $BRANCH || git checkout -b $BRANCH
    git pull origin $BRANCH || echo 'Branch not pushed yet'
else
    git clone $GITHUB_REPO
    cd reciperesuggestion
    git checkout $BRANCH || echo 'Using main branch'
fi

cd Recipes_Ingredients/recipe-chat-system

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo 'Creating .env file...'
    cp .env.example .env 2>/dev/null || cat > .env << 'EOF'
POSTGRES_DB=recipes_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/recipes_db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
SESSION_SECRET=your-secret-key-change-in-production
DEBUG=true
LANGFUSE_ENABLED=false
EOF
fi

# Start Docker services
echo 'Starting Docker services with GPU support...'
sudo docker-compose -f docker-compose.gpu.yml down 2>/dev/null || true
sudo docker-compose -f docker-compose.gpu.yml up -d

# Wait for services to be ready
echo 'Waiting for services to start (2 minutes)...'
sleep 120

# Check if GPU is being used
echo 'Checking GPU status...'
sudo docker exec recipe_ollama nvidia-smi || echo 'GPU check failed - will retry'

# Show running containers
echo 'Running containers:'
sudo docker ps

echo 'Deployment complete!'
"

# Step 10: Final status check and information
print_status "Verifying deployment..."
sleep 10

# Test if services are accessible
if curl -s -o /dev/null -w "%{http_code}" http://$EXTERNAL_IP:8501 | grep -q "200\|302"; then
    print_status "Frontend is accessible! ✓"
else
    print_warning "Frontend might still be starting up..."
fi

if curl -s -o /dev/null -w "%{http_code}" http://$EXTERNAL_IP:8001/health | grep -q "200"; then
    print_status "Backend API is accessible! ✓"
else
    print_warning "Backend API might still be starting up..."
fi

# Print summary
echo ""
echo "=============================================="
echo -e "${GREEN}   🎉 DEPLOYMENT COMPLETE! 🎉${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}📱 Access your application:${NC}"
echo -e "   Frontend: ${YELLOW}http://$EXTERNAL_IP:8501${NC}"
echo -e "   API Docs: ${YELLOW}http://$EXTERNAL_IP:8001/docs${NC}"
echo ""
echo -e "${BLUE}💰 Cost Information:${NC}"
echo "   Running: \$0.137/hour (\$3.29/day if running 24h)"
echo "   Stopped: \$0/hour (only pay for 50GB disk ~\$2/month)"
echo ""
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo "   SSH into instance:"
echo "   ${YELLOW}gcloud compute ssh $INSTANCE_NAME --zone=$ZONE${NC}"
echo ""
echo "   Stop instance (save money):"
echo "   ${YELLOW}gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE${NC}"
echo ""
echo "   Start instance:"
echo "   ${YELLOW}gcloud compute instances start $INSTANCE_NAME --zone=$ZONE${NC}"
echo ""
echo "   View logs:"
echo "   ${YELLOW}./scripts/manage-instance.sh logs${NC}"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Stop the instance when not in use to save money!${NC}"
echo "=============================================="