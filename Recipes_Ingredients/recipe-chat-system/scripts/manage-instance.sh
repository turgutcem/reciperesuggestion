#!/bin/bash
# Daily management script for Recipe Chat System on GCP
# Use this script for starting, stopping, and managing your instance

# Configuration (modify these if needed)
PROJECT_ID=${GCP_PROJECT_ID:-"recipe-rag"}
ZONE=${GCP_ZONE:-"us-central1-a"}
INSTANCE_NAME=${GCP_INSTANCE_NAME:-"recipe-gpu"}

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

# Check if gcloud is configured
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if [ -z "$(gcloud config get-value project 2>/dev/null)" ]; then
        print_info "Setting project to $PROJECT_ID"
        gcloud config set project $PROJECT_ID
    fi
}

# Main script
check_gcloud

case "$1" in
    start)
        echo "🚀 Starting Recipe Chat System..."
        
        # Start the instance
        print_info "Starting instance $INSTANCE_NAME..."
        gcloud compute instances start $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID
        
        # Wait for instance to be ready
        print_info "Waiting for instance to be ready..."
        sleep 30
        
        # Get external IP
        EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID \
            --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        
        # Start Docker containers
        print_info "Starting Docker containers..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            cd ~/reciperesuggestion/Recipes_Ingredients/recipe-chat-system
            sudo docker-compose -f docker-compose.gpu.yml up -d
            sleep 10
            sudo docker ps
        " 2>/dev/null
        
        echo ""
        print_status "Application is starting up!"
        echo ""
        echo "📱 Access your application at:"
        echo "   Frontend: ${YELLOW}http://$EXTERNAL_IP:8501${NC}"
        echo "   API Docs: ${YELLOW}http://$EXTERNAL_IP:8001/docs${NC}"
        echo ""
        echo "Note: It may take 1-2 minutes for the application to be fully ready"
        ;;
    
    stop)
        echo "🛑 Stopping Recipe Chat System..."
        
        # Get current status
        STATUS=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID --format='get(status)' 2>/dev/null)
        
        if [ "$STATUS" = "TERMINATED" ]; then
            print_info "Instance is already stopped"
        else
            # Stop Docker containers first
            print_info "Stopping Docker containers..."
            gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
                cd ~/reciperesuggestion/Recipes_Ingredients/recipe-chat-system
                sudo docker-compose -f docker-compose.gpu.yml down
            " 2>/dev/null || true
            
            # Stop the instance
            print_info "Stopping instance..."
            gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID
            
            print_status "Instance stopped successfully!"
            echo "💰 You are now saving \$0.137/hour"
        fi
        ;;
    
    restart)
        echo "🔄 Restarting Recipe Chat System..."
        $0 stop
        sleep 5
        $0 start
        ;;
    
    status)
        echo "📊 Recipe Chat System Status"
        echo "============================"
        
        # Get instance status
        STATUS=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID \
            --format='get(status)' 2>/dev/null || echo "NOT_FOUND")
        
        if [ "$STATUS" = "NOT_FOUND" ]; then
            print_error "Instance $INSTANCE_NAME not found"
            exit 1
        fi
        
        echo "Instance: $INSTANCE_NAME"
        echo "Project: $PROJECT_ID"
        echo "Zone: $ZONE"
        
        if [ "$STATUS" = "RUNNING" ]; then
            echo -e "Status: ${GREEN}RUNNING${NC} (costing \$0.137/hour)"
            
            # Get external IP
            EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
                --zone=$ZONE --project=$PROJECT_ID \
                --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
            echo "External IP: $EXTERNAL_IP"
            
            # Check Docker containers
            echo ""
            echo "Docker Containers:"
            gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
                sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
            " 2>/dev/null || print_warning "Could not fetch container status"
            
            # URLs
            echo ""
            echo "📱 Access URLs:"
            echo "   Frontend: http://$EXTERNAL_IP:8501"
            echo "   API Docs: http://$EXTERNAL_IP:8001/docs"
        else
            echo -e "Status: ${YELLOW}$STATUS${NC} (not costing money)"
        fi
        ;;
    
    ssh)
        print_info "Connecting to instance via SSH..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID
        ;;
    
    logs)
        echo "📜 Showing logs (last 50 lines, Ctrl+C to exit)..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            cd ~/reciperesuggestion/Recipes_Ingredients/recipe-chat-system
            sudo docker-compose -f docker-compose.gpu.yml logs --tail=50 -f
        "
        ;;
    
    logs-backend)
        echo "📜 Showing backend logs..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            sudo docker logs recipe_backend --tail=100 -f
        "
        ;;
    
    logs-ollama)
        echo "📜 Showing Ollama logs..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            sudo docker logs recipe_ollama --tail=100 -f
        "
        ;;
    
    gpu)
        echo "🎮 GPU Status:"
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            echo '=== GPU Information ==='
            nvidia-smi
            echo ''
            echo '=== GPU Usage by Ollama Container ==='
            sudo docker exec recipe_ollama nvidia-smi 2>/dev/null || echo 'Ollama container not running'
        "
        ;;
    
    test)
        echo "🧪 Testing Recipe Chat API..."
        
        # Get IP
        EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID \
            --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        
        # Test health endpoint
        print_info "Testing health endpoint..."
        curl -s http://$EXTERNAL_IP:8001/health | python3 -m json.tool || print_error "Health check failed"
        
        # Test chat endpoint
        print_info "Testing chat endpoint (this may take 5-10 seconds)..."
        echo ""
        
        START_TIME=$(date +%s)
        RESPONSE=$(curl -s -X POST http://$EXTERNAL_IP:8001/chat/ \
            -H "Content-Type: application/json" \
            -d '{"message": "I want quick Italian pasta with tomatoes"}')
        END_TIME=$(date +%s)
        
        DURATION=$((END_TIME - START_TIME))
        
        if [ ! -z "$RESPONSE" ]; then
            print_status "Chat API responded in ${DURATION} seconds"
            echo ""
            echo "Response preview:"
            echo "$RESPONSE" | python3 -m json.tool | head -20
            echo "..."
        else
            print_error "No response from chat API"
        fi
        ;;
    
    cost)
        echo "💰 Cost Analysis for Recipe Chat System"
        echo "======================================="
        
        # Get current status
        STATUS=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID --format='get(status)' 2>/dev/null)
        
        echo "Instance: $INSTANCE_NAME (e2-standard-4 + Tesla T4)"
        echo ""
        echo "Pricing (Preemptible):"
        echo "  When RUNNING: \$0.137/hour"
        echo "  When STOPPED: \$0.00/hour"
        echo "  Disk storage: ~\$2/month (50GB)"
        echo ""
        echo "Cost Scenarios:"
        echo "  8 hours/day:  \$32.88/month"
        echo "  12 hours/day: \$49.32/month" 
        echo "  24 hours/day: \$98.64/month"
        echo ""
        
        if [ "$STATUS" = "RUNNING" ]; then
            echo -e "Current Status: ${GREEN}RUNNING${NC}"
            echo "You are currently being charged \$0.137/hour"
            echo ""
            echo "💡 Tip: Run './scripts/manage-instance.sh stop' when not using"
        else
            echo -e "Current Status: ${YELLOW}STOPPED${NC}"
            echo "You are currently being charged \$0/hour (only disk storage)"
        fi
        ;;
    
    update)
        echo "🔄 Updating application code..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            cd ~/reciperesuggestion/Recipes_Ingredients/recipe-chat-system
            echo 'Pulling latest code...'
            git pull
            echo 'Rebuilding containers...'
            sudo docker-compose -f docker-compose.gpu.yml build
            echo 'Restarting services...'
            sudo docker-compose -f docker-compose.gpu.yml down
            sudo docker-compose -f docker-compose.gpu.yml up -d
            echo 'Update complete!'
            sudo docker ps
        "
        ;;
    
    backup)
        echo "💾 Creating backup of database..."
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="recipe_backup_$TIMESTAMP.sql"
        
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            sudo docker exec recipe_postgres pg_dump -U postgres recipes_db > /tmp/$BACKUP_FILE
            echo 'Backup created: /tmp/$BACKUP_FILE'
            ls -lh /tmp/$BACKUP_FILE
        "
        
        # Download backup to local machine
        print_info "Downloading backup to local machine..."
        gcloud compute scp $INSTANCE_NAME:/tmp/$BACKUP_FILE ./$BACKUP_FILE --zone=$ZONE
        print_status "Backup saved to: ./$BACKUP_FILE"
        ;;
    
    *)
        echo "Recipe Chat System - GCP Instance Manager"
        echo "=========================================="
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  start         - Start the instance and application"
        echo "  stop          - Stop the instance (save money)"
        echo "  restart       - Restart the instance and application"
        echo "  status        - Show current status"
        echo "  ssh           - SSH into the instance"
        echo "  logs          - Show all container logs"
        echo "  logs-backend  - Show only backend logs"
        echo "  logs-ollama   - Show only Ollama logs"
        echo "  gpu           - Show GPU status"
        echo "  test          - Test the API endpoints"
        echo "  cost          - Show cost analysis"
        echo "  update        - Update application code"
        echo "  backup        - Backup the database"
        echo ""
        echo "Configuration:"
        echo "  Project: $PROJECT_ID"
        echo "  Zone: $ZONE"
        echo "  Instance: $INSTANCE_NAME"
        echo ""
        echo "To use different settings, set environment variables:"
        echo "  export GCP_PROJECT_ID=your-project"
        echo "  export GCP_ZONE=us-central1-a"
        echo "  export GCP_INSTANCE_NAME=recipe-gpu"
        exit 1
        ;;
esac