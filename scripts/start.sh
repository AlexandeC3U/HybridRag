#!/bin/bash

# HybridRag Start Script
# Quick script to start all services

set -e

echo "🚀 Starting HybridRag services..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please run setup.sh first."
    exit 1
fi

# Start services
print_status "Starting all services..."
docker-compose up -d

print_success "Services started successfully!"

echo ""
echo "Service URLs:"
echo "  - Neo4j Browser: http://localhost:7474"
echo "  - Qdrant Dashboard: http://localhost:6333"
echo "  - Ollama API: http://localhost:11434"
echo "  - FastAPI App: http://localhost:8000"
echo "  - API Documentation: http://localhost:8000/docs"

echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop services: docker-compose down" 