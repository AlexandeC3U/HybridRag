# UNS Graph PoC: Unified Namespace with Graph Database

A proof-of-concept implementation of a Unified Namespace (UNS) architecture leveraging graph databases for industrial IoT systems. This project demonstrates how to model industrial assets, equipment, and sensors as a connected graph while maintaining high-performance time-series data storage.

## 🎯 Project Overview

The Unified Namespace (UNS) concept centralizes all industrial data into a single, standardized namespace that enables seamless data exchange between different systems, applications, and stakeholders. This implementation uses a graph database to model the relationships between industrial assets and their hierarchical structure.

### Key Features

- **Graph-Based Asset Modeling**: Industrial hierarchy (Site → Area → Line → Machine → Sensor) represented as a connected graph
- **Semantic Extensibility**: Support for RDF/OWL ontologies via Neo4j's n10s plugin
- **Time-Series Integration**: High-performance sensor data storage with InfluxDB
- **Real-Time Messaging**: MQTT broker for industrial IoT communication
- **Unified API**: RESTful API providing access to both graph and time-series data
- **Visualization**: Grafana dashboards for operational insights
- **Containerized**: Complete Docker-based development environment

## 🏗️ Architecture

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Graph Database | Neo4j Community + n10s plugin | Asset hierarchy and relationships |
| Time-Series DB | InfluxDB 2.0 | High-performance sensor data storage |
| Message Broker | EMQX | MQTT communication |
| API Gateway | FastAPI | Unified REST API |
| Visualization | Grafana | Dashboards and analytics |
| Containerization | Docker Compose | Development environment |

### Architecture Decision Process

We evaluated multiple approaches for the UNS implementation:

#### 1. RDF Triple Store + SPARQL
*Examples: Apache Jena, Blazegraph, GraphDB*

**Pros:**
- Standards-based (RDF, OWL, RDFS)
- Rich semantic modeling capabilities
- Excellent interoperability with industrial standards
- Built-in reasoning capabilities

**Cons:**
- Verbose modeling and querying
- Steep learning curve for developers
- Limited visualization tools
- Performance concerns for large datasets

#### 2. Property Graph + Cypher
*Examples: Neo4j, Memgraph, ArangoDB*

**Pros:**
- Intuitive object modeling
- Developer-friendly query language
- Strong visualization ecosystem
- Excellent traversal performance

**Cons:**
- Limited semantic web standards support
- Requires additional tooling for ontology management
- Vendor-specific query languages

#### 3. Multi-Model Database
*Examples: ArangoDB, Amazon Neptune*

**Pros:**
- Single database for multiple data models
- Unified query language
- Operational simplicity

**Cons:**
- Less mature ecosystem
- Limited semantic capabilities
- Fewer specialized tools

#### 4. Hybrid Approach (Our Choice)
*Neo4j + n10s plugin + InfluxDB*

**Selected for:**
- **Rapid Development**: Cypher provides intuitive graph querying
- **Semantic Extensibility**: n10s plugin enables RDF/OWL import
- **Performance**: Dedicated time-series storage with InfluxDB
- **Ecosystem**: Rich tooling and visualization options
- **Future-Proofing**: Can evolve to full semantic web standards

### Data Flow Architecture

```
Industrial Systems → MQTT Broker → Data Router
                                      ├── Neo4j (Asset Graph)
                                      └── InfluxDB (Time Series)
                                           ↓
                                      Unified API
                                           ↓
                                   Grafana Dashboards
```

## 📊 Data Models

### Graph Schema

The graph models the industrial hierarchy using the following node types:

- **Site**: Top-level facility (e.g., manufacturing plant)
- **Asset**: Generic industrial asset (Area, Line, Machine, etc.)
- **Sensor**: Measurement devices attached to assets

**Relationship Types:**
- `CONTAINS`: Hierarchical containment (Site contains Areas, etc.)
- `HAS_SENSOR`: Asset to sensor relationships
- `CONNECTS_TO`: Equipment interconnections
- `PART_OF`: Component relationships

### Time-Series Schema

InfluxDB stores sensor measurements with the following structure:

