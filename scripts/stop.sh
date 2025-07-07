#!/bin/bash

# UNS Graph PoC Stop Script
# This script stops all services with various options

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
        log_error "Docker is not installed."
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_warning "Docker is not running. Services may already be stopped."
        return 1
    fi
    return 0
}

# Check if docker-compose file exists
check_compose_file() {
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found. Please run from the project root directory."
        exit 1
    fi
}

# Check if services are running
check_services_running() {
    if docker-compose ps | grep -q "Up"; then
        return 0  # Services are running
    else
        return 1  # No services running
    fi
}

# Stop services gracefully
stop_services() {
    log_info "Stopping UNS Graph PoC services..."
    
    if ! check_services_running; then
        log_warning "No services appear to be running"
        return 0
    fi
    
    # Stop services
    docker-compose down
    
    if [ $? -eq 0 ]; then
        log_success "Services stopped successfully"
    else
        log_error "Failed to stop services"
        exit 1
    fi
}

# Stop services and remove volumes
stop_with_volumes() {
    log_warning "Stopping services and removing volumes (this will delete all data)..."
    
    if ! check_services_running; then
        log_warning "No services appear to be running"
    fi
    
    # Confirm data deletion
    echo -e "${YELLOW}⚠️  This will permanently delete all data in the volumes!${NC}"
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down -v
        if [ $? -eq 0 ]; then
            log_success "Services stopped and volumes removed"
        else
            log_error "Failed to stop services and remove volumes"
            exit 1
        fi
    else
        log_info "Operation cancelled"
        exit 0
    fi
}

# Force stop services
force_stop() {
    log_warning "Force stopping services..."
    
    # Stop and remove containers
    docker-compose down --remove-orphans
    
    # Kill any remaining containers
    CONTAINERS=$(docker ps -a -q --filter "label=com.docker.compose.project=uns-graph-poc" 2>/dev/null || true)
    if [ -n "$CONTAINERS" ]; then
        log_info "Removing remaining containers..."
        docker rm -f $CONTAINERS
    fi
    
    log_success "Services force stopped"
}

# Clean up everything
clean_all() {
    log_warning "Cleaning up all UNS Graph PoC resources..."
    
    echo -e "${YELLOW}⚠️  This will remove:${NC}"
    echo "  • All containers"
    echo "  • All volumes (data will be lost)"
    echo "  • All networks"
    echo "  • All images (if --images flag is used)"
    echo ""
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stop and remove everything
        docker-compose down -v --remove-orphans
        
        # Remove networks
        NETWORKS=$(docker network ls -q --filter "name=uns-graph-poc" 2>/dev/null || true)
        if [ -n "$NETWORKS" ]; then
            log_info "Removing networks..."
            docker network rm $NETWORKS 2>/dev/null || true
        fi
        
        # Remove images if requested
        if [ "$1" = "--images" ]; then
            log_info "Removing images..."
            IMAGES=$(docker images -q --filter "reference=uns-graph-poc*" 2>/dev/null || true)
            if [ -n "$IMAGES" ]; then
                docker rmi $IMAGES 2>/dev/null || true
            fi
        fi
        
        # Clean up Docker system
        log_info "Cleaning up Docker system..."
        docker system prune -f
        
        log_success "Complete cleanup finished"
    else
        log_info "Cleanup cancelled"
        exit 0
    fi
}

# Show service status
show_status() {
    log_info "UNS Graph PoC Services Status:"
    echo ""
    
    if check_docker; then
        if check_compose_file; then
            docker-compose ps
        else
            log_warning "docker-compose.yml not found"
        fi
    else
        log_warning "Docker is not running"
    fi
    
    echo ""
    log_info "Docker containers related to UNS Graph PoC:"
    docker ps -a --filter "label=com.docker.compose.project=uns-graph-poc" 2>/dev/null || log_warning "No containers found"
}

# Display usage information
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Stop UNS Graph PoC services"
    echo ""
    echo "Commands:"
    echo "  stop          Stop services gracefully (default)"
    echo "  --volumes     Stop services and remove volumes (deletes data)"
    echo "  --force       Force stop services"
    echo "  --clean       Clean up all resources"
    echo "  --status      Show service status"
    echo "  --help        Show this help message"
    echo ""
    echo "Options:"
    echo "  --images      Remove images (use with --clean)"
    echo ""
    echo "Examples:"
    echo "  $0                    Stop services"
    echo "  $0 --volumes          Stop services and remove data"
    echo "  $0 --force            Force stop services"
    echo "  $0 --clean            Clean up everything"
    echo "  $0 --clean --images   Clean up everything including images"
    echo "  $0 --status           Show service status"
}

# Main function
main() {
    # Check prerequisites
    check_docker
    check_compose_file
    
    case "${1:-stop}" in
        stop|--stop)
            stop_services
            ;;
        --volumes|-v)
            stop_with_volumes
            ;;
        --force|-f)
            force_stop
            ;;
        --clean|-c)
            clean_all "$2"
            ;;
        --status|-s)
            show_status
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Script execution
main "$@"