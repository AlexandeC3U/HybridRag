from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re
import spacy
from collections import defaultdict

from src.config import Settings

logger = logging.getLogger(__name__)

class GraphSearch:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.driver = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.nlp = None
        
    async def initialize(self):
        """Initialize the graph search client"""
        try:
            # Initialize Neo4j driver
            self.driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_username, self.settings.neo4j_password)
            )
            
            # Test connection
            await self._test_connection()
            
            # Initialize NLP model for entity extraction
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("SpaCy model not found, using simple entity extraction")
                self.nlp = None
                
            # Create indexes and constraints
            await self._create_schema()
            
            logger.info("Graph search initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize graph search: {e}")
            raise
            
    async def _test_connection(self):
        """Test the Neo4j connection"""
        def test_query(tx):
            return tx.run("RETURN 1").single()
            
        loop = asyncio.get_event_loop()
        with self.driver.session() as session:
            await loop.run_in_executor(self.executor, session.execute_read, test_query)
            
    async def _create_schema(self):
        """Create necessary indexes and constraints"""
        schema_queries = [
            # Constraints
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
            
            # Indexes
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.source)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.domain)",
            "CREATE TEXT INDEX IF NOT EXISTS FOR (d:Document) ON (d.content)",
            "CREATE TEXT INDEX IF NOT EXISTS FOR (e:Entity) ON (e.description)"
        ]
        
        for query in schema_queries:
            await self._execute_query(query)
            
    async def _execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        """Execute a Cypher query"""
        def run_query(tx):
            return tx.run(query, parameters or {})
            
        loop = asyncio.get_event_loop()
        with self.driver.session() as session:
            result = await loop.run_in_executor(
                self.executor, session.execute_read, run_query
            )
            return [record.data() for record in result]
            
    async def _execute_write_query(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        """Execute a write Cypher query"""
        def run_query(tx):
            return tx.run(query, parameters or {})
            
        loop = asyncio.get_event_loop()
        with self.driver.session() as session:
            result = await loop.run_in_executor(
                self.executor, session.execute_write, run_query
            )
            return [record.data() for record in result]
            
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract entities from text using NLP"""
        entities = []
        
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                entities.append({
                    "name": ent.text,
                    "type": ent.label_,
                    "description": spacy.explain(ent.label_) or ""
                })
        else:
            # Simple entity extraction using patterns
            patterns = {
                "PERSON": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
                "ORG": r'\b[A-Z][a-z]+ (?:Inc|Corp|Ltd|LLC|Company)\b',
                "GPE": r'\b[A-Z][a-z]+ (?:City|State|Country)\b'
            }
            
            for entity_type, pattern in patterns.items():
                matches = re.findall(pattern, text)
                for match in matches:
                    entities.append({
                        "name": match,
                        "type": entity_type,
                        "description": f"Extracted {entity_type}"
                    })
                    
        return entities
        
    async def add_document(self, document_id: str, content: str, 
                          metadata: Optional[Dict[str, Any]] = None,
                          entities: Optional[List[str]] = None) -> bool:
        """Add a document to the knowledge graph"""
        try:
            # Extract entities if not provided
            if entities is None:
                extracted_entities = self._extract_entities(content)
                entities = [e["name"] for e in extracted_entities]
            else:
                extracted_entities = [{"name": e, "type": "UNKNOWN", "description": ""} 
                                    for e in entities]
                
            # Create document node
            doc_query = """
            MERGE (d:Document {id: $doc_id})
            SET d.content = $content,
                d.source = $source,
                d.created_at = datetime()
            RETURN d
            """
            
            await self._execute_write_query(doc_query, {
                "doc_id": document_id,
                "content": content,
                "source": metadata.get("source", "unknown") if metadata else "unknown"
            })
            
            # Create entity nodes and relationships
            for entity_data in extracted_entities:
                entity_query = """
                MERGE (e:Entity {name: $name})
                SET e.type = $type,
                    e.description = $description
                WITH e
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:CONTAINS]->(e)
                """
                
                await self._execute_write_query(entity_query, {
                    "name": entity_data["name"],
                    "type": entity_data["type"],
                    "description": entity_data["description"],
                    "doc_id": document_id
                })
                
            # Create relationships between entities (co-occurrence)
            if len(extracted_entities) > 1:
                for i, entity1 in enumerate(extracted_entities):
                    for entity2 in extracted_entities[i+1:]:
                        rel_query = """
                        MATCH (e1:Entity {name: $name1})
                        MATCH (e2:Entity {name: $name2})
                        MERGE (e1)-[r:CO_OCCURS_WITH]-(e2)
                        ON CREATE SET r.weight = 1
                        ON MATCH SET r.weight = r.weight + 1
                        """
                        
                        await self._execute_write_query(rel_query, {
                            "name1": entity1["name"],
                            "name2": entity2["name"]
                        })
                        
            logger.info(f"Added document {document_id} to graph with {len(extracted_entities)} entities")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document to graph: {e}")
            return False
            
    async def ingest_graph_data(self, nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> bool:
        """Ingest graph data (nodes and relationships) into the database"""
        try:
            # Create nodes
            for node in nodes:
                node_id = node.get('id')
                node_type = node.get('type', 'Node')
                
                # Build node properties
                properties = {k: v for k, v in node.items() if k not in ['id', 'type']}
                
                # Create node query
                if node_type == 'Document':
                    query = """
                    MERGE (d:Document {id: $node_id})
                    SET d += $properties
                    """
                elif node_type == 'Entity':
                    query = """
                    MERGE (e:Entity {id: $node_id})
                    SET e += $properties
                    """
                else:
                    query = f"""
                    MERGE (n:{node_type} {{id: $node_id}})
                    SET n += $properties
                    """
                
                await self._execute_write_query(query, {
                    "node_id": node_id,
                    "properties": properties
                })
            
            # Create relationships
            for rel in relationships:
                source = rel.get('source')
                target = rel.get('target')
                relation = rel.get('relation', 'RELATES_TO')
                metadata = rel.get('metadata', {})
                
                # Create relationship query
                query = f"""
                MATCH (source {{id: $source}})
                MATCH (target {{id: $target}})
                MERGE (source)-[r:{relation}]->(target)
                SET r += $metadata
                """
                
                await self._execute_write_query(query, {
                    "source": source,
                    "target": target,
                    "metadata": metadata
                })
            
            logger.info(f"Ingested {len(nodes)} nodes and {len(relationships)} relationships to graph")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest graph data: {e}")
            return False
            
    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search the knowledge graph"""
        try:
            # Extract entities from query
            query_entities = self._extract_entities(query)
            
            results = []
            
            # Strategy 1: Direct entity match
            if query_entities:
                entity_names = [e["name"] for e in query_entities]
                direct_search = await self._search_by_entities(entity_names, limit)
                results.extend(direct_search)
                
            # Strategy 2: Text-based search
            text_results = await self._search_by_text(query, limit)
            results.extend(text_results)
            
            # Strategy 3: Relationship-based search
            if query_entities:
                rel_results = await self._search_by_relationships(query_entities, limit)
                results.extend(rel_results)
                
            # Remove duplicates and sort by score
            unique_results = {}
            for result in results:
                doc_id = result.get("document_id")
                if doc_id not in unique_results or result.get("score", 0) > unique_results[doc_id].get("score", 0):
                    unique_results[doc_id] = result
                    
            sorted_results = sorted(unique_results.values(), 
                                  key=lambda x: x.get("score", 0), reverse=True)
            
            return sorted_results[:limit]
            
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []
            
    async def _search_by_entities(self, entity_names: List[str], limit: int) -> List[Dict[str, Any]]:
        """Search by entity names"""
        query = """
        MATCH (d:Document)-[:CONTAINS]->(e:Entity)
        WHERE e.name IN $entity_names
        WITH d, COUNT(e) as entity_count
        RETURN d.id as document_id, d.content as content, d.source as source,
               entity_count * 1.0 as score,
               {source: d.source, entity_count: entity_count} as metadata
        ORDER BY score DESC
        LIMIT $limit
        """
        
        results = await self._execute_query(query, {
            "entity_names": entity_names,
            "limit": limit
        })
        
        return results
        
    async def _search_by_text(self, query_text: str, limit: int) -> List[Dict[str, Any]]:
        """Search by text content"""
        # Simple text search using CONTAINS
        query = """
        MATCH (d:Document)
        WHERE d.content CONTAINS $query_text
        RETURN d.id as document_id, d.content as content, d.source as source,
               0.5 as score,
               {source: d.source, search_type: "text"} as metadata
        LIMIT $limit
        """
        
        results = await self._execute_query(query, {
            "query_text": query_text,
            "limit": limit
        })
        
        return results
        
    async def _search_by_relationships(self, query_entities: List[Dict[str, str]], limit: int) -> List[Dict[str, Any]]:
        """Search by entity relationships"""
        if len(query_entities) < 2:
            return []
            
        entity_names = [e["name"] for e in query_entities]
        
        query = """
        MATCH (e1:Entity)-[:CO_OCCURS_WITH]-(e2:Entity)
        WHERE e1.name IN $entity_names AND e2.name IN $entity_names
        MATCH (d:Document)-[:CONTAINS]->(e1)
        MATCH (d)-[:CONTAINS]->(e2)
        RETURN d.id as document_id, d.content as content, d.source as source,
               0.8 as score,
               {source: d.source, search_type: "relationship"} as metadata
        LIMIT $limit
        """
        
        results = await self._execute_query(query, {
            "entity_names": entity_names,
            "limit": limit
        })
        
        return results
        
    async def get_entity_relationships(self, entity_name: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Get relationships for an entity"""
        # First check if APOC is available
        apoc_check_query = "CALL apoc.help('path') YIELD name LIMIT 1 RETURN count(*) as apoc_available"
        
        try:
            apoc_result = await self._execute_query(apoc_check_query)
            apoc_available = apoc_result and apoc_result[0]["apoc_available"] > 0
        except Exception as e:
            logger.warning(f"APOC procedures not available: {e}")
            apoc_available = False
        
        if apoc_available:
            # Use APOC for advanced path expansion
            query = """
            MATCH (e:Entity {name: $entity_name})
            CALL apoc.path.expand(e, "CO_OCCURS_WITH", null, 1, $max_depth)
            YIELD path
            RETURN [n in nodes(path) | n.name] as entity_path,
                   [r in relationships(path) | r.weight] as weights
            """
        else:
            # Fallback to basic Cypher without APOC
            query = """
            MATCH (e:Entity {name: $entity_name})
            OPTIONAL MATCH (e)-[r1:CO_OCCURS_WITH]-(e2:Entity)
            OPTIONAL MATCH (e2)-[r2:CO_OCCURS_WITH]-(e3:Entity)
            WHERE e3.name <> $entity_name
            RETURN 
                CASE 
                    WHEN e2 IS NOT NULL THEN [e.name, e2.name]
                    ELSE [e.name]
                END as entity_path,
                CASE 
                    WHEN e2 IS NOT NULL THEN [r1.weight]
                    ELSE []
                END as weights
            LIMIT 10
            """
        
        try:
            results = await self._execute_query(query, {
                "entity_name": entity_name,
                "max_depth": max_depth
            })
            return results
        except Exception as e:
            logger.error(f"Failed to get entity relationships: {e}")
            return []
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get graph database statistics"""
        try:
            stats_query = """
            MATCH (d:Document) WITH COUNT(d) as doc_count
            MATCH (e:Entity) WITH doc_count, COUNT(e) as entity_count
            MATCH ()-[r:CONTAINS]->() WITH doc_count, entity_count, COUNT(r) as contains_count
            MATCH ()-[r:CO_OCCURS_WITH]->() WITH doc_count, entity_count, contains_count, COUNT(r) as cooccur_count
            RETURN doc_count, entity_count, contains_count, cooccur_count
            """
            
            result = await self._execute_query(stats_query)
            
            if result:
                return {
                    "total_documents": result[0]["doc_count"],
                    "total_entities": result[0]["entity_count"],
                    "contains_relationships": result[0]["contains_count"],
                    "cooccurrence_relationships": result[0]["cooccur_count"]
                }
            else:
                return {"total_documents": 0, "total_entities": 0, "contains_relationships": 0, "cooccurrence_relationships": 0}
                
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {}
            
    async def clear_all(self) -> bool:
        """Clear all data from the graph"""
        try:
            clear_query = "MATCH (n) DETACH DELETE n"
            await self._execute_write_query(clear_query)
            
            logger.info("Cleared all data from graph database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear graph database: {e}")
            return False
            
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and its associated entities from the graph"""
        try:
            # Delete document and all its relationships
            delete_query = """
            MATCH (d:Document {id: $doc_id})
            OPTIONAL MATCH (d)-[r]-()
            DELETE r
            DELETE d
            """
            
            await self._execute_write_query(delete_query, {
                "doc_id": document_id
            })
            
            logger.info(f"Deleted document {document_id} from graph")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document from graph: {e}")
            return False
            
    async def get_all_entities(self) -> List[Dict[str, Any]]:
        """Get all entities from the graph database"""
        try:
            query = """
            MATCH (e:Entity)
            RETURN e.name as name, e.type as type, e.description as description,
                   e.id as id, e.confidence as confidence
            """
            
            results = await self._execute_query(query)
            return results
            
        except Exception as e:
            logger.error(f"Failed to get all entities: {e}")
            return []
            
    async def close(self):
        """Close the database connection"""
        try:
            if self.driver:
                self.driver.close()
            if self.executor:
                self.executor.shutdown(wait=True)
                
        except Exception as e:
            logger.error(f"Error closing graph search: {e}")