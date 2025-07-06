#!/bin/bash

# HybridRag Setup Script
# This script sets up the environment and pulls necessary Ollama models

set -e

echo "🚀 Setting up HybridRag..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Check if Docker Compose is available
check_docker_compose() {
    if ! docker-compose --version > /dev/null 2>&1; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
    print_success "Docker Compose is available"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p data
    mkdir -p logs
    mkdir -p nginx/ssl
    
    print_success "Directories created"
}

# Copy environment file if it doesn't exist
setup_environment() {
    if [ ! -f .env ]; then
        print_status "Creating .env file from template..."
        cp env.example .env
        print_warning "Please edit .env file with your configuration"
    else
        print_success ".env file already exists"
    fi
}

# Pull Ollama models
pull_ollama_models() {
    print_status "Starting Ollama service to pull models..."
    
    # Start Ollama service
    docker-compose up -d ollama
    
    # Wait for Ollama to be ready
    print_status "Waiting for Ollama to be ready..."
    timeout=120
    counter=0
    
    while [ $counter -lt $timeout ]; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            print_success "Ollama is ready"
            break
        fi
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_error "Ollama failed to start within $timeout seconds"
        exit 1
    fi
    
    # Pull language models
    print_status "Pulling language models..."
    
    # Pull a good general-purpose model
    docker exec hybrid-rag-ollama ollama pull llama2:7b
    print_success "Pulled llama2:7b"
    
    # Pull a smaller, faster model for development
    docker exec hybrid-rag-ollama ollama pull llama2:7b-chat-q4_0
    print_success "Pulled llama2:7b-chat-q4_0"
    
    # Pull embedding models
    print_status "Pulling embedding models..."
    
    # Pull a good embedding model
    docker exec hybrid-rag-ollama ollama pull nomic-embed-text
    print_success "Pulled nomic-embed-text"
    
    print_success "All Ollama models pulled successfully"
}

# Build and start all services
start_services() {
    print_status "Building and starting all services..."
    
    docker-compose up -d --build
    
    print_success "All services started"
}

# Show status
show_status() {
    print_status "Checking service status..."
    
    docker-compose ps
    
    echo ""
    print_status "Service URLs:"
    echo "  - Neo4j Browser: http://localhost:7474"
    echo "  - Qdrant Dashboard: http://localhost:6333"
    echo "  - Ollama API: http://localhost:11434"
    echo "  - FastAPI App: http://localhost:8000"
    echo "  - API Documentation: http://localhost:8000/docs"
    
    echo ""
    print_success "Setup complete! 🎉"
    print_warning "Remember to:"
    echo "  1. Edit .env file with your configuration"
    echo "  2. Check the logs if any service fails to start"
    echo "  3. Visit http://localhost:8000/docs to test the API"
}

# Main execution
main() {
    echo "=========================================="
    echo "    HybridRag Setup Script"
    echo "=========================================="
    echo ""
    
    check_docker
    check_docker_compose
    create_directories
    setup_environment
    pull_ollama_models
    start_services
    show_status
}

# Run main function
main "$@" 