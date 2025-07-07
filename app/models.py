from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal, Union
from datetime import datetime
from enum import Enum

class AssetType(str, Enum):
    SITE = "site"
    AREA = "area"
    LINE = "line"
    MACHINE = "machine"
    EQUIPMENT = "equipment"
    COMPONENT = "component"

class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VIBRATION = "vibration"
    FLOW = "flow"
    LEVEL = "level"
    SPEED = "speed"
    CURRENT = "current"
    VOLTAGE = "voltage"
    POWER = "power"
    HUMIDITY = "humidity"
    pH = "ph"
    CONDUCTIVITY = "conductivity"
    POSITION = "position"
    FORCE = "force"
    TORQUE = "torque"

class DataQuality(str, Enum):
    GOOD = "good"
    BAD = "bad"
    UNCERTAIN = "uncertain"
    SUBSTITUTED = "substituted"

class AssetStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    FAULT = "fault"

# Base Models
class BaseAsset(BaseModel):
    name: str = Field(..., description="Asset name")
    description: Optional[str] = Field(None, description="Asset description")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom properties")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class BaseSensor(BaseModel):
    name: str = Field(..., description="Sensor name")
    type: SensorType = Field(..., description="Sensor type")
    unit: str = Field(..., description="Measurement unit")
    description: Optional[str] = Field(None, description="Sensor description")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom properties")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

# Asset Models
class AssetCreate(BaseAsset):
    type: AssetType = Field(..., description="Asset type")
    parent_id: Optional[str] = Field(None, description="Parent asset ID")
    status: AssetStatus = Field(AssetStatus.ACTIVE, description="Asset status")
    tags: List[str] = Field(default_factory=list, description="Asset tags")

class Asset(BaseAsset):
    id: str = Field(..., description="Asset ID")
    type: AssetType = Field(..., description="Asset type")
    parent_id: Optional[str] = Field(None, description="Parent asset ID")
    status: AssetStatus = Field(..., description="Asset status")
    tags: List[str] = Field(default_factory=list, description="Asset tags")
    children: List['Asset'] = Field(default_factory=list, description="Child assets")
    sensors: List['Sensor'] = Field(default_factory=list, description="Attached sensors")

class AssetHierarchy(BaseModel):
    site: Asset = Field(..., description="Site asset")
    total_assets: int = Field(..., description="Total number of assets")
    total_sensors: int = Field(..., description="Total number of sensors")
    hierarchy_depth: int = Field(..., description="Maximum hierarchy depth")

# Sensor Models
class SensorCreate(BaseSensor):
    asset_id: str = Field(..., description="Asset ID this sensor belongs to")
    min_value: Optional[float] = Field(None, description="Minimum expected value")
    max_value: Optional[float] = Field(None, description="Maximum expected value")
    sampling_rate: Optional[int] = Field(None, description="Sampling rate in seconds")
    alarm_high: Optional[float] = Field(None, description="High alarm threshold")
    alarm_low: Optional[float] = Field(None, description="Low alarm threshold")

class Sensor(BaseSensor):
    id: str = Field(..., description="Sensor ID")
    asset_id: str = Field(..., description="Asset ID this sensor belongs to")
    min_value: Optional[float] = Field(None, description="Minimum expected value")
    max_value: Optional[float] = Field(None, description="Maximum expected value")
    sampling_rate: Optional[int] = Field(None, description="Sampling rate in seconds")
    alarm_high: Optional[float] = Field(None, description="High alarm threshold")
    alarm_low: Optional[float] = Field(None, description="Low alarm threshold")
    last_reading: Optional['SensorReading'] = Field(None, description="Last sensor reading")

# Sensor Data Models
class SensorReading(BaseModel):
    value: float = Field(..., description="Sensor value")
    quality: DataQuality = Field(DataQuality.GOOD, description="Data quality")
    timestamp: datetime = Field(default_factory=datetime.now, description="Reading timestamp")
    status: Optional[str] = Field(None, description="Sensor status")
    alarm_state: Optional[str] = Field(None, description="Alarm state")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")

    @validator('timestamp', pre=True)
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

class SensorData(BaseModel):
    sensor_id: str = Field(..., description="Sensor ID")
    readings: List[SensorReading] = Field(..., description="List of sensor readings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")

