from typing import Dict, List, Any
import logging
import re
from collections import Counter
import spacy

from src.config import Settings

logger = logging.getLogger(__name__)

class QueryRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.nlp = None
        
        # Initialize NLP model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("SpaCy model not found, using pattern-based routing")
            self.nlp = None
            
        # Define routing patterns
        self.graph_indicators = [
            # Relationship queries
            "relationship", "related", "connected", "linked", "associated",
            "connection", "ties", "bonds", "correlates", "corresponds",
            
            # Comparison queries
            "compare", "comparison", "contrast", "difference", "similar",
            "alike", "different", "versus", "vs", "against",
            
            # Hierarchical queries
            "hierarchy", "parent", "child", "ancestor", "descendant",
            "belongs to", "part of", "contains", "includes",
            
            # Network queries
            "network", "graph", "structure", "topology", "pathway",
            "chain", "sequence", "flow", "dependencies",
            
            # Entity-focused queries
            "who", "what", "which", "whose", "whom"
        ]
        
        self.vector_indicators = [
            # Semantic queries
            "meaning", "concept", "idea", "theme", "topic",
            "semantic", "contextual", "conceptual",
            
            # Content queries
            "about", "regarding", "concerning", "related to content",
            "discusses", "mentions", "describes", "explains",
            
            # Search queries
            "find", "search", "look for", "retrieve", "get",
            "show me", "tell me about", "information about"
        ]
        
    async def route_query(self, query: str, strategy_hint: str = "auto", 
                         context: Dict[str, Any] = None) -> str:
        """Route query to appropriate search strategy with context awareness"""
        try:
            # If strategy is explicitly specified, use it
            if strategy_hint in ["vector", "graph", "hybrid"]:
                return strategy_hint
                
            # Analyze query to determine best strategy
            analysis = await self._analyze_query(query)
            
            # Enhanced decision logic with context awareness
            strategy = await self._determine_strategy_with_context(query, analysis, context)
            
            logger.info(f"Query '{query}' routed to '{strategy}' strategy")
            return strategy
                
        except Exception as e:
            logger.error(f"Query routing failed: {e}")
            return "vector"  # Fallback to vector search
    
    async def _determine_strategy_with_context(self, query: str, analysis: Dict[str, Any], 
                                             context: Dict[str, Any] = None) -> str:
        """Determine strategy with context awareness"""
        
        # Base scoring
        vector_score = analysis["vector_indicators"] * 2
        graph_score = analysis["graph_indicators"] * 2
        entity_score = analysis["entity_count"] * 1.5
        
        # Context-aware adjustments
        if context:
            # Previous query context
            if context.get("previous_strategy") == "graph":
                graph_score += 1
            elif context.get("previous_strategy") == "vector":
                vector_score += 1
            
            # User preference context
            if context.get("user_preference") == "detailed":
                graph_score += 2
            elif context.get("user_preference") == "semantic":
                vector_score += 2
            
            # Domain context
            domain = context.get("domain", "")
            if domain in ["technical", "scientific", "medical"]:
                graph_score += 1.5
            elif domain in ["creative", "general"]:
                vector_score += 1.5
        
        # Query intent analysis
        intent = await self._analyze_query_intent(query)
        if intent == "relationship":
            graph_score += 3
        elif intent == "definition":
            vector_score += 2
        elif intent == "comparison":
            graph_score += 2
            vector_score += 1
        
        # Complexity-based adjustment
        if analysis["complexity"] == "complex":
            return "hybrid"
        elif analysis["complexity"] == "medium":
            if abs(vector_score - graph_score) < 2:
                return "hybrid"
        
        # Final decision
        if graph_score > vector_score + 2:
            return "graph"
        elif vector_score > graph_score + 2:
            return "vector"
        else:
            return "hybrid"
    
    async def _analyze_query_intent(self, query: str) -> str:
        """Analyze the intent behind the query"""
        query_lower = query.lower()
        
        # Relationship intent
        relationship_indicators = [
            "relationship", "related", "connected", "link", "association",
            "how does", "what connects", "relationship between"
        ]
        
        # Definition intent
        definition_indicators = [
            "what is", "define", "definition", "meaning", "explain",
            "describe", "tell me about"
        ]
        
        # Comparison intent
        comparison_indicators = [
            "compare", "difference", "similar", "versus", "vs",
            "contrast", "better", "worse"
        ]
        
        # Count indicators
        relationship_count = sum(1 for indicator in relationship_indicators if indicator in query_lower)
        definition_count = sum(1 for indicator in definition_indicators if indicator in query_lower)
        comparison_count = sum(1 for indicator in comparison_indicators if indicator in query_lower)
        
        # Determine intent
        if relationship_count > definition_count and relationship_count > comparison_count:
            return "relationship"
        elif definition_count > relationship_count and definition_count > comparison_count:
            return "definition"
        elif comparison_count > 0:
            return "comparison"
        else:
            return "general"
            
    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query characteristics"""
        analysis = {
            "entity_count": 0,
            "entity_density": 0.0,
            "graph_indicators": 0,
            "vector_indicators": 0,
            "question_type": "general",
            "complexity": "simple"
        }
        
        try:
            # Convert to lowercase for analysis
            query_lower = query.lower()
            
            # Count indicator words
            analysis["graph_indicators"] = sum(
                1 for indicator in self.graph_indicators 
                if indicator in query_lower
            )
            
            analysis["vector_indicators"] = sum(
                1 for indicator in self.vector_indicators 
                if indicator in query_lower
            )
            
            # Extract entities using NLP
            if self.nlp:
                doc = self.nlp(query)
                entities = [ent for ent in doc.ents if ent.label_ in 
                           ["PERSON", "ORG", "GPE", "PRODUCT", "EVENT"]]
                analysis["entity_count"] = len(entities)
                analysis["entity_density"] = len(entities) / len(doc) if len(doc) > 0 else 0
                
                # Determine question type
                if query.strip().endswith("?"):
                    if query_lower.startswith(("what", "which", "who", "whose", "whom")):
                        analysis["question_type"] = "entity_focused"
                    elif query_lower.startswith(("how", "why", "when", "where")):
                        analysis["question_type"] = "relationship_focused"
                    else:
                        analysis["question_type"] = "general"
                        
            else:
                # Simple pattern-based entity extraction
                entity_patterns = [
                    r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Person names
                    r'\b[A-Z][a-z]+ (?:Inc|Corp|Ltd|LLC|Company)\b',  # Organizations
                    r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b'  # Proper nouns
                ]
                
                entity_count = 0
                for pattern in entity_patterns:
                    matches = re.findall(pattern, query)
                    entity_count += len(matches)
                    
                analysis["entity_count"] = entity_count
                analysis["entity_density"] = entity_count / len(query.split()) if query.split() else 0
                
            # Determine complexity
            word_count = len(query.split())
            if word_count > 15 or analysis["entity_count"] > 3:
                analysis["complexity"] = "complex"
            elif word_count > 8 or analysis["entity_count"] > 1:
                analysis["complexity"] = "medium"
            else:
                analysis["complexity"] = "simple"
                
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return analysis
            
    def explain_routing_decision(self, query: str, strategy: str) -> str:
        """Explain why a particular strategy was chosen"""
        try:
            if strategy == "vector":
                return (
                    f"Vector search selected because the query '{query}' appears to be "
                    "content-focused and would benefit from semantic similarity matching."
                )
            elif strategy == "graph":
                return (
                    f"Graph search selected because the query '{query}' contains "
                    "relationship indicators or multiple entities that suggest "
                    "ontological connections are important."
                )
            elif strategy == "hybrid":
                return (
                    f"Hybrid search selected because the query '{query}' has both "
                    "semantic and relational aspects that would benefit from "
                    "combining vector and graph search approaches."
                )
            else:
                return f"Default vector search selected for query '{query}'."
                
        except Exception as e:
            logger.error(f"Failed to explain routing decision: {e}")
            return f"Strategy '{strategy}' was selected for the query."
            
    async def get_routing_stats(self) -> Dict[str, Any]:
        """Get statistics about query routing patterns"""
        # This would typically be implemented with a database to track routing decisions
        return {
            "total_queries": 0,
            "vector_queries": 0,
            "graph_queries": 0,
            "hybrid_queries": 0,
            "routing_accuracy": 0.0
        }