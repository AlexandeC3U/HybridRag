#!/bin/bash

# UNS Graph PoC Setup Script
# This script sets up the entire development environment

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

# Main setup function
main() {
    log_info "Starting UNS Graph PoC Setup..."
    
    # Check prerequisites
    check_prerequisites
    
    # Setup project structure
    setup_project_structure
    
    # Configure environment
    setup_environment
    
    # Generate secure tokens
    generate_secure_tokens
    
    # Setup configurations
    setup_configurations
    
    # Build and start services
    build_and_start
    
    # Initialize data
    initialize_data
    
    # Display access information
    display_access_info
    
    log_success "Setup completed successfully!"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command_exists docker; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command_exists docker-compose; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

setup_project_structure() {
    log_info "Setting up project structure..."
    
    # Create directory structure
    mkdir -p {api,simulator,neo4j/init,emqx/{config,data,log},grafana/{provisioning/{datasources,dashboards},dashboards},data,docs,scripts,tests}
    
    log_success "Project structure created"
}

setup_environment() {
    log_info "Setting up environment configuration..."
    
    if [ ! -f .env ]; then
        log_info "Creating .env file from template..."
        cp .env.example .env 2>/dev/null || true
    else
        log_warning ".env file already exists, skipping creation"
    fi
    
    log_success "Environment configuration ready"
}

generate_secure_tokens() {
    log_info "Generating secure tokens..."
    
    # Generate InfluxDB token
    if command_exists openssl; then
        INFLUXDB_TOKEN=$(openssl rand -hex 32)
        JWT_SECRET=$(openssl rand -hex 64)
        
        # Update .env file
        if [ -f .env ]; then
            sed -i.bak "s/change_me_to_secure_token_32_chars_long/$INFLUXDB_TOKEN/g" .env
            sed -i.bak "s/change_me_to_secure_jwt_secret_64_chars_long/$JWT_SECRET/g" .env
            rm .env.bak
        fi
        
        log_success "Secure tokens generated"
    else
        log_warning "OpenSSL not found, please manually update tokens in .env file"
    fi
}

setup_configurations() {
    log_info "Setting up service configurations..."
    
    # Neo4j initialization script
    cat > neo4j/init/01-init.cypher << EOF
// UNS Graph PoC Initialization Script
// This script sets up the initial graph schema and constraints

// Create constraints
CREATE CONSTRAINT asset_name_unique IF NOT EXISTS FOR (a:Asset) REQUIRE a.name IS UNIQUE;
CREATE CONSTRAINT sensor_name_unique IF NOT EXISTS FOR (s:Sensor) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT site_name_unique IF NOT EXISTS FOR (s:Site) REQUIRE s.name IS UNIQUE;

// Create indexes for performance
CREATE INDEX asset_type_index IF NOT EXISTS FOR (a:Asset) ON (a.type);
CREATE INDEX sensor_type_index IF NOT EXISTS FOR (s:Sensor) ON (s.type);
CREATE INDEX timestamp_index IF NOT EXISTS FOR (e:Event) ON (e.timestamp);

// Initialize n10s plugin
CALL n10s.graphconfig.init({
  handleVocabUris: "IGNORE",
  handleMultival: "ARRAY",
  multivalPropList: ["tags", "categories"],
  keepLangTag: true
});

// Create sample data
CREATE (site:Site {name: 'PlantA', type: 'manufacturing', location: 'Factory North'})
CREATE (area:Asset {name: 'Area1', type: 'area', level: 2})
CREATE (line:Asset {name: 'Line1', type: 'line', level: 3})
CREATE (machine:Asset {name: 'Machine1', type: 'cnc_mill', level: 4})
CREATE (sensor1:Sensor {name: 'TempSensor1', type: 'temperature', unit: 'celsius', range_min: -20, range_max: 100})
CREATE (sensor2:Sensor {name: 'VibSensor1', type: 'vibration', unit: 'mm/s', range_min: 0, range_max: 50})

// Create relationships
CREATE (site)-[:CONTAINS {level: 'area'}]->(area)
CREATE (area)-[:CONTAINS {level: 'line'}]->(line)
CREATE (line)-[:CONTAINS {level: 'machine'}]->(machine)
CREATE (machine)-[:HAS_SENSOR {install_date: date('2024-01-01')}]->(sensor1)
CREATE (machine)-[:HAS_SENSOR {install_date: date('2024-01-01')}]->(sensor2);
EOF
    
    # Grafana datasource configuration
    mkdir -p grafana/provisioning/datasources
    cat > grafana/provisioning/datasources/influxdb.yml << EOF
apiVersion: 1

datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    database: sensor_data
    user: admin
    password: uns_secure_password_2024
    version: 2.0
    jsonData:
      organization: UNS_Organization
      defaultBucket: sensor_data
      version: Flux
    secureJsonData:
      token: \${INFLUXDB_TOKEN}
EOF
    
    log_success "Service configurations created"
}

build_and_start() {
    log_info "Building and starting services..."
    
    # Create API Dockerfile
    mkdir -p api
    cat > api/Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
EOF
    
    # Create API requirements
    cat > api/requirements.txt << EOF
fastapi==0.104.1
uvicorn==0.24.0
neo4j==5.14.0
influxdb-client==1.38.0
paho-mqtt==1.6.1
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
aiofiles==23.2.1
httpx==0.25.2
EOF
    
    # Create simulator Dockerfile
    mkdir -p simulator
    cat > simulator/Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Command to run the simulator
CMD ["python", "simulator.py"]
EOF
    
    # Create simulator requirements
    cat > simulator/requirements.txt << EOF
neo4j==5.14.0
paho-mqtt==1.6.1
schedule==1.2.0
random-word==1.0.11
EOF
    
    # Start services
    log_info "Starting Docker services..."
    docker-compose up -d --build
    
    log_success "Services started successfully"
}

initialize_data() {
    log_info "Initializing data..."
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check if Neo4j is ready
    for i in {1..30}; do
        if docker-compose exec -T neo4j cypher-shell -u neo4j -p uns_secure_password_2024 "RETURN 1" >/dev/null 2>&1; then
            log_success "Neo4j is ready"
            break
        fi
        log_info "Waiting for Neo4j to be ready... ($i/30)"
        sleep 5
    done
    
    log_success "Data initialization completed"
}

display_access_info() {
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
    echo "📖 Documentation:  ./docs/README.md"
    echo "🔧 Configuration:  .env file"
    echo ""
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    docker-compose down
    log_success "Cleanup completed"
}

# Script execution
case "${1:-setup}" in
    setup)
        main
        ;;
    start)
        log_info "Starting UNS Graph PoC services..."
        docker-compose up -d
        log_success "Services started"
        ;;
    stop)
        log_info "Stopping UNS Graph PoC services..."
        docker-compose down
        log_success "Services stopped"
        ;;
    restart)
        log_info "Restarting UNS Graph PoC services..."
        docker-compose restart
        log_success "Services restarted"
        ;;
    clean)
        log_warning "This will remove all containers, volumes, and data!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cleanup
            docker-compose down -v --remove-orphans
            docker system prune -f
            log_success "Complete cleanup finished"
        else
            log_info "Cleanup cancelled"
        fi
        ;;
    logs)
        docker-compose logs -f
        ;;
    status)
        docker-compose ps
        ;;
    *)
        echo "Usage: $0 {setup|start|stop|restart|clean|logs|status}"
        echo ""
        echo "Commands:"
        echo "  setup     - Initial setup and start (default)"
        echo "  start     - Start all services"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  clean     - Remove all containers and data"
        echo "  logs      - Show service logs"
        echo "  status    - Show service status"
        exit 1
        ;;
esac