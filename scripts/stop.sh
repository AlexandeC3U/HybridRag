#!/bin/bash

# HybridRag Stop Script
# Quick script to stop all services

set -e

echo "🛑 Stopping HybridRag services..."

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

# Stop services
print_status "Stopping all services..."
docker-compose down

print_success "Services stopped successfully!"

echo ""
echo "To start services again: ./scripts/start.sh"
echo "To remove all data: docker-compose down -v" 