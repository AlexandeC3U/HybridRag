#!/bin/bash

# UNS Graph PoC Start Script
# This script starts all services and performs health checks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Docker is running
check_docker() {
    if ! command_exists docker; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Check if docker-compose file exists
check_compose_file() {
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found. Please run from the project root directory."
        exit 1
    fi
}

# Start services
start_services() {
    log_info "Starting UNS Graph PoC services..."
    
    # Check if services are already running
    if docker-compose ps | grep -q "Up"; then
        log_warning "Some services are already running. Stopping them first..."
        docker-compose down
    fi
    
    # Start services
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        log_success "Services started successfully"
    else
        log_error "Failed to start services"
        exit 1
    fi
}

# Health check function
health_check() {
    log_info "Performing health checks..."
    
    # Wait a bit for services to initialize
    sleep 10
    
    # Check Neo4j
    log_info "Checking Neo4j..."
    for i in {1..30}; do
        if curl -s -f "http://localhost:7474" >/dev/null 2>&1; then
            log_success "Neo4j is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_warning "Neo4j may still be starting up"
        fi
        sleep 2
    done
    
    # Check InfluxDB
    log_info "Checking InfluxDB..."
    for i in {1..30}; do
        if curl -s -f "http://localhost:8086/health" >/dev/null 2>&1; then
            log_success "InfluxDB is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_warning "InfluxDB may still be starting up"
        fi
        sleep 2
    done
    
    # Check Grafana
    log_info "Checking Grafana..."
    for i in {1..30}; do
        if curl -s -f "http://localhost:3000" >/dev/null 2>&1; then
            log_success "Grafana is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_warning "Grafana may still be starting up"
        fi
        sleep 2
    done
    
    # Check API (if it exists)
    log_info "Checking API..."
    for i in {1..30}; do
        if curl -s -f "http://localhost:8000/health" >/dev/null 2>&1; then
            log_success "API is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_warning "API may still be starting up or not configured"
        fi
        sleep 2
    done
    
    # Check MQTT Broker
    log_info "Checking MQTT Broker..."
    if docker-compose ps emqx | grep -q "Up"; then
        log_success "MQTT Broker is running"
    else
        log_warning "MQTT Broker may not be running properly"
    fi
}

# Display service information
display_info() {
    echo ""
    log_info "UNS Graph PoC Services Status:"
    echo ""
    
    # Show running containers
    docker-compose ps
    
    echo ""
    log_info "Access Information:"
    echo ""
    echo "🔗 Service URLs:"
    echo "  • Neo4j Browser:  http://localhost:7474"
    echo "  • InfluxDB UI:    http://localhost:8086"
    echo "  • Grafana:        http://localhost:3000"
    echo "  • UNS API:        http://localhost:8000"
    echo ""
    echo "🔐 Default Credentials:"
    echo "  • Neo4j:         neo4j / uns_secure_password_2024"
    echo "  • InfluxDB:      admin / uns_secure_password_2024"
    echo "  • Grafana:       admin / uns_secure_password_2024"
    echo ""
    echo "📊 MQTT Broker:    localhost:1883"
    echo ""
    echo "📖 Use 'docker-compose logs -f' to view logs"
    echo "🛑 Use './scripts/stop.sh' to stop services"
    echo ""
}

# Show logs if requested
show_logs() {
    if [ "$1" = "--logs" ] || [ "$1" = "-l" ]; then
        log_info "Showing service logs (Press Ctrl+C to exit)..."
        docker-compose logs -f
    fi
}

# Main function
main() {
    log_info "Starting UNS Graph PoC..."
    
    # Check prerequisites
    check_docker
    check_compose_file
    
    # Start services
    start_services
    
    # Perform health checks
    health_check
    
    # Display information
    display_info
    
    # Show logs if requested
    show_logs "$1"
}

# Script execution
case "${1:-start}" in
    start|--start)
        main
        ;;
    --logs|-l)
        main --logs
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Start UNS Graph PoC services"
        echo ""
        echo "Options:"
        echo "  --logs, -l    Start services and show logs"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0            Start services"
        echo "  $0 --logs     Start services and show logs"
        ;;
    *)
        log_error "Unknown option: $1"
        echo "Use '$0 --help' for usage information"
        exit 1
        ;;
esac