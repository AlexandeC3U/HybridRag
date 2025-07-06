"""
Ontology Manager for Hybrid RAG System
Handles rich ontological relationships and concept hierarchies
"""

import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class OntologyConcept:
    """Represents an ontological concept"""
    id: str
    name: str
    description: str
    parent_concepts: List[str]
    child_concepts: List[str]
    related_concepts: List[str]
    entity_instances: List[str]
    confidence: float

@dataclass
class OntologyRelationship:
    """Represents a relationship between concepts"""
    source_concept: str
    target_concept: str
    relationship_type: str
    confidence: float
    evidence: List[str]

class OntologyManager:
    """
    Manages ontological relationships and concept hierarchies
    """
    
    def __init__(self, graph_search, settings):
        self.graph_search = graph_search
        self.settings = settings
        
        # Ontology concepts cache
        self.concepts: Dict[str, OntologyConcept] = {}
        self.relationships: List[OntologyRelationship] = []
        
        # Performance cache
        self.cache = None
        
        # Relationship types
        self.relationship_types = {
            "IS_A": "Taxonomic relationship",
            "PART_OF": "Meronymic relationship", 
            "RELATED_TO": "Associative relationship",
            "INSTANCE_OF": "Instantiation relationship",
            "SIMILAR_TO": "Similarity relationship",
            "OPPOSITE_OF": "Antonymic relationship",
            "CAUSES": "Causal relationship",
            "PRECEDES": "Temporal relationship"
        }
        
    async def initialize(self):
        """Initialize ontology from existing graph data"""
        try:
            # Initialize cache
            from src.ontology_cache import OntologyCache
            self.cache = OntologyCache(max_size=1000, ttl_seconds=3600)
            
            # Load existing concepts from graph
            await self._load_existing_concepts()
            
            # Build concept hierarchies
            await self._build_concept_hierarchies()
            
            logger.info(f"Ontology manager initialized with {len(self.concepts)} concepts")
            
        except Exception as e:
            logger.error(f"Failed to initialize ontology manager: {e}")
            raise
    
    async def _load_existing_concepts(self):
        """Load existing concepts from the graph database"""
        try:
            # Query for existing entities and their relationships
            query = """
            MATCH (e:Entity)
            OPTIONAL MATCH (e)-[r:CO_OCCURS_WITH]-(other:Entity)
            RETURN e.name as name, e.type as type, e.description as description,
                   collect(DISTINCT other.name) as related_entities,
                   count(r) as relationship_count
            """
            
            results = await self.graph_search._execute_query(query)
            
            for result in results:
                concept_id = f"concept_{result['name'].lower().replace(' ', '_')}"
                
                concept = OntologyConcept(
                    id=concept_id,
                    name=result['name'],
                    description=result.get('description', ''),
                    parent_concepts=[],
                    child_concepts=[],
                    related_concepts=result.get('related_entities', []),
                    entity_instances=[result['name']],
                    confidence=min(result.get('relationship_count', 0) / 10.0, 1.0)
                )
                
                self.concepts[concept_id] = concept
                
        except Exception as e:
            logger.error(f"Failed to load existing concepts: {e}")
    
    async def _build_concept_hierarchies(self):
        """Build hierarchical relationships between concepts"""
        try:
            # Use NLP to identify hierarchical relationships
            for concept_id, concept in self.concepts.items():
                # Find potential parent concepts
                potential_parents = await self._find_parent_concepts(concept)
                concept.parent_concepts = potential_parents
                
                # Find potential child concepts
                potential_children = await self._find_child_concepts(concept)
                concept.child_concepts = potential_children
                
        except Exception as e:
            logger.error(f"Failed to build concept hierarchies: {e}")
    
    async def _find_parent_concepts(self, concept: OntologyConcept) -> List[str]:
        """Find potential parent concepts using semantic similarity"""
        parents = []
        
        for other_id, other_concept in self.concepts.items():
            if other_id == concept.id:
                continue
                
            # Check if this concept is more general than the other
            if await self._is_more_general(other_concept, concept):
                parents.append(other_id)
        
        return parents
    
    async def _find_child_concepts(self, concept: OntologyConcept) -> List[str]:
        """Find potential child concepts"""
        children = []
        
        for other_id, other_concept in self.concepts.items():
            if other_id == concept.id:
                continue
                
            # Check if this concept is more specific than the other
            if await self._is_more_specific(concept, other_concept):
                children.append(other_id)
        
        return children
    
    async def _is_more_general(self, concept1: OntologyConcept, concept2: OntologyConcept) -> bool:
        """Check if concept1 is more general than concept2"""
        # Simple heuristic: longer names tend to be more specific
        if len(concept1.name.split()) < len(concept2.name.split()):
            return True
        
        # Check if concept2 is an instance of concept1
        if concept2.name.lower() in concept1.name.lower():
            return True
            
        return False
    
    async def _is_more_specific(self, concept1: OntologyConcept, concept2: OntologyConcept) -> bool:
        """Check if concept1 is more specific than concept2"""
        return await self._is_more_general(concept2, concept1)
    
    async def add_concept(self, name: str, description: str = "", 
                         parent_concepts: List[str] = None) -> str:
        """Add a new concept to the ontology"""
        try:
            concept_id = f"concept_{name.lower().replace(' ', '_')}"
            
            if concept_id in self.concepts:
                return concept_id
            
            concept = OntologyConcept(
                id=concept_id,
                name=name,
                description=description,
                parent_concepts=parent_concepts or [],
                child_concepts=[],
                related_concepts=[],
                entity_instances=[name],
                confidence=0.5
            )
            
            self.concepts[concept_id] = concept
            
            # Add to graph database
            await self._add_concept_to_graph(concept)
            
            logger.info(f"Added concept: {name}")
            return concept_id
            
        except Exception as e:
            logger.error(f"Failed to add concept {name}: {e}")
            raise
    
    async def _add_concept_to_graph(self, concept: OntologyConcept):
        """Add concept to the graph database"""
        try:
            query = """
            MERGE (c:Concept {id: $concept_id, name: $name, description: $description})
            """
            
            await self.graph_search._execute_write_query(query, {
                "concept_id": concept.id,
                "name": concept.name,
                "description": concept.description
            })
            
            # Add relationships to parent concepts
            for parent_id in concept.parent_concepts:
                if parent_id in self.concepts:
                    parent_query = """
                    MATCH (c:Concept {id: $concept_id})
                    MATCH (p:Concept {id: $parent_id})
                    MERGE (c)-[:IS_A]->(p)
                    """
                    
                    await self.graph_search._execute_write_query(parent_query, {
                        "concept_id": concept.id,
                        "parent_id": parent_id
                    })
                    
        except Exception as e:
            logger.error(f"Failed to add concept to graph: {e}")
    
    async def find_related_concepts(self, concept_name: str, 
                                  max_depth: int = 2) -> List[Dict[str, Any]]:
        """Find concepts related to the given concept"""
        try:
            # Check cache first
            if self.cache:
                cached_relationships = await self.cache.get_relationships(concept_name)
                if cached_relationships:
                    return cached_relationships
            
            related = []
            
            # Find the concept
            concept_id = f"concept_{concept_name.lower().replace(' ', '_')}"
            if concept_id not in self.concepts:
                return related
            
            concept = self.concepts[concept_id]
            
            # Get direct relationships
            direct_related = concept.related_concepts + concept.parent_concepts + concept.child_concepts
            
            # Get hierarchical relationships
            hierarchical_related = await self._get_hierarchical_relationships(concept_id, max_depth)
            
            # Combine and deduplicate
            all_related = list(set(direct_related + hierarchical_related))
            
            for related_id in all_related:
                if related_id in self.concepts:
                    related_concept = self.concepts[related_id]
                    related.append({
                        "id": related_id,
                        "name": related_concept.name,
                        "description": related_concept.description,
                        "confidence": related_concept.confidence,
                        "relationship_type": "related"
                    })
            
            # Cache the results
            if self.cache and related:
                await self.cache.set_relationships(concept_name, related)
            
            return related
            
        except Exception as e:
            logger.error(f"Failed to find related concepts: {e}")
            return []
    
    async def _get_hierarchical_relationships(self, concept_id: str, 
                                            max_depth: int) -> List[str]:
        """Get hierarchical relationships up to max_depth"""
        try:
            query = """
            MATCH (c:Concept {id: $concept_id})
            CALL apoc.path.expand(c, "IS_A", null, 1, $max_depth)
            YIELD path
            RETURN [n in nodes(path) | n.id] as concept_path
            """
            
            results = await self.graph_search._execute_query(query, {
                "concept_id": concept_id,
                "max_depth": max_depth
            })
            
            related = []
            for result in results:
                related.extend(result.get("concept_path", []))
            
            return list(set(related))
            
        except Exception as e:
            logger.error(f"Failed to get hierarchical relationships: {e}")
            return []
    
    async def enhance_search_context(self, query: str, 
                                   vector_results: List[Any],
                                   graph_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhance search context using ontological knowledge"""
        try:
            enhanced_context = {
                "original_results": {
                    "vector": vector_results,
                    "graph": graph_results
                },
                "ontological_enhancements": [],
                "concept_links": [],
                "hierarchical_context": []
            }
            
            # Extract concepts from query and results
            query_concepts = await self._extract_concepts_from_text(query)
            result_concepts = await self._extract_concepts_from_results(vector_results, graph_results)
            
            # Find ontological relationships
            for concept in query_concepts + result_concepts:
                related = await self.find_related_concepts(concept)
                if related:
                    enhanced_context["ontological_enhancements"].extend(related)
            
            # Build hierarchical context
            enhanced_context["hierarchical_context"] = await self._build_hierarchical_context(
                query_concepts, result_concepts
            )
            
            return enhanced_context
            
        except Exception as e:
            logger.error(f"Failed to enhance search context: {e}")
            return {"original_results": {"vector": vector_results, "graph": graph_results}}
    
    async def _extract_concepts_from_text(self, text: str) -> List[str]:
        """Extract concept names from text"""
        concepts = []
        
        # Simple extraction - in production, use more sophisticated NLP
        words = text.split()
        for word in words:
            if word.lower() in [c.name.lower() for c in self.concepts.values()]:
                concepts.append(word)
        
        return concepts
    
    async def _extract_concepts_from_results(self, vector_results: List[Any],
                                           graph_results: List[Dict[str, Any]]) -> List[str]:
        """Extract concepts from search results"""
        concepts = []
        
        # Extract from vector results
        for result in vector_results:
            content = result.payload.get("content", "")
            concepts.extend(await self._extract_concepts_from_text(content))
        
        # Extract from graph results
        for result in graph_results:
            content = result.get("content", "")
            concepts.extend(await self._extract_concepts_from_text(content))
        
        return list(set(concepts))
    
    async def _build_hierarchical_context(self, query_concepts: List[str],
                                        result_concepts: List[str]) -> List[Dict[str, Any]]:
        """Build hierarchical context for the concepts"""
        hierarchical_context = []
        
        all_concepts = list(set(query_concepts + result_concepts))
        
        for concept in all_concepts:
            concept_id = f"concept_{concept.lower().replace(' ', '_')}"
            if concept_id in self.concepts:
                concept_obj = self.concepts[concept_id]
                
                # Get parent concepts
                parents = []
                for parent_id in concept_obj.parent_concepts:
                    if parent_id in self.concepts:
                        parents.append(self.concepts[parent_id].name)
                
                # Get child concepts
                children = []
                for child_id in concept_obj.child_concepts:
                    if child_id in self.concepts:
                        children.append(self.concepts[child_id].name)
                
                hierarchical_context.append({
                    "concept": concept,
                    "parents": parents,
                    "children": children,
                    "description": concept_obj.description
                })
        
        return hierarchical_context
    
    async def close(self):
        """Clean up resources"""
        try:
            # Clear in-memory caches
            self.concepts.clear()
            self.relationships.clear()
            
            # Close cache
            if self.cache:
                await self.cache.close()
            
            logger.info("Ontology manager closed")
        except Exception as e:
            logger.error(f"Error closing ontology manager: {e}") 