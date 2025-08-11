#!/bin/bash
# Performance monitoring script for Recipe Chat System
# Run this to see real-time performance metrics

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"recipe-rag"}
ZONE=${GCP_ZONE:-"us-central1-a"}
INSTANCE_NAME=${GCP_INSTANCE_NAME:-"recipe-gpu"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Clear screen and show header
show_header() {
    clear
    echo -e "${CYAN}========================================"
    echo "   Recipe Chat System - Monitor"
    echo "   $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "========================================${NC}"
    echo ""
}

# Check if instance is running
check_instance() {
    STATUS=$(gcloud compute instances describe $INSTANCE_NAME \
        --zone=$ZONE --project=$PROJECT_ID \
        --format='get(status)' 2>/dev/null)
    
    if [ "$STATUS" != "RUNNING" ]; then
        echo -e "${RED}Instance is not running!${NC}"
        echo "Start it with: ./scripts/manage-instance.sh start"
        exit 1
    fi
}

# Main monitoring function
monitor() {
    check_instance
    
    # Get external IP
    EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
        --zone=$ZONE --project=$PROJECT_ID \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    while true; do
        show_header
        
        echo -e "${BLUE}Instance:${NC} $INSTANCE_NAME (n1-standard-4 + Tesla T4)"
        echo -e "${BLUE}External IP:${NC} $EXTERNAL_IP"
        echo ""
        
        # Run monitoring commands on the instance
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            echo -e '\033[0;33m=== GPU Status ===\033[0m'
            nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits | \
                awk -F', ' '{printf \"GPU: %s\\nMemory: %s/%s MB (%.1f%%)\\nUtilization: %s%%\\nTemperature: %s°C\\n\", \$1, \$2, \$3, (\$2/\$3)*100, \$4, \$5}'
            
            echo ''
            echo -e '\033[0;33m=== Docker Container Status ===\033[0m'
            sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Size}}' | grep recipe || echo 'No recipe containers running'
            
            echo ''
            echo -e '\033[0;33m=== Memory Usage ===\033[0m'
            free -h | grep -E 'Mem:|Swap:' | awk '{printf \"%-6s Total: %s  Used: %s  Free: %s\\n\", \$1, \$2, \$3, \$4}'
            
            echo ''
            echo -e '\033[0;33m=== Container Resource Usage ===\033[0m'
            sudo docker stats --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' | grep -E 'CONTAINER|recipe'
            
            echo ''
            echo -e '\033[0;33m=== GPU Memory by Container ===\033[0m'
            sudo docker exec recipe_ollama nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null && echo 'MB used by Ollama' || echo 'Ollama not using GPU'
            
            echo ''
            echo -e '\033[0;33m=== Disk Usage ===\033[0m'
            df -h / | tail -1 | awk '{printf \"Root: %s used of %s (Usage: %s)\\n\", \$3, \$2, \$5}'
            sudo du -sh /var/lib/docker 2>/dev/null | awk '{printf \"Docker: %s\\n\", \$1}'
        " 2>/dev/null
        
        # Test response time
        echo ""
        echo -e "${YELLOW}=== API Response Time ===${NC}"
        
        # Health check
        START=$(date +%s%N)
        if curl -s -o /dev/null -w "%{http_code}" http://$EXTERNAL_IP:8001/health | grep -q "200"; then
            END=$(date +%s%N)
            DURATION=$((($END - $START) / 1000000))
            echo -e "Health Check: ${GREEN}✓${NC} (${DURATION}ms)"
        else
            echo -e "Health Check: ${RED}✗${NC}"
        fi
        
        # Langfuse check
        if curl -s -o /dev/null -w "%{http_code}" http://$EXTERNAL_IP:3000 | grep -q "200\|302"; then
            echo -e "Langfuse UI: ${GREEN}✓${NC}"
        else
            echo -e "Langfuse UI: ${YELLOW}Not running${NC} (start with: manage-instance.sh langfuse-start)"
        fi
        
        echo ""
        echo -e "${CYAN}Refreshing in 5 seconds... (Ctrl+C to exit)${NC}"
        sleep 5
    done
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${GREEN}Monitoring stopped${NC}"; exit 0' INT

