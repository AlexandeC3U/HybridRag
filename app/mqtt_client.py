import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import logging
from neo4j import AsyncGraphDatabase
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.query_api import QueryApi
from models import (
    Asset, AssetCreate, AssetHierarchy, Sensor, SensorCreate, 
    SensorReading, SensorSummary, DataQualityMetrics, GraphSchema
)

logger = logging.getLogger(__name__)

class Neo4jManager:
    def __init__(self):
        self.driver = None
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        
    async def connect(self):
        """Connect to Neo4j database"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            await self.driver.verify_connectivity()
            logger.info("Connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    async def health_check(self) -> bool:
        """Check Neo4j health"""
        try:
            if not self.driver:
                return False
            async with self.driver.session() as session:
                result = await session.run("RETURN 1")
                await result.consume()
                return True
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False

    async def get_asset_hierarchy(self, site_name: str) -> Optional[AssetHierarchy]:
        """Get complete asset hierarchy for a site"""
        async with self.driver.session() as session:
            # Get site node
            site_query = """
            MATCH (s:Site {name: $site_name})
            RETURN s
            """
            result = await session.run(site_query, site_name=site_name)
            site_record = await result.single()
            
            if not site_record:
                return None
            
            # Get complete hierarchy
            hierarchy_query = """
            MATCH (s:Site {name: $site_name})
            OPTIONAL MATCH path = (s)-[:CONTAINS*]->(child:Asset)
            OPTIONAL MATCH (child)-[:HAS_SENSOR]->(sensor:Sensor)
            RETURN s, collect(DISTINCT child) as assets, collect(DISTINCT sensor) as sensors
            """
            result = await session.run(hierarchy_query, site_name=site_name)
            record = await result.single()
            
            if not record:
                return None
                
            site_node = record["s"]
            assets = record["assets"] or []
            sensors = record["sensors"] or []
            
            # Build hierarchy tree
            site_asset = Asset(
                id=str(site_node.element_id),
                name=site_node["name"],
                type=site_node.get("type", "site"),
                description=site_node.get("description"),
                status=site_node.get("status", "active"),
                properties=dict(site_node)
            )
            
            return AssetHierarchy(
                site=site_asset,
                total_assets=len(assets) + 1,  # +1 for site itself
                total_sensors=len(sensors),
                hierarchy_depth=self._calculate_hierarchy_depth(assets)
            )

    async def create_asset(self, asset: AssetCreate) -> str:
        """Create a new asset"""
        async with self.driver.session() as session:
            now = datetime.now()
            
            create_query = """
            CREATE (a:Asset {
                name: $name,
                type: $type,
                description: $description,
                status: $status,
                properties: $properties,
                tags: $tags,
                created_at: $created_at,
                updated_at: $updated_at
            })
            RETURN elementId(a) as id
            """
            
            result = await session.run(
                create_query,
                name=asset.name,
                type=asset.type.value,
                description=asset.description,
                status=asset.status.value,
                properties=asset.properties,
                tags=asset.tags,
                created_at=now,
                updated_at=now
            )
            
            record = await result.single()
            asset_id = record["id"]
            
            # Create parent relationship if specified
            if asset.parent_id:
                parent_query = """
                MATCH (parent) WHERE elementId(parent) = $parent_id
                MATCH (child) WHERE elementId(child) = $child_id
                CREATE (parent)-[:CONTAINS]->(child)
                """
                await session.run(parent_query, parent_id=asset.parent_id, child_id=asset_id)
            
            return asset_id

    async def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get asset by ID"""
        async with self.driver.session() as session:
            query = """
            MATCH (a) WHERE elementId(a) = $asset_id
            OPTIONAL MATCH (a)-[:CONTAINS]->(child:Asset)
            OPTIONAL MATCH (a)-[:HAS_SENSOR]->(sensor:Sensor)
            RETURN a, collect(DISTINCT child) as children, collect(DISTINCT sensor) as sensors
            """
            result = await session.run(query, asset_id=asset_id)
            record = await result.single()
            
            if not record:
                return None
                
            asset_node = record["a"]
            children = record["children"] or []
            sensors = record["sensors"] or []
            
            return {
                "id": asset_id,
                "name": asset_node["name"],
                "type": asset_node.get("type"),
                "description": asset_node.get("description"),
                "status": asset_node.get("status"),
                "properties": dict(asset_node),
                "children": [dict(child) for child in children],
                "sensors": [dict(sensor) for sensor in sensors]
            }

    async def search_assets(self, query: str, asset_type: Optional[str] = None, site: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search assets by name or properties"""
        async with self.driver.session() as session:
            conditions = ["a.name CONTAINS $query"]
            params = {"query": query}
            
            if asset_type:
                conditions.append("a.type = $asset_type")
                params["asset_type"] = asset_type
                
            if site:
                conditions.append("EXISTS { MATCH (s:Site {name: $site})-[:CONTAINS*]->(a) }")
                params["site"] = site
            
            cypher_query = f"""
            MATCH (a:Asset)
            WHERE {' AND '.join(conditions)}
            RETURN a, elementId(a) as id
            LIMIT 100
            """
            
            result = await session.run(cypher_query, **params)
            assets = []
            
            async for record in result:
                asset_node = record["a"]
                assets.append({
                    "id": record["id"],
                    "name": asset_node["name"],
                    "type": asset_node.get("type"),
                    "description": asset_node.get("description"),
                    "status": asset_node.get("status"),
                    "properties": dict(asset_node)
                })
            
            return assets

    async def create_sensor(self, sensor: SensorCreate) -> str:
        """Create a new sensor"""
        async with self.driver.session() as session:
            now = datetime.now()
            
            create_query = """
            CREATE (s:Sensor {
                name: $name,
                type: $type,
                unit: $unit,
                description: $description,
                min_value: $min_value,
                max_value: $max_value,
                sampling_rate: $sampling_rate,
                alarm_high: $alarm_high,
                alarm_low: $alarm_low,
                properties: $properties,
                created_at: $created_at,
                updated_at: $updated_at
            })
            RETURN elementId(s) as id
            """
            
            result = await session.run(
                create_query,
                name=sensor.name,
                type=sensor.type.value,
                unit=sensor.unit,
                description=sensor.description,
                min_value=sensor.min_value,
                max_value=sensor.max_value,
                sampling_rate=sensor.sampling_rate,
                alarm_high=sensor.alarm_high,
                alarm_low=sensor.alarm_low,
                properties=sensor.properties,
                created_at=now,
                updated_at=now
            )
            
            record = await result.single()
            sensor_id = record["id"]
            
            # Create asset relationship
            asset_query = """
            MATCH (asset) WHERE elementId(asset) = $asset_id
            MATCH (sensor) WHERE elementId(sensor) = $sensor_id
            CREATE (asset)-[:HAS_SENSOR]->(sensor)
            """
            await session.run(asset_query, asset_id=sensor.asset_id, sensor_id=sensor_id)
            
            return sensor_id

    async def get_sensors_summary(self, site: Optional[str] = None) -> List[SensorSummary]:
        """Get summary of all sensors"""
        async with self.driver.session() as session:
            conditions = []
            params = {}
            
            if site:
                conditions.append("EXISTS { MATCH (s:Site {name: $site})-[:CONTAINS*]->(a) }")
                params["site"] = site
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            query = f"""
            MATCH (a:Asset)-[:HAS_SENSOR]->(sensor:Sensor)
            {where_clause}
            OPTIONAL MATCH (s:Site)-[:CONTAINS*]->(a)
            RETURN elementId(sensor) as sensor_id, sensor.name as name, sensor.type as type,
                   a.name as asset_name, s.name as site_name,
                   sensor.created_at as created_at
            """
            
            result = await session.run(query, **params)
            sensors = []
            
            async for record in result:
                sensors.append(SensorSummary(
                    sensor_id=record["sensor_id"],
                    name=record["name"],
                    type=record["type"],
                    asset_name=record["asset_name"],
                    site=record["site_name"] or "Unknown",
                    last_reading=None,  # Will be populated from InfluxDB
                    reading_count=0,    # Will be populated from InfluxDB
                    is_active=True
                ))
            
            return sensors

    async def get_schema(self) -> GraphSchema:
        """Get graph schema information"""
        async with self.driver.session() as session:
            # Get node labels and counts
            nodes_query = """
            CALL db.labels() YIELD label
            CALL {
                WITH label
                CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) as count', {})
                YIELD value
                RETURN value.count as count
            }
            RETURN label, count
            """
            
            # Get relationship types and counts
            rels_query = """
            CALL db.relationshipTypes() YIELD relationshipType
            CALL {
                WITH relationshipType
                CALL apoc.cypher.run('MATCH ()-[r:' + relationshipType + ']->() RETURN count(r) as count', {})
                YIELD value
                RETURN value.count as count
            }
            RETURN relationshipType, count
            """
            
            # Execute queries (simplified without APOC)
            simple_nodes_query = """
            MATCH (n) 
            RETURN DISTINCT labels(n) as labels, count(n) as count
            """
            
            simple_rels_query = """
            MATCH ()-[r]->()
            RETURN DISTINCT type(r) as type, count(r) as count
            """
            
            result = await session.run(simple_nodes_query)
            nodes = []
            total_nodes = 0
            
            async for record in result:
                count = record["count"]
                total_nodes += count
                nodes.append({
                    "labels": record["labels"],
                    "properties": {},
                    "count": count
                })
            
            result = await session.run(simple_rels_query)
            relationships = []
            total_relationships = 0
            
            async for record in result:
                count = record["count"]
                total_relationships += count
                relationships.append({
                    "type": record["type"],
                    "properties": {},
                    "count": count
                })
            
            return GraphSchema(
                nodes=nodes,
                relationships=relationships,
                total_nodes=total_nodes,
                total_relationships=total_relationships
            )

    async def execute_query(self, cypher_query: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query"""
        async with self.driver.session() as session:
            result = await session.run(cypher_query)
            records = []
            
            async for record in result:
                records.append(dict(record))
            
            return records

    def _calculate_hierarchy_depth(self, assets: List[Any]) -> int:
        """Calculate maximum hierarchy depth"""
        # Simplified implementation - in practice, you'd traverse the graph
        return 5  # Typical depth: Site -> Area -> Line -> Machine -> Component