- **measurement**: `sensor_data`
- **tags**: `site`, `area`, `line`, `machine`, `sensor_type`, `unit`
- **fields**: `value`, `quality`, `status`
- **time**: `timestamp`

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- 4GB+ available RAM
- Ports 7474, 7687, 8086, 1883, 3000, 8000 available

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd uns-graph-poc
   ```

2. **Run the setup script**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

   The setup script will:
   - Create project structure
   - Generate secure tokens
   - Configure services
   - Build and start containers
   - Initialize sample data

3. **Access the services**
   - Neo4j Browser: http://localhost:7474
   - InfluxDB UI: http://localhost:8086
   - Grafana: http://localhost:3000
   - UNS API: http://localhost:8000

### Manual Setup

If you prefer manual setup:

1. **Copy environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **Initialize data**
   ```bash
   # Wait for services to start, then run initialization
   ./scripts/init-data.sh
   ```

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Database Credentials
NEO4J_PASSWORD=your_secure_password
INFLUXDB_PASSWORD=your_secure_password
INFLUXDB_TOKEN=your_secure_token

# Service Ports
NEO4J_HTTP_PORT=7474
INFLUXDB_PORT=8086
MQTT_PORT=1883

# Security
JWT_SECRET=your_jwt_secret
```

### Service Configuration

