"""
Cross-Reference Manager for Hybrid RAG System
Links vector and graph results for enhanced context understanding
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio
from collections import defaultdict
import re

logger = logging.getLogger(__name__)

@dataclass
class CrossReference:
    """Represents a cross-reference between vector and graph results"""
    vector_doc_id: str
    graph_entity_id: str
    relationship_type: str
    confidence: float
    evidence: str

@dataclass
class EnhancedResult:
    """Enhanced result with cross-references"""
    original_result: Any
    cross_references: List[CrossReference]
    ontological_links: List[str]
    context_enhancement: str

class CrossReferenceManager:
    """
    Manages cross-references between vector and graph search results
    """
    
    def __init__(self, vector_search, graph_search, ontology_manager, settings):
        self.vector_search = vector_search
        self.graph_search = graph_search
        self.ontology_manager = ontology_manager
        self.settings = settings
        
        # Cross-reference cache
        self.cross_references: Dict[str, List[CrossReference]] = defaultdict(list)
        
        # Entity extraction patterns
        self.entity_patterns = [
            r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Person names
            r'\b[A-Z][a-z]+ (?:Inc|Corp|Ltd|LLC|Company)\b',  # Organizations
            r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b',  # Proper nouns
            r'\b(?:machine learning|artificial intelligence|deep learning|neural network)\b',  # Tech terms
        ]
        
    async def initialize(self):
        """Initialize the cross-reference manager"""
        try:
            # Build initial cross-references from existing data
            await self._build_initial_cross_references()
            
            logger.info("Cross-reference manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize cross-reference manager: {e}")
            raise
    
    async def _build_initial_cross_references(self):
        """Build initial cross-references from existing data"""
        try:
            # Get all vector documents
            vector_docs = await self._get_all_vector_documents()
            
            # Get all graph entities
            graph_entities = await self._get_all_graph_entities()
            
            # Build cross-references
            for vector_doc in vector_docs:
                doc_content = vector_doc.payload.get("content", "")
                doc_entities = await self._extract_entities_from_text(doc_content)
                
                for entity in doc_entities:
                    # Find matching graph entities
                    matching_entities = await self._find_matching_graph_entities(entity, graph_entities)
                    
                    for graph_entity in matching_entities:
                        cross_ref = CrossReference(
                            vector_doc_id=vector_doc.id,
                            graph_entity_id=graph_entity["id"],
                            relationship_type="MENTIONS",
                            confidence=0.8,
                            evidence=f"Entity '{entity}' found in document content"
                        )
                        
                        self.cross_references[vector_doc.id].append(cross_ref)
                        
        except Exception as e:
            logger.error(f"Failed to build initial cross-references: {e}")
    
    async def _get_all_vector_documents(self) -> List[Any]:
        """Get all documents from vector database"""
        try:
            return await self.vector_search.get_all_documents()
        except Exception as e:
            logger.error(f"Failed to get vector documents: {e}")
            return []
    
    async def _get_all_graph_entities(self) -> List[Dict[str, Any]]:
        """Get all entities from graph database"""
        try:
            return await self.graph_search.get_all_entities()
        except Exception as e:
            logger.error(f"Failed to get graph entities: {e}")
            return []
    
    async def _extract_entities_from_text(self, text: str) -> List[str]:
        """Extract entities from text using patterns"""
        entities = []
        
        for pattern in self.entity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities.extend(matches)
        
        return list(set(entities))
    
    async def _find_matching_graph_entities(self, entity_name: str, 
                                          graph_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find graph entities that match the given entity name"""
        matches = []
        
        entity_lower = entity_name.lower()
        
        for entity in graph_entities:
            graph_entity_name = entity.get("name", "").lower()
            
            # Exact match
            if entity_lower == graph_entity_name:
                matches.append(entity)
            # Partial match
            elif entity_lower in graph_entity_name or graph_entity_name in entity_lower:
                matches.append(entity)
            # Synonym match (could be enhanced with synonym database)
            elif await self._are_synonyms(entity_lower, graph_entity_name):
                matches.append(entity)
        
        return matches
    
    async def _are_synonyms(self, entity1: str, entity2: str) -> bool:
        """Check if two entities are synonyms"""
        # Simple synonym mapping - in production, use a proper synonym database
        synonym_map = {
            "ml": "machine learning",
            "ai": "artificial intelligence",
            "dl": "deep learning",
            "nn": "neural network"
        }
        
        entity1_normalized = synonym_map.get(entity1, entity1)
        entity2_normalized = synonym_map.get(entity2, entity2)
        
        return entity1_normalized == entity2_normalized
    
    async def enhance_search_results(self, query: str, 
                                   vector_results: List[Any],
                                   graph_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhance search results with cross-references"""
        try:
            enhanced_results = {
                "vector_results": [],
                "graph_results": [],
                "cross_references": [],
                "enhanced_context": "",
                "ontological_enhancements": []
            }
            
            # Process vector results
            for result in vector_results:
                enhanced_vector = await self._enhance_vector_result(result, graph_results)
                enhanced_results["vector_results"].append(enhanced_vector)
            
            # Process graph results
            for result in graph_results:
                enhanced_graph = await self._enhance_graph_result(result, vector_results)
                enhanced_results["graph_results"].append(enhanced_graph)
            
            # Build cross-references
            cross_refs = await self._build_cross_references(vector_results, graph_results)
            enhanced_results["cross_references"] = cross_refs
            
            # Build enhanced context
            enhanced_context = await self._build_enhanced_context(
                enhanced_results["vector_results"],
                enhanced_results["graph_results"],
                cross_refs
            )
            enhanced_results["enhanced_context"] = enhanced_context
            
            # Add ontological enhancements
            if self.ontology_manager:
                ontological_enhancements = await self.ontology_manager.enhance_search_context(
                    query, vector_results, graph_results
                )
                enhanced_results["ontological_enhancements"] = ontological_enhancements
            
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Failed to enhance search results: {e}")
            return {
                "vector_results": vector_results,
                "graph_results": graph_results,
                "cross_references": [],
                "enhanced_context": "",
                "ontological_enhancements": []
            }
    
    async def _enhance_vector_result(self, vector_result: Any, 
                                   graph_results: List[Dict[str, Any]]) -> EnhancedResult:
        """Enhance a vector result with cross-references"""
        try:
            content = vector_result.payload.get("content", "")
            entities = await self._extract_entities_from_text(content)
            
            cross_refs = []
            ontological_links = []
            
            # Find cross-references with graph entities
            for entity in entities:
                for graph_result in graph_results:
                    graph_entity_name = graph_result.get("entity_name", "")
                    
                    if entity.lower() in graph_entity_name.lower() or graph_entity_name.lower() in entity.lower():
                        cross_ref = CrossReference(
                            vector_doc_id=vector_result.id,
                            graph_entity_id=graph_result.get("entity_id", ""),
                            relationship_type="MENTIONS",
                            confidence=0.8,
                            evidence=f"Entity '{entity}' found in vector document"
                        )
                        cross_refs.append(cross_ref)
                        ontological_links.append(entity)
            
            # Build context enhancement
            context_enhancement = await self._build_context_enhancement(content, cross_refs)
            
            return EnhancedResult(
                original_result=vector_result,
                cross_references=cross_refs,
                ontological_links=ontological_links,
                context_enhancement=context_enhancement
            )
            
        except Exception as e:
            logger.error(f"Failed to enhance vector result: {e}")
            return EnhancedResult(
                original_result=vector_result,
                cross_references=[],
                ontological_links=[],
                context_enhancement=""
            )
    
    async def _enhance_graph_result(self, graph_result: Dict[str, Any], 
                                  vector_results: List[Any]) -> EnhancedResult:
        """Enhance a graph result with cross-references"""
        try:
            entity_name = graph_result.get("entity_name", "")
            content = graph_result.get("content", "")
            
            cross_refs = []
            ontological_links = []
            
            # Find cross-references with vector documents
            for vector_result in vector_results:
                vector_content = vector_result.payload.get("content", "")
                
                if entity_name.lower() in vector_content.lower():
                    cross_ref = CrossReference(
                        vector_doc_id=vector_result.id,
                        graph_entity_id=graph_result.get("entity_id", ""),
                        relationship_type="MENTIONS",
                        confidence=0.8,
                        evidence=f"Entity '{entity_name}' found in vector document"
                    )
                    cross_refs.append(cross_ref)
                    ontological_links.append(entity_name)
            
            # Build context enhancement
            context_enhancement = await self._build_context_enhancement(content, cross_refs)
            
            return EnhancedResult(
                original_result=graph_result,
                cross_references=cross_refs,
                ontological_links=ontological_links,
                context_enhancement=context_enhancement
            )
            
        except Exception as e:
            logger.error(f"Failed to enhance graph result: {e}")
            return EnhancedResult(
                original_result=graph_result,
                cross_references=[],
                ontological_links=[],
                context_enhancement=""
            )
    
    async def _build_cross_references(self, vector_results: List[Any],
                                    graph_results: List[Dict[str, Any]]) -> List[CrossReference]:
        """Build cross-references between vector and graph results"""
        cross_refs = []
        
        for vector_result in vector_results:
            content = vector_result.payload.get("content", "")
            entities = await self._extract_entities_from_text(content)
            
            for entity in entities:
                for graph_result in graph_results:
                    graph_entity_name = graph_result.get("entity_name", "")
                    
                    if entity.lower() in graph_entity_name.lower() or graph_entity_name.lower() in entity.lower():
                        cross_ref = CrossReference(
                            vector_doc_id=vector_result.id,
                            graph_entity_id=graph_result.get("entity_id", ""),
                            relationship_type="MENTIONS",
                            confidence=0.8,
                            evidence=f"Entity '{entity}' links vector and graph results"
                        )
                        cross_refs.append(cross_ref)
        
        return cross_refs
    
    async def _build_context_enhancement(self, content: str, 
                                       cross_refs: List[CrossReference]) -> str:
        """Build enhanced context from cross-references"""
        if not cross_refs:
            return content
        
        enhancement_parts = [content]
        
        for cross_ref in cross_refs:
            enhancement_parts.append(f"Related entity: {cross_ref.graph_entity_id}")
        
        return "\n\n".join(enhancement_parts)
    
    async def _build_enhanced_context(self, enhanced_vector_results: List[EnhancedResult],
                                    enhanced_graph_results: List[EnhancedResult],
                                    cross_refs: List[CrossReference]) -> str:
        """Build enhanced context from all enhanced results"""
        context_parts = []
        
        # Add vector results
        for result in enhanced_vector_results:
            original_content = result.original_result.payload.get("content", "")
            if result.context_enhancement:
                context_parts.append(result.context_enhancement)
            else:
                context_parts.append(original_content)
        
        # Add graph results
        for result in enhanced_graph_results:
            original_content = result.original_result.get("content", "")
            if result.context_enhancement:
                context_parts.append(result.context_enhancement)
            else:
                context_parts.append(original_content)
        
        # Add cross-reference information
        if cross_refs:
            cross_ref_info = f"Cross-references found: {len(cross_refs)}"
            context_parts.append(cross_ref_info)
        
        return "\n\n---\n\n".join(context_parts)
    
    async def add_cross_reference(self, vector_doc_id: str, graph_entity_id: str,
                                relationship_type: str, confidence: float, evidence: str):
        """Add a new cross-reference"""
        try:
            cross_ref = CrossReference(
                vector_doc_id=vector_doc_id,
                graph_entity_id=graph_entity_id,
                relationship_type=relationship_type,
                confidence=confidence,
                evidence=evidence
            )
            
            self.cross_references[vector_doc_id].append(cross_ref)
            
            logger.info(f"Added cross-reference: {vector_doc_id} -> {graph_entity_id}")
            
        except Exception as e:
            logger.error(f"Failed to add cross-reference: {e}")
    
    async def get_cross_references(self, vector_doc_id: str = None) -> List[CrossReference]:
        """Get cross-references for a specific document or all"""
        if vector_doc_id:
            return self.cross_references.get(vector_doc_id, [])
        else:
            all_refs = []
            for refs in self.cross_references.values():
                all_refs.extend(refs)
            return all_refs
    
    async def close(self):
        """Clean up resources"""
        try:
            self.cross_references.clear()
        except Exception as e:
            logger.error(f"Error closing cross-reference manager: {e}") 