class InfluxDBManager:
    def __init__(self):
        self.client = None
        self.write_api = None
        self.query_api = None
        self.url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.token = os.getenv("INFLUXDB_TOKEN", "")
        self.org = os.getenv("INFLUXDB_ORG", "uns-org")
        self.bucket = os.getenv("INFLUXDB_BUCKET", "uns-bucket")
        
    async def connect(self):
        """Connect to InfluxDB"""
        try:
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()
            logger.info("Connected to InfluxDB")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            raise

    async def close(self):
        """Close InfluxDB connection"""
        if self.client:
            self.client.close()
            logger.info("InfluxDB connection closed")

    async def health_check(self) -> bool:
        """Check InfluxDB health"""
        try:
            if not self.client:
                return False
            health = self.client.health()
            return health.status == "pass"
        except Exception as e:
            logger.error(f"InfluxDB health check failed: {e}")
            return False

    async def write_sensor_data(self, sensor_id: str, reading: SensorReading):
        """Write sensor data to InfluxDB"""
        try:
            # Create data point
            point = {
                "measurement": "sensor_data",
                "tags": {
                    "sensor_id": sensor_id,
                    "quality": reading.quality.value
                },
                "fields": {
                    "value": reading.value,
                    "status": reading.status or "",
                    "alarm_state": reading.alarm_state or ""
                },
                "time": reading.timestamp
            }
            
            # Add custom properties as fields
            for key, value in reading.properties.items():
                if isinstance(value, (int, float, str, bool)):
                    point["fields"][f"prop_{key}"] = value
            
            # Write to InfluxDB
            await asyncio.get_event_loop().run_in_executor(
                None, self.write_api.write, self.bucket, self.org, point
            )
            
        except Exception as e:
            logger.error(f"Failed to write sensor data: {e}")
            raise

    async def get_sensor_data(self, sensor_id: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get sensor data from InfluxDB"""
        try:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
                |> limit(n: {limit})
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.query_api.query, query, org=self.org
            )
            
            data = []
            for table in result:
                for record in table.records:
                    data.append({
                        "timestamp": record.get_time().isoformat(),
                        "value": record.get_value() if record.get_field() == "value" else None,
                        "quality": record.values.get("quality", "good"),
                        "status": record.values.get("status", ""),
                        "alarm_state": record.values.get("alarm_state", "")
                    })
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to get sensor data: {e}")
            raise

    async def get_latest_reading(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        """Get latest reading for a sensor"""
        try:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
                |> last()
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.query_api.query, query, org=self.org
            )
            
            for table in result:
                for record in table.records:
                    return {
                        "timestamp": record.get_time().isoformat(),
                        "value": record.values.get("value"),
                        "quality": record.values.get("quality", "good"),
                        "status": record.values.get("status", ""),
                        "alarm_state": record.values.get("alarm_state", "")
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get latest reading: {e}")
            raise

    async def get_data_quality_metrics(self, start_time: datetime, end_time: datetime, site: Optional[str] = None) -> DataQualityMetrics:
        """Get data quality metrics"""
        try:
            site_filter = f'|> filter(fn: (r) => r["site"] == "{site}")' if site else ""
            
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                {site_filter}
                |> group(columns: ["quality"])
                |> count()
            '''
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.query_api.query, query, org=self.org
            )
            
            quality_counts = {}
            total_readings = 0
            
            for table in result:
                for record in table.records:
                    quality = record.values.get("quality", "unknown")
                    count = record.get_value()
                    quality_counts[quality] = count
                    total_readings += count
            
            good_readings = quality_counts.get("good", 0)
            bad_readings = quality_counts.get("bad", 0)
            uncertain_readings = quality_counts.get("uncertain", 0)
            substituted_readings = quality_counts.get("substituted", 0)
            
            quality_percentage = (good_readings / total_readings * 100) if total_readings > 0 else 0
            
            return DataQualityMetrics(
                site=site,
                total_readings=total_readings,
                good_readings=good_readings,
                bad_readings=bad_readings,
                uncertain_readings=uncertain_readings,
                substituted_readings=substituted_readings,
                quality_percentage=quality_percentage,
                sensors_active=0,  # Would need additional query
                sensors_inactive=0  # Would need additional query
            )
            
        except Exception as e:
            logger.error(f"Failed to get data quality metrics: {e}")
            raise