- **Neo4j**: Configuration in `neo4j/init/`
- **InfluxDB**: Auto-configured via environment variables
- **EMQX**: Configuration via environment variables and EMQX Dashboard (http://localhost:18083)
- **Grafana**: Provisioning in `grafana/provisioning/`

## 📈 Usage Examples

### Graph Queries

**Find all sensors in a plant:**
```cypher
MATCH (s:Site {name: 'PlantA'})-[:CONTAINS*]->(sensor:Sensor)
RETURN sensor.name, sensor.type, sensor.unit
```

**Get equipment hierarchy:**
```cypher
MATCH path = (site:Site)-[:CONTAINS*]->(asset:Asset)
RETURN site.name, [node in nodes(path) | node.name] as hierarchy
```

**Find machines with temperature sensors:**
```cypher
MATCH (machine:Asset {type: 'machine'})-[:HAS_SENSOR]->(sensor:Sensor {type: 'temperature'})
RETURN machine.name, sensor.name, sensor.unit
```

### Time-Series Queries

**Recent sensor readings:**
```sql
SELECT * FROM sensor_data 
WHERE time > now() - 1h 
AND site = 'PlantA'
```

**Aggregated data by machine:**
```sql
SELECT mean(value) as avg_value
FROM sensor_data 
WHERE time > now() - 24h 
GROUP BY machine, sensor_type
```

### API Usage

**Get asset hierarchy:**
```bash
curl http://localhost:8000/api/v1/assets/hierarchy/PlantA
```

**Query sensor data:**
```bash
curl "http://localhost:8000/api/v1/sensors/TempSensor1/data?hours=24"
```

**Generate MQTT topics:**
```bash
curl http://localhost:8000/api/v1/topics/generate
```

## 🔌 Integration

### MQTT Topic Structure

The system generates hierarchical MQTT topics based on the asset structure stored in the graph database:

```
{site}/{area}/{line}/{machine}/{sensor_type}/{metric_type}
```

**Examples:**
- `PlantA/Area1/Line1/Machine1/temperature/value`
- `PlantA/Area1/Line1/Machine1/temperature/quality`
- `PlantA/Area1/Line1/Machine1/pressure/value`
- `PlantA/Area2/Line2/Machine2/vibration/alarm`

### Topic Generation Rules

1. **Hierarchical Path**: Generated from graph traversal (Site → Area → Line → Machine)
2. **Sensor Type**: Based on the sensor's `type` property
3. **Metric Type**: Common suffixes include:
   - `value` - Primary measurement
   - `quality` - Data quality indicator
   - `status` - Equipment status
   - `alarm` - Alarm conditions
   - `setpoint` - Control setpoints

### Data Publishers

**Python Example:**
```python
import paho.mqtt.client as mqtt
import json
from datetime import datetime

def publish_sensor_data(client, site, area, line, machine, sensor_type, value):
    topic = f"{site}/{area}/{line}/{machine}/{sensor_type}/value"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "value": value,
        "quality": "good",
        "source": "sensor_gateway"
    }
    client.publish(topic, json.dumps(payload))

# Usage
client = mqtt.Client()
client.connect("localhost", 1883, 60)
publish_sensor_data(client, "PlantA", "Area1", "Line1", "Machine1", "temperature", 75.2)
```

**Node.js Example:**
```javascript
const mqtt = require('mqtt');
const client = mqtt.connect('mqtt://localhost:1883');

function publishSensorData(site, area, line, machine, sensorType, value) {
    const topic = `${site}/${area}/${line}/${machine}/${sensorType}/value`;
    const payload = {
        timestamp: new Date().toISOString(),
        value: value,
        quality: 'good',
        source: 'plc_gateway'
    };
    client.publish(topic, JSON.stringify(payload));
}

// Usage
publishSensorData('PlantA', 'Area1', 'Line1', 'Machine1', 'pressure', 2.5);
```

## 🧪 Testing

### Unit Tests

Run the test suite:
```bash
docker-compose exec api pytest tests/
```

### Integration Tests

Test the complete data flow:
```bash
./scripts/test-integration.sh
```

### Load Testing

Simulate high-volume data ingestion:
```bash
./scripts/load-test.sh --sensors 1000 --duration 60s
```

## 📊 Monitoring

### Health Checks

The system provides health check endpoints:

```bash
# API Health
curl http://localhost:8000/health

# Neo4j Health
curl http://localhost:7474/db/neo4j/tx/commit

# InfluxDB Health
curl http://localhost:8086/health
```

### Metrics

Key metrics are exposed via Prometheus endpoints:

- **Message Throughput**: MQTT messages per second
- **Query Performance**: Graph and time-series query latency
- **Data Quality**: Sensor data quality indicators
- **System Health**: Service availability and resource usage

## 🚀 Deployment

### Production Considerations

1. **Security**:
   - Enable authentication for all services
   - Use TLS/SSL for all communications
   - Configure firewall rules
   - Implement API rate limiting

2. **High Availability**:
   - Neo4j clustering for graph database
   - InfluxDB clustering for time-series data
   - MQTT broker clustering with load balancing
   - Container orchestration with Kubernetes

3. **Scalability**:
   - Horizontal scaling of API services
   - Sharding strategies for large datasets
   - Caching layer for frequently accessed data
   - Message queue for high-volume ingestion

### Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.prod.yml uns-stack
```

### Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f k8s/

# Check deployment
kubectl get pods -n uns-namespace
```

## 🔧 Development

### Adding New Asset Types

1. **Update Graph Schema**:
   ```cypher
   CREATE (new_asset:Asset {
       name: 'NewAssetType',
       type: 'custom_type',
       description: 'Custom asset type'
   })
   ```

2. **Update API Models**:
   ```python
   # In models.py
   class CustomAsset(BaseModel):
       name: str
       type: Literal['custom_type']
       properties: Dict[str, Any]
   ```

3. **Add Topic Generation Rules**:
   ```python
   # In topic_generator.py
   def generate_custom_topic(asset_node):
       # Custom topic generation logic
       pass
   ```

### Extending with Ontologies

1. **Import OWL Ontology**:
   ```cypher
   CALL n10s.onto.import.fetch(
       'https://example.com/ontology.owl',
       'RDF/XML'
   )
   ```

2. **Map to Graph Schema**:
   ```cypher
   CALL n10s.mapping.add(
       'https://example.com/ontology#Equipment',
       'Asset'
   )
   ```

## 📚 Documentation

### API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Graph Schema Documentation

Generate schema documentation:
```bash
./scripts/generate-schema-docs.sh
```

## 🆘 Support

### Common Issues

1. **Services not starting**: Check Docker logs and port availability
2. **Connection refused**: Verify service health and network configuration
3. **Performance issues**: Check resource allocation and query optimization



