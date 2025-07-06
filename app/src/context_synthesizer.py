"""
Context Synthesizer for Hybrid RAG System
Combines and synthesizes results from vector and graph searches
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
import asyncio
from dataclasses import dataclass
from collections import Counter
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

@dataclass
class SynthesizedResult:
    content: str
    score: float
    source_type: str
    metadata: Dict[str, Any]
    relevance_score: float

class ContextSynthesizer:
    """
    Synthesizes context from multiple search sources (vector and graph)
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.embedding_model = None
        self.max_context_length = getattr(settings, 'MAX_CONTEXT_LENGTH', 4000)
        self.similarity_threshold = getattr(settings, 'SIMILARITY_THRESHOLD', 0.7)
        self.reranking_enabled = getattr(settings, 'ENABLE_RERANKING', True)
        
    async def initialize(self):
        """Initialize the embedding model for similarity calculations"""
        try:
            model_name = getattr(self.settings, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            self.embedding_model = SentenceTransformer(model_name)
            logger.info(f"Context synthesizer initialized with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize context synthesizer: {e}")
            raise

    async def synthesize(self, query: str, search_results: Dict[str, Any], 
                        ontology_manager=None, cross_reference_manager=None) -> Dict[str, Any]:
        """
        Synthesize context from vector and graph search results with ontology enhancement
        
        Args:
            query: The user's query
            search_results: Dict containing 'vector' and 'graph' results
            ontology_manager: Optional ontology manager for concept enhancement
            cross_reference_manager: Optional cross-reference manager
            
        Returns:
            Dict with synthesized context, sources, and confidence
        """
        try:
            # Extract results from both sources
            vector_results = search_results.get('vector', [])
            graph_results = search_results.get('graph', [])
            
            # Enhanced synthesis with cross-references
            if cross_reference_manager:
                enhanced_results = await cross_reference_manager.enhance_search_results(
                    query, vector_results, graph_results
                )
                vector_results = enhanced_results.get("vector_results", vector_results)
                graph_results = enhanced_results.get("graph_results", graph_results)
            
            # Convert to unified format
            unified_results = []
            unified_results.extend(await self._process_vector_results(vector_results))
            unified_results.extend(await self._process_graph_results(graph_results))
            
            if not unified_results:
                return {
                    'context': '',
                    'sources': [],
                    'confidence': 0.0,
                    'synthesis_info': {'method': 'empty_results'}
                }
            
            # Remove duplicates and near-duplicates
            deduplicated_results = await self._deduplicate_results(unified_results)
            
            # Rerank results based on query relevance
            if self.reranking_enabled:
                reranked_results = await self._rerank_results(query, deduplicated_results)
            else:
                reranked_results = sorted(deduplicated_results, key=lambda x: x.score, reverse=True)
            
            # Select top results and build context
            selected_results = await self._select_top_results(reranked_results)
            
            # Build final context with ontology enhancement
            context = await self._build_enhanced_context(selected_results, query, ontology_manager)
            
            # Calculate overall confidence
            confidence = await self._calculate_confidence(selected_results, vector_results, graph_results)
            
            # Prepare sources for response
            sources = await self._prepare_sources(selected_results)
            
            # Add ontological enhancements
            ontological_info = {}
            if ontology_manager:
                ontological_info = await self._get_ontological_enhancements(
                    query, selected_results, ontology_manager
                )
            
            return {
                'context': context,
                'sources': sources,
                'confidence': confidence,
                'ontological_enhancements': ontological_info,
                'synthesis_info': {
                    'method': 'enhanced_hybrid_synthesis',
                    'vector_count': len(vector_results),
                    'graph_count': len(graph_results),
                    'final_count': len(selected_results),
                    'deduplicated_count': len(deduplicated_results),
                    'ontology_enhanced': ontology_manager is not None
                }
            }
            
        except Exception as e:
            logger.error(f"Context synthesis error: {e}")
            raise
    
    async def _build_enhanced_context(self, selected_results: List[SynthesizedResult], 
                                    query: str, ontology_manager=None) -> str:
        """Build enhanced context with ontological knowledge"""
        try:
            # Build base context
            base_context = await self._build_context(selected_results)
            
            if not ontology_manager:
                return base_context
            
            # Extract concepts from query and results
            query_concepts = await self._extract_concepts_from_text(query)
            result_concepts = await self._extract_concepts_from_results(selected_results)
            
            # Get ontological enhancements
            ontological_enhancements = []
            for concept in query_concepts + result_concepts:
                related_concepts = await ontology_manager.find_related_concepts(concept)
                if related_concepts:
                    ontological_enhancements.extend(related_concepts)
            
            # Build enhanced context
            enhanced_parts = [base_context]
            
            if ontological_enhancements:
                enhancement_text = "Related concepts: " + ", ".join([
                    f"{c['name']} ({c['description']})" 
                    for c in ontological_enhancements[:5]  # Limit to top 5
                ])
                enhanced_parts.append(enhancement_text)
            
            return "\n\n---\n\n".join(enhanced_parts)
            
        except Exception as e:
            logger.error(f"Failed to build enhanced context: {e}")
            return await self._build_context(selected_results)
    
    async def _extract_concepts_from_text(self, text: str) -> List[str]:
        """Extract concept names from text"""
        # Simple extraction - could be enhanced with NLP
        words = text.split()
        return [word for word in words if len(word) > 3]  # Filter short words
    
    async def _extract_concepts_from_results(self, results: List[SynthesizedResult]) -> List[str]:
        """Extract concepts from search results"""
        concepts = []
        for result in results:
            content_words = result.content.split()
            concepts.extend([word for word in content_words if len(word) > 3])
        return list(set(concepts))
    
    async def _get_ontological_enhancements(self, query: str, selected_results: List[SynthesizedResult],
                                          ontology_manager) -> Dict[str, Any]:
        """Get ontological enhancements for the query and results"""
        try:
            query_concepts = await self._extract_concepts_from_text(query)
            result_concepts = await self._extract_concepts_from_results(selected_results)
            
            enhancements = {
                "query_concepts": query_concepts,
                "result_concepts": result_concepts,
                "related_concepts": [],
                "hierarchical_context": []
            }
            
            # Get related concepts for each concept
            all_concepts = list(set(query_concepts + result_concepts))
            for concept in all_concepts:
                related = await ontology_manager.find_related_concepts(concept)
                if related:
                    enhancements["related_concepts"].extend(related)
            
            return enhancements
            
        except Exception as e:
            logger.error(f"Failed to get ontological enhancements: {e}")
            return {}

    async def _process_vector_results(self, vector_results: List[Any]) -> List[SynthesizedResult]:
        """Process vector search results into unified format"""
        processed = []
        
        for result in vector_results:
            try:
                content = result.payload.get('content', '')
                metadata = result.payload.get('metadata', {})
                
                synthesized = SynthesizedResult(
                    content=content,
                    score=float(result.score),
                    source_type='vector',
                    metadata=metadata,
                    relevance_score=float(result.score)
                )
                processed.append(synthesized)
                
            except Exception as e:
                logger.warning(f"Error processing vector result: {e}")
                continue
                
        return processed

    async def _process_graph_results(self, graph_results: List[Dict[str, Any]]) -> List[SynthesizedResult]:
        """Process graph search results into unified format"""
        processed = []
        
        for result in graph_results:
            try:
                content = result.get('content', '')
                score = result.get('score', 0.0)
                metadata = result.get('metadata', {})
                
                synthesized = SynthesizedResult(
                    content=content,
                    score=float(score),
                    source_type='graph',
                    metadata=metadata,
                    relevance_score=float(score)
                )
                processed.append(synthesized)
                
            except Exception as e:
                logger.warning(f"Error processing graph result: {e}")
                continue
                
        return processed

    async def _deduplicate_results(self, results: List[SynthesizedResult]) -> List[SynthesizedResult]:
        """Remove duplicate and near-duplicate results"""
        if not results or not self.embedding_model:
            return results
            
        try:
            # Get embeddings for all content
            contents = [result.content for result in results]
            embeddings = self.embedding_model.encode(contents)
            
            # Find duplicates using cosine similarity
            similarity_matrix = cosine_similarity(embeddings)
            
            # Keep track of indices to remove
            to_remove = set()
            
            for i in range(len(results)):
                if i in to_remove:
                    continue
                    
                for j in range(i + 1, len(results)):
                    if j in to_remove:
                        continue
                        
                    similarity = similarity_matrix[i][j]
                    
                    if similarity > self.similarity_threshold:
                        # Keep the one with higher score
                        if results[i].score >= results[j].score:
                            to_remove.add(j)
                        else:
                            to_remove.add(i)
                            break
            
            # Return results without duplicates
            deduplicated = [result for i, result in enumerate(results) if i not in to_remove]
            
            logger.info(f"Deduplication: {len(results)} -> {len(deduplicated)} results")
            return deduplicated
            
        except Exception as e:
            logger.error(f"Deduplication error: {e}")
            return results

    async def _rerank_results(self, query: str, results: List[SynthesizedResult]) -> List[SynthesizedResult]:
        """Rerank results based on query relevance"""
        if not results or not self.embedding_model:
            return results
            
        try:
            # Get query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Get content embeddings
            contents = [result.content for result in results]
            content_embeddings = self.embedding_model.encode(contents)
            
            # Calculate relevance scores
            relevance_scores = cosine_similarity(query_embedding, content_embeddings)[0]
            
            # Update relevance scores and combine with original scores
            for i, result in enumerate(results):
                result.relevance_score = float(relevance_scores[i])
                # Combine original score with relevance score
                result.score = (result.score * 0.6) + (result.relevance_score * 0.4)
            
            # Sort by combined score
            return sorted(results, key=lambda x: x.score, reverse=True)
            
        except Exception as e:
            logger.error(f"Reranking error: {e}")
            return results

    async def _select_top_results(self, results: List[SynthesizedResult]) -> List[SynthesizedResult]:
        """Select top results based on score and diversity"""
        if not results:
            return results
            
        selected = []
        current_length = 0
        
        # Ensure we have results from both sources if available
        vector_results = [r for r in results if r.source_type == 'vector']
        graph_results = [r for r in results if r.source_type == 'graph']
        
        # Interleave results from both sources
        max_per_source = 5
        vector_count = 0
        graph_count = 0
        
        for result in results:
            # Check if adding this result would exceed context length
            if current_length + len(result.content) > self.max_context_length:
                break
                
            # Limit results per source type for diversity
            if result.source_type == 'vector' and vector_count >= max_per_source:
                continue
            if result.source_type == 'graph' and graph_count >= max_per_source:
                continue
                
            selected.append(result)
            current_length += len(result.content)
            
            if result.source_type == 'vector':
                vector_count += 1
            else:
                graph_count += 1
                
            # Stop if we have enough results
            if len(selected) >= 10:
                break
        
        return selected

    async def _build_context(self, results: List[SynthesizedResult]) -> str:
        """Build final context string from selected results"""
        if not results:
            return ""
            
        context_parts = []
        
        for i, result in enumerate(results):
            # Add source type indicator
            source_indicator = f"[{result.source_type.upper()}]"
            
            # Add metadata if available
            metadata_str = ""
            if result.metadata:
                title = result.metadata.get('title', '')
                if title:
                    metadata_str = f" ({title})"
            
            # Format the content
            formatted_content = f"{source_indicator}{metadata_str}: {result.content}"
            context_parts.append(formatted_content)
        
        return "\n\n".join(context_parts)

    async def _calculate_confidence(self, selected_results: List[SynthesizedResult], 
                                  vector_results: List[Any], graph_results: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence score"""
        if not selected_results:
            return 0.0
            
        # Base confidence on average score of selected results
        avg_score = sum(result.score for result in selected_results) / len(selected_results)
        
        # Boost confidence if we have results from both sources
        source_types = set(result.source_type for result in selected_results)
        source_diversity_bonus = 0.1 if len(source_types) > 1 else 0.0
        
        # Boost confidence based on number of results
        result_count_bonus = min(len(selected_results) / 10, 0.1)
        
        # Final confidence score
        confidence = min(avg_score + source_diversity_bonus + result_count_bonus, 1.0)
        
        return confidence

    async def _prepare_sources(self, results: List[SynthesizedResult]) -> List[Dict[str, Any]]:
        """Prepare sources for API response"""
        sources = []
        
        for result in results:
            source = {
                'type': result.source_type,
                'content': result.content,
                'score': result.score,
                'metadata': result.metadata,
                'relevance_score': result.relevance_score
            }
            sources.append(source)
            
        return sources

    async def close(self):
        """Cleanup resources"""
        # Clean up embedding model if needed
        self.embedding_model = None
        logger.info("Context synthesizer closed")