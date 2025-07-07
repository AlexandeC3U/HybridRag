from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
from contextlib import asynccontextmanager

from models import (
    AssetHierarchy, SensorData, SensorReading, 
    HealthStatus, TopicStructure, AssetCreate, SensorCreate
)
from database import Neo4jManager, InfluxDBManager
from mqtt_client import MQTTPublisher
from topic_generator import TopicGenerator

# Database managers
neo4j_manager = Neo4jManager()
influxdb_manager = InfluxDBManager()
mqtt_publisher = MQTTPublisher()
topic_generator = TopicGenerator(neo4j_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await neo4j_manager.connect()
    await influxdb_manager.connect()
    await mqtt_publisher.connect()
    print("🚀 UNS Graph PoC API started successfully")
    yield
    # Shutdown
    await neo4j_manager.close()
    await influxdb_manager.close()
    await mqtt_publisher.disconnect()
    print("🛑 UNS Graph PoC API shutdown complete")

app = FastAPI(
    title="UNS Graph PoC API",
    description="Unified Namespace with Graph Database - REST API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint"""
    try:
        neo4j_healthy = await neo4j_manager.health_check()
        influxdb_healthy = await influxdb_manager.health_check()
        mqtt_healthy = await mqtt_publisher.health_check()
        
        overall_healthy = neo4j_healthy and influxdb_healthy and mqtt_healthy
        
        return HealthStatus(
            status="healthy" if overall_healthy else "unhealthy",
            services={
                "neo4j": "healthy" if neo4j_healthy else "unhealthy",
                "influxdb": "healthy" if influxdb_healthy else "unhealthy",
                "mqtt": "healthy" if mqtt_healthy else "unhealthy"
            },
            timestamp=datetime.now()
        )
    except Exception as e:
        return HealthStatus(
            status="error",
            services={},
            timestamp=datetime.now(),
            error=str(e)
        )

# Asset Management Endpoints
@app.get("/api/v1/assets/hierarchy/{site_name}", response_model=AssetHierarchy)
async def get_asset_hierarchy(site_name: str):
    """Get complete asset hierarchy for a site"""
    try:
        hierarchy = await neo4j_manager.get_asset_hierarchy(site_name)
        if not hierarchy:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")
        return hierarchy
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve hierarchy: {str(e)}")

@app.post("/api/v1/assets", response_model=Dict[str, str])
async def create_asset(asset: AssetCreate):
    """Create a new asset"""
    try:
        asset_id = await neo4j_manager.create_asset(asset)
        return {"asset_id": asset_id, "message": "Asset created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create asset: {str(e)}")

@app.get("/api/v1/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Get asset details by ID"""
    try:
        asset = await neo4j_manager.get_asset(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")
        return asset
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve asset: {str(e)}")

@app.get("/api/v1/assets/search")
async def search_assets(
    query: str = Query(..., description="Search query"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    site: Optional[str] = Query(None, description="Filter by site")
):
    """Search assets by name or properties"""
    try:
        assets = await neo4j_manager.search_assets(query, asset_type, site)
        return {"assets": assets, "count": len(assets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# Sensor Management Endpoints
@app.post("/api/v1/sensors", response_model=Dict[str, str])
async def create_sensor(sensor: SensorCreate):
    """Create a new sensor"""
    try:
        sensor_id = await neo4j_manager.create_sensor(sensor)
        return {"sensor_id": sensor_id, "message": "Sensor created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create sensor: {str(e)}")

@app.get("/api/v1/sensors/{sensor_id}/data")
async def get_sensor_data(
    sensor_id: str,
    hours: int = Query(24, description="Hours of data to retrieve"),
    limit: int = Query(1000, description="Maximum number of data points")
):
    """Get time-series data for a sensor"""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        data = await influxdb_manager.get_sensor_data(sensor_id, start_time, end_time, limit)
        return {
            "sensor_id": sensor_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "data_points": len(data),
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sensor data: {str(e)}")

@app.post("/api/v1/sensors/{sensor_id}/data")
async def ingest_sensor_data(sensor_id: str, data: SensorReading):
    """Ingest sensor data point"""
    try:
        # Store in InfluxDB
        await influxdb_manager.write_sensor_data(sensor_id, data)
        
        # Publish to MQTT
        topic = await topic_generator.generate_sensor_topic(sensor_id)
        await mqtt_publisher.publish_sensor_data(topic, data)
        
        return {"message": "Data ingested successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest data: {str(e)}")

@app.get("/api/v1/sensors/{sensor_id}/latest")
async def get_latest_sensor_reading(sensor_id: str):
    """Get the latest reading for a sensor"""
    try:
        reading = await influxdb_manager.get_latest_reading(sensor_id)
        if not reading:
            raise HTTPException(status_code=404, detail=f"No data found for sensor '{sensor_id}'")
        return reading
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve latest reading: {str(e)}")

# Topic Management Endpoints
@app.get("/api/v1/topics/generate", response_model=List[TopicStructure])
async def generate_all_topics():
    """Generate MQTT topics for all sensors"""
    try:
        topics = await topic_generator.generate_all_topics()
        return topics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate topics: {str(e)}")

@app.get("/api/v1/topics/sensor/{sensor_id}")
async def get_sensor_topic(sensor_id: str):
    """Get MQTT topic for a specific sensor"""
    try:
        topic = await topic_generator.generate_sensor_topic(sensor_id)
        return {"sensor_id": sensor_id, "topic": topic}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate sensor topic: {str(e)}")

# Analytics Endpoints
@app.get("/api/v1/analytics/sensors/summary")
async def get_sensors_summary(site: Optional[str] = None):
    """Get summary of all sensors"""
    try:
        summary = await neo4j_manager.get_sensors_summary(site)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sensors summary: {str(e)}")

@app.get("/api/v1/analytics/data/quality")
async def get_data_quality_metrics(
    hours: int = Query(24, description="Hours to analyze"),
    site: Optional[str] = Query(None, description="Filter by site")
):
    """Get data quality metrics"""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        metrics = await influxdb_manager.get_data_quality_metrics(start_time, end_time, site)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data quality metrics: {str(e)}")

# Utility Endpoints
@app.get("/api/v1/graph/schema")
async def get_graph_schema():
    """Get Neo4j graph schema information"""
    try:
        schema = await neo4j_manager.get_schema()
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {str(e)}")

@app.post("/api/v1/graph/query")
async def execute_cypher_query(query: Dict[str, str]):
    """Execute a Cypher query (development/debugging only)"""
    try:
        if not query.get("cypher"):
            raise HTTPException(status_code=400, detail="Missing 'cypher' field")
        
        # Security check - only allow read operations
        cypher_query = query["cypher"].strip().upper()
        if not cypher_query.startswith(("MATCH", "RETURN", "WITH", "OPTIONAL")):
            raise HTTPException(status_code=400, detail="Only read queries are allowed")
        
        results = await neo4j_manager.execute_query(query["cypher"])
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )