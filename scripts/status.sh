#!/bin/bash

# UNS Graph PoC Status Script
# This script checks the status of all services and performs health checks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "${CYAN}=== $1 ===${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Docker is running
check_docker() {
    if ! command_exists docker; then
        log_error "Docker is not installed"
        return 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        return 1
    fi
    
    log_success "Docker is running"
    return 0
}

# Check if docker-compose file exists
check_compose_file() {
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found. Please run from the project root directory."
        return 1
    fi
    
    log_success "docker-compose.yml found"
    return 0
}

# Show container status
show_container_status() {
    log_header "Container Status"
    
    if docker-compose ps 2>/dev/null; then
        echo ""
    else
        log_warning "Failed to get container status"
        return 1
    fi
}

# Health check for individual services
health_check_neo4j() {
    local status="❌"
    local details=""
    
    if curl -s -f "http://localhost:7474" >/dev/null 2>&1; then
        status="✅"
        details="Accessible"
    else
        details="Not accessible"
    fi
    
    echo -e "Neo4j Browser:   $status http://localhost:7474 ($details)"
    
    # Check if Neo4j is accepting connections
    if docker-compose exec -T neo4j cypher-shell -u neo4j -p uns_secure_password_2024 "RETURN 1" >/dev/null 2>&1; then
        echo -e "Neo4j Database:  ✅ Database responding"
    else
        echo -e "Neo4j Database:  ❌ Database not responding"
    fi
}

health_check_influxdb() {
    local status="❌"
    local details=""
    
    if curl -s -f "http://localhost:8086/health" >/dev/null 2>&1; then
        status="✅"
        details="Healthy"
    else
        details="Not healthy"
    fi
    
    echo -e "InfluxDB:        $status http://localhost:8086 ($details)"
}

health_check_grafana() {
    local status="❌"
    local details=""
    
    if curl -s -f "http://localhost:3000" >/dev/null 2>&1; then
        status="✅"
        details="Accessible"
    else
        details="Not accessible"
    fi
    
    echo -e "Grafana:         $status http://localhost:3000 ($details)"
}

health_check_api() {
    local status="❌"
    local details=""
    
    if curl -s -f "http://localhost:8000/health" >/dev/null 2>&1; then
        status="✅"
        details="Healthy"
    elif curl -s -f "http://localhost:8000" >/dev/null 2>&1; then
        status="⚠️"
        details="Responding (no health endpoint)"
    else
        details="Not responding"
    fi
    
    echo -e "API Service:     $status http://localhost:8000 ($details)"
}

health_check_mqtt() {
    local status="❌"
    local details=""
    
    # Check if MQTT container is running
    if docker-compose ps emqx 2>/dev/null | grep -q "Up"; then
        status="✅"
        details="Running"
    else
        details="Not running"
    fi
    
    echo -e "MQTT Broker:     $status localhost:1883 ($details)"
}

# Perform all health checks
perform_health_checks() {
    log_header "Service Health Checks"
    
    health_check_neo4j
    health_check_influxdb
    health_check_grafana
    health_check_api
    health_check_mqtt
    echo ""
}

# Show resource usage
show_resource_usage() {
    log_header "Resource Usage"
    
    if command_exists docker; then
        echo "Container Resource Usage:"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker-compose ps -q) 2>/dev/null || log_warning "Could not get resource usage"
        echo ""
    fi
}

# Show logs summary
show_logs_summary() {
    log_header "Recent Logs Summary"
    
    echo "Recent errors from all services:"
    docker-compose logs --tail=10 2>/dev/null | grep -i error || echo "No recent errors found"
    echo ""
}

# Show network information
show_network_info() {
    log_header "Network Information"
    
    echo "Port Mappings:"
    docker-compose ps --format "table {{.Service}}\t{{.Ports}}" 2>/dev/null || log_warning "Could not get port information"
    echo ""
}

# Show volume information
show_volume_info() {
    log_header "Volume Information"
    
    echo "Docker Volumes:"
    docker volume ls --filter "name=uns-graph-poc" 2>/dev/null || log_warning "Could not get volume information"
    echo ""
}

# Show quick access information
show_access_info() {
    log_header "Quick Access Information"
    
    echo "🔗 Service URLs:"
    echo "  • Neo4j Browser:  http://localhost:7474"
    echo "  • InfluxDB UI:    http://localhost:8086"
    echo "  • Grafana:        http://localhost:3000"
    echo "  • API Service:    http://localhost:8000"
    echo ""
    echo "🔐 Default Credentials:"
    echo "  • Neo4j:         neo4j / uns_secure_password_2024"
    echo "  • InfluxDB:      admin / uns_secure_password_2024"
    echo "  • Grafana:       admin / uns_secure_password_2024"
    echo ""
    echo "📊 MQTT Broker:    localhost:1883"
    echo ""
}

# Show useful commands
show_commands() {
    log_header "Useful Commands"
    
    echo "Common operations:"
    echo "  • View logs:           docker-compose logs -f"
    echo "  • View specific logs:  docker-compose logs -f [service_name]"
    echo "  • Restart service:     docker-compose restart [service_name]"
    echo "  • Stop all services:   ./scripts/stop.sh"
    echo "  • Start all services:  ./scripts/start.sh"
    echo ""
}

# Main status check
main() {
    log_info "Checking UNS Graph PoC Status..."
    echo ""
    
    # Check prerequisites
    if ! check_docker; then
        exit 1
    fi
    
    if ! check_compose_file; then
        exit 1
    fi
    
    # Show various status information
    show_container_status
    perform_health_checks
    
    case "${1:-full}" in
        full|--full)
            show_resource_usage
            show_network_info
            show_volume_info
            show_access_info
            show_commands
            ;;
        health|--health)
            # Health checks already performed above
            ;;
        quick|--quick)
            show_access_info
            ;;
        logs|--logs)
            show_logs_summary
            ;;
        resources|--resources)
            show_resource_usage
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown option: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Show usage information
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Check UNS Graph PoC status and health"
    echo ""
    echo "Options:"
    echo "  full        Show full status information (default)"
    echo "  --health    Show only health checks"
    echo "  --quick     Show quick access information"
    echo "  --logs      Show recent logs summary"
    echo "  --resources Show resource usage"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0             Show full status"
    echo "  $0 --health    Show only health checks"
    echo "  $0 --quick     Show access URLs and credentials"
}

# Script execution
main "$@"