# MQTT Topic Models
class TopicStructure(BaseModel):
    sensor_id: str = Field(..., description="Sensor ID")
    topic: str = Field(..., description="Generated MQTT topic")
    hierarchy: List[str] = Field(..., description="Asset hierarchy path")
    sensor_type: str = Field(..., description="Sensor type")
    metric_types: List[str] = Field(default_factory=list, description="Available metric types")

# Health Check Models
class HealthStatus(BaseModel):
    status: Literal["healthy", "unhealthy", "error"] = Field(..., description="Overall health status")
    services: Dict[str, str] = Field(..., description="Individual service health")
    timestamp: datetime = Field(..., description="Health check timestamp")
    error: Optional[str] = Field(None, description="Error message if any")

# Analytics Models
class SensorSummary(BaseModel):
    sensor_id: str = Field(..., description="Sensor ID")
    name: str = Field(..., description="Sensor name")
    type: str = Field(..., description="Sensor type")
    asset_name: str = Field(..., description="Asset name")
    site: str = Field(..., description="Site name")
    last_reading: Optional[datetime] = Field(None, description="Last reading timestamp")
    reading_count: int = Field(0, description="Total number of readings")
    is_active: bool = Field(True, description="Whether sensor is active")

class DataQualityMetrics(BaseModel):
    site: Optional[str] = Field(None, description="Site name")
    total_readings: int = Field(0, description="Total number of readings")
    good_readings: int = Field(0, description="Good quality readings")
    bad_readings: int = Field(0, description="Bad quality readings")
    uncertain_readings: int = Field(0, description="Uncertain quality readings")
    substituted_readings: int = Field(0, description="Substituted readings")
    quality_percentage: float = Field(0.0, description="Percentage of good readings")
    sensors_active: int = Field(0, description="Number of active sensors")
    sensors_inactive: int = Field(0, description="Number of inactive sensors")
    timestamp: datetime = Field(default_factory=datetime.now, description="Metrics timestamp")

# Graph Schema Models
class GraphNode(BaseModel):
    labels: List[str] = Field(..., description="Node labels")
    properties: Dict[str, Any] = Field(..., description="Node properties")
    count: int = Field(0, description="Count of nodes with this label")

class GraphRelationship(BaseModel):
    type: str = Field(..., description="Relationship type")
    properties: Dict[str, Any] = Field(..., description="Relationship properties")
    count: int = Field(0, description="Count of relationships of this type")

class GraphSchema(BaseModel):
    nodes: List[GraphNode] = Field(..., description="Node types in the graph")
    relationships: List[GraphRelationship] = Field(..., description="Relationship types in the graph")
    total_nodes: int = Field(0, description="Total number of nodes")
    total_relationships: int = Field(0, description="Total number of relationships")

# Batch Processing Models
class BatchSensorData(BaseModel):
    readings: List[Dict[str, Any]] = Field(..., description="Batch of sensor readings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Batch metadata")

class BatchResult(BaseModel):
    success_count: int = Field(0, description="Number of successful inserts")
    error_count: int = Field(0, description="Number of failed inserts")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    processing_time: float = Field(0.0, description="Processing time in seconds")

# Configuration Models
class DatabaseConfig(BaseModel):
    neo4j_uri: str = Field(..., description="Neo4j connection URI")
    neo4j_username: str = Field(..., description="Neo4j username")
    neo4j_password: str = Field(..., description="Neo4j password")
    influxdb_url: str = Field(..., description="InfluxDB URL")
    influxdb_token: str = Field(..., description="InfluxDB token")
    influxdb_org: str = Field(..., description="InfluxDB organization")
    influxdb_bucket: str = Field(..., description="InfluxDB bucket")

class MQTTConfig(BaseModel):
    broker_host: str = Field(..., description="MQTT broker host")
    broker_port: int = Field(1883, description="MQTT broker port")
    username: Optional[str] = Field(None, description="MQTT username")
    password: Optional[str] = Field(None, description="MQTT password")
    client_id: str = Field("uns_api_client", description="MQTT client ID")
    qos: int = Field(1, description="Quality of Service level")

# Update forward references
Asset.model_rebuild()
Sensor.model_rebuild()