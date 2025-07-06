"""
Ontology Cache for Hybrid RAG System
Caches ontological relationships and concept hierarchies for improved performance
"""

import logging
from typing import Dict, List, Any, Optional
import asyncio
import time
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class OntologyCache:
    """
    Caches ontological relationships and concept hierarchies
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
        # Cache storage
        self.concept_cache: Dict[str, Dict[str, Any]] = {}
        self.relationship_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.hierarchy_cache: Dict[str, List[str]] = {}
        
        # Cache metadata
        self.access_times: Dict[str, float] = {}
        self.creation_times: Dict[str, float] = {}
        
        # Statistics
        self.hits = 0
        self.misses = 0
        
    async def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get a concept from cache"""
        try:
            if concept_id in self.concept_cache:
                # Check if expired
                if self._is_expired(concept_id):
                    await self._remove_from_cache(concept_id)
                    self.misses += 1
                    return None
                
                # Update access time
                self.access_times[concept_id] = time.time()
                self.hits += 1
                return self.concept_cache[concept_id]
            
            self.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Error getting concept from cache: {e}")
            return None
    
    async def set_concept(self, concept_id: str, concept_data: Dict[str, Any]):
        """Set a concept in cache"""
        try:
            # Check cache size and evict if necessary
            if len(self.concept_cache) >= self.max_size:
                await self._evict_oldest()
            
            self.concept_cache[concept_id] = concept_data
            self.access_times[concept_id] = time.time()
            self.creation_times[concept_id] = time.time()
            
        except Exception as e:
            logger.error(f"Error setting concept in cache: {e}")
    
    async def get_relationships(self, concept_id: str) -> List[Dict[str, Any]]:
        """Get relationships for a concept from cache"""
        try:
            cache_key = f"relationships_{concept_id}"
            
            if cache_key in self.relationship_cache:
                # Check if expired
                if self._is_expired(cache_key):
                    await self._remove_from_cache(cache_key)
                    self.misses += 1
                    return []
                
                # Update access time
                self.access_times[cache_key] = time.time()
                self.hits += 1
                return self.relationship_cache[cache_key]
            
            self.misses += 1
            return []
            
        except Exception as e:
            logger.error(f"Error getting relationships from cache: {e}")
            return []
    
    async def set_relationships(self, concept_id: str, relationships: List[Dict[str, Any]]):
        """Set relationships for a concept in cache"""
        try:
            cache_key = f"relationships_{concept_id}"
            
            # Check cache size and evict if necessary
            if len(self.relationship_cache) >= self.max_size:
                await self._evict_oldest()
            
            self.relationship_cache[cache_key] = relationships
            self.access_times[cache_key] = time.time()
            self.creation_times[cache_key] = time.time()
            
        except Exception as e:
            logger.error(f"Error setting relationships in cache: {e}")
    
    async def get_hierarchy(self, concept_id: str, max_depth: int) -> List[str]:
        """Get hierarchical relationships for a concept from cache"""
        try:
            cache_key = f"hierarchy_{concept_id}_{max_depth}"
            
            if cache_key in self.hierarchy_cache:
                # Check if expired
                if self._is_expired(cache_key):
                    await self._remove_from_cache(cache_key)
                    self.misses += 1
                    return []
                
                # Update access time
                self.access_times[cache_key] = time.time()
                self.hits += 1
                return self.hierarchy_cache[cache_key]
            
            self.misses += 1
            return []
            
        except Exception as e:
            logger.error(f"Error getting hierarchy from cache: {e}")
            return []
    
    async def set_hierarchy(self, concept_id: str, max_depth: int, hierarchy: List[str]):
        """Set hierarchical relationships for a concept in cache"""
        try:
            cache_key = f"hierarchy_{concept_id}_{max_depth}"
            
            # Check cache size and evict if necessary
            if len(self.hierarchy_cache) >= self.max_size:
                await self._evict_oldest()
            
            self.hierarchy_cache[cache_key] = hierarchy
            self.access_times[cache_key] = time.time()
            self.creation_times[cache_key] = time.time()
            
        except Exception as e:
            logger.error(f"Error setting hierarchy in cache: {e}")
    
    def _is_expired(self, key: str) -> bool:
        """Check if a cache entry is expired"""
        if key not in self.creation_times:
            return True
        
        age = time.time() - self.creation_times[key]
        return age > self.ttl_seconds
    
    async def _evict_oldest(self):
        """Evict the oldest cache entries"""
        try:
            # Find the oldest entries
            sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
            
            # Remove oldest 10% of entries
            evict_count = max(1, len(sorted_keys) // 10)
            
            for key, _ in sorted_keys[:evict_count]:
                await self._remove_from_cache(key)
                
        except Exception as e:
            logger.error(f"Error evicting cache entries: {e}")
    
    async def _remove_from_cache(self, key: str):
        """Remove an entry from all cache stores"""
        try:
            # Remove from concept cache
            if key in self.concept_cache:
                del self.concept_cache[key]
            
            # Remove from relationship cache
            if key in self.relationship_cache:
                del self.relationship_cache[key]
            
            # Remove from hierarchy cache
            if key in self.hierarchy_cache:
                del self.hierarchy_cache[key]
            
            # Remove from metadata
            if key in self.access_times:
                del self.access_times[key]
            if key in self.creation_times:
                del self.creation_times[key]
                
        except Exception as e:
            logger.error(f"Error removing from cache: {e}")
    
    async def clear_cache(self):
        """Clear all cache data"""
        try:
            self.concept_cache.clear()
            self.relationship_cache.clear()
            self.hierarchy_cache.clear()
            self.access_times.clear()
            self.creation_times.clear()
            
            logger.info("Cache cleared")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0
            
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "concept_cache_size": len(self.concept_cache),
                "relationship_cache_size": len(self.relationship_cache),
                "hierarchy_cache_size": len(self.hierarchy_cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    async def warm_cache(self, ontology_manager, concepts: List[str]):
        """Warm the cache with frequently accessed concepts"""
        try:
            logger.info(f"Warming cache with {len(concepts)} concepts")
            
            for concept in concepts:
                # Get concept data
                concept_data = await ontology_manager.get_concept_data(concept)
                if concept_data:
                    await self.set_concept(concept, concept_data)
                
                # Get relationships
                relationships = await ontology_manager.get_concept_relationships(concept)
                if relationships:
                    await self.set_relationships(concept, relationships)
                
                # Get hierarchy
                hierarchy = await ontology_manager.get_concept_hierarchy(concept, max_depth=2)
                if hierarchy:
                    await self.set_hierarchy(concept, 2, hierarchy)
            
            logger.info("Cache warming completed")
            
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
    
    async def close(self):
        """Clean up cache resources"""
        try:
            await self.clear_cache()
            logger.info("Ontology cache closed")
        except Exception as e:
            logger.error(f"Error closing ontology cache: {e}") 