# Main execution
case "$1" in
    once)
        # Run once and exit
        check_instance
        show_header
        EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID \
            --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            echo '=== System Overview ==='
            echo 'Hostname:' \$(hostname)
            echo 'Uptime:' \$(uptime)
            echo ''
            echo '=== GPU Information ==='
            nvidia-smi
            echo ''
            echo '=== Docker Containers ==='
            sudo docker ps
            echo ''
            echo '=== Recent Backend Activity ==='
            sudo docker logs recipe_backend --tail=10 2>&1 | grep -E 'POST|GET|Error|WARNING' || echo 'No recent activity'
            echo ''
            echo '=== Ollama Models ==='
            sudo docker exec recipe_ollama ollama list 2>/dev/null || echo 'Ollama not ready'
        "
        ;;
    
    benchmark)
        # Run performance benchmark
        echo "🧪 Running Performance Benchmark..."
        check_instance
        
        EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
            --zone=$ZONE --project=$PROJECT_ID \
            --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        
        echo "Testing Chat API Performance with GPU..."
        echo "========================================"
        
        # Test queries
        QUERIES=(
            "I want Italian pasta with tomatoes"
            "Show me vegan breakfast recipes"
            "Quick dinner with chicken and rice"
            "Healthy salad recipes without nuts"
            "Mexican tacos with beef"
        )
        
        TOTAL_TIME=0
        COUNT=0
        
        for query in "${QUERIES[@]}"; do
            echo -n "Query: \"$query\""
            START=$(date +%s)
            
            RESPONSE=$(curl -s -X POST http://$EXTERNAL_IP:8001/chat/ \
                -H "Content-Type: application/json" \
                -d "{\"message\": \"$query\"}" 2>/dev/null)
            
            END=$(date +%s)
            DURATION=$((END - START))
            
            if [ ! -z "$RESPONSE" ]; then
                RECIPES=$(echo "$RESPONSE" | grep -o '"recipes"' | wc -l)
                echo -e " - ${GREEN}✓${NC} ${DURATION}s"
                TOTAL_TIME=$((TOTAL_TIME + DURATION))
                COUNT=$((COUNT + 1))
            else
                echo -e " - ${RED}✗${NC} Failed"
            fi
        done
        
        if [ $COUNT -gt 0 ]; then
            AVG=$((TOTAL_TIME / COUNT))
            echo ""
            echo "Results:"
            echo "  Successful queries: $COUNT/${#QUERIES[@]}"
            echo "  Average response time: ${AVG}s"
            echo "  Total time: ${TOTAL_TIME}s"
            
            if [ $AVG -lt 5 ]; then
                echo -e "  Performance: ${GREEN}Excellent${NC} (GPU acceleration working perfectly!)"
            elif [ $AVG -lt 10 ]; then
                echo -e "  Performance: ${GREEN}Good${NC} (GPU acceleration working)"
            elif [ $AVG -lt 20 ]; then
                echo -e "  Performance: ${YELLOW}Fair${NC} (Check GPU utilization)"
            else
                echo -e "  Performance: ${RED}Poor${NC} (GPU may not be working properly)"
            fi
            
            # Check GPU utilization during test
            echo ""
            echo "Current GPU status:"
            gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
                nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits
            " 2>/dev/null
        fi
        ;;
    
    gpu-test)
        # Test GPU functionality
        echo "🎮 Testing GPU Functionality..."
        check_instance
        
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
            echo '=== NVIDIA Driver Version ==='
            nvidia-smi --query-gpu=driver_version --format=csv,noheader
            
            echo ''
            echo '=== Testing GPU in Docker ==='
            sudo docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
            
            echo ''
            echo '=== Testing Ollama GPU Access ==='
            sudo docker exec recipe_ollama nvidia-smi 2>/dev/null && echo 'Ollama has GPU access' || echo 'Ollama cannot access GPU'
            
            echo ''
            echo '=== Ollama Model Info ==='
            sudo docker exec recipe_ollama ollama list
        "
        ;;
    
    *)
        # Continuous monitoring
        monitor
        ;;
esac