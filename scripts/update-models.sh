#!/bin/bash

# HybridRag Update Models Script
# Script to update or add new Ollama models

set -e

echo "🔄 Updating Ollama models..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if Ollama service is running
check_ollama() {
    if ! docker ps | grep -q hybrid-rag-ollama; then
        print_error "Ollama service is not running. Please start the services first."
        exit 1
    fi
    print_success "Ollama service is running"
}

# Pull specific model
pull_model() {
    local model=$1
    print_status "Pulling model: $model"
    docker exec hybrid-rag-ollama ollama pull "$model"
    print_success "Successfully pulled $model"
}

# Main execution
main() {
    echo "=========================================="
    echo "    HybridRag Model Update Script"
    echo "=========================================="
    echo ""
    
    check_ollama
    
    # Language models
    print_status "Updating language models..."
    pull_model "llama2:7b"
    pull_model "llama2:7b-chat-q4_0"
    pull_model "llama2:13b"
    pull_model "llama2:13b-chat-q4_0"
    
    # Embedding models
    print_status "Updating embedding models..."
    pull_model "nomic-embed-text"
    pull_model "all-minilm"
    
    # Additional models for different use cases
    print_status "Pulling additional models..."
    pull_model "codellama:7b"
    pull_model "mistral:7b"
    
    print_success "All models updated successfully!"
    
    echo ""
    print_status "Available models:"
    docker exec hybrid-rag-ollama ollama list
}

# Run main function
main "$@" 