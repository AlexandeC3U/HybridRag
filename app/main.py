from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import logging
from contextlib import asynccontextmanager
import re

from src.query_router import QueryRouter
from src.vector_search import VectorSearch
from src.graph_search import GraphSearch
from src.context_synthesizer import ContextSynthesizer
from src.llm_interface import LLMInterface
from src.data_ingestion import DataIngestion
from src.ontology_manager import OntologyManager
from src.cross_reference_manager import CrossReferenceManager
from src.config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize settings
settings = Settings()

# Global variables for components
query_router: QueryRouter = None
vector_search: VectorSearch = None
graph_search: GraphSearch = None
context_synthesizer: ContextSynthesizer = None
llm_interface: LLMInterface = None
data_ingestion: DataIngestion = None
ontology_manager: OntologyManager = None
cross_reference_manager: CrossReferenceManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup"""
    global query_router, vector_search, graph_search, context_synthesizer, llm_interface, data_ingestion, ontology_manager, cross_reference_manager
    
    try:
        logger.info("Initializing hybrid RAG system components...")
        
        # Initialize vector search
        vector_search = VectorSearch(settings)
        await vector_search.initialize()
        
        # Initialize graph search
        graph_search = GraphSearch(settings)
        await graph_search.initialize()
        
        # Initialize ontology manager
        ontology_manager = OntologyManager(graph_search, settings)
        await ontology_manager.initialize()
        
        # Initialize cross-reference manager
        cross_reference_manager = CrossReferenceManager(vector_search, graph_search, ontology_manager, settings)
        await cross_reference_manager.initialize()
        
        # Initialize LLM interface
        llm_interface = LLMInterface(settings)
        
        # Initialize context synthesizer
        context_synthesizer = ContextSynthesizer(settings)
        
        # Initialize query router
        query_router = QueryRouter(settings)
        
        # Initialize data ingestion with enhanced components
        data_ingestion = DataIngestion(vector_search, graph_search, settings, ontology_manager, cross_reference_manager)
        
        logger.info("All components initialized successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise
    finally:
        # Cleanup
        if vector_search:
            await vector_search.close()
        if graph_search:
            await graph_search.close()
        if ontology_manager:
            await ontology_manager.close()
        if cross_reference_manager:
            await cross_reference_manager.close()

# Create FastAPI app
app = FastAPI(
    title="Hybrid RAG System",
    description="A RAG system combining vector search and knowledge graphs",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models with validation
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="The query to process")
    max_results: Optional[int] = Field(default=10, ge=1, le=100, description="Maximum number of results to return")
    search_strategy: Optional[str] = Field(default="auto", description="Search strategy to use")
    include_reasoning: Optional[bool] = Field(default=False, description="Whether to include reasoning in response")
    
    @validator('search_strategy')
    def validate_search_strategy(cls, v):
        allowed_strategies = ["auto", "vector", "graph", "hybrid"]
        if v not in allowed_strategies:
            raise ValueError(f"search_strategy must be one of {allowed_strategies}")
        return v
    
    @validator('query')
    def validate_query(cls, v):
        # Remove potentially dangerous characters
        v = re.sub(r'[<>"\']', '', v)
        if not v.strip():
            raise ValueError("Query cannot be empty or only whitespace")
        return v.strip()

class Document(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000, description="Document content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Document metadata")
    entities: Optional[List[str]] = Field(default_factory=list, description="List of entities in the document")
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError("Document content cannot be empty or only whitespace")
        return v.strip()
    
    @validator('entities')
    def validate_entities(cls, v):
        if v is None:
            return []
        # Validate each entity
        validated_entities = []
        for entity in v:
            if isinstance(entity, str) and entity.strip():
                validated_entities.append(entity.strip())
        return validated_entities
    
class IngestRequest(BaseModel):
    documents: List[Document] = Field(..., min_items=1, max_items=1000, description="List of documents to ingest")
    source: Optional[str] = Field(default="api", max_length=100, description="Source of the documents")
    
    @validator('source')
    def validate_source(cls, v):
        # Remove potentially dangerous characters
        v = re.sub(r'[<>"\']', '', v)
        return v.strip()

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    strategy_used: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """Main query endpoint for the hybrid RAG system"""
    try:
        logger.info(f"Received query: {request.query}")
        
        # Validate that components are initialized
        if not all([query_router, vector_search, graph_search, context_synthesizer, llm_interface, ontology_manager, cross_reference_manager]):
            raise HTTPException(status_code=503, detail="System components not initialized")
        
        # Route the query to determine search strategy with context
        try:
            # Build context for routing
            routing_context = {
                "user_preference": request.include_reasoning and "detailed" or "standard",
                "query_complexity": "complex" if len(request.query.split()) > 10 else "simple"
            }
            strategy = await query_router.route_query(request.query, request.search_strategy, routing_context)
        except Exception as e:
            logger.error(f"Query routing failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to route query")
        
        # Perform search based on strategy
        try:
            if strategy == "vector":
                results = await vector_search.search(request.query, request.max_results)
                sources = [{"type": "vector", "content": r.payload.get("content", ""), 
                           "score": r.score, "metadata": r.payload.get("metadata", {})} 
                          for r in results]
            elif strategy == "graph":
                results = await graph_search.search(request.query, request.max_results)
                sources = [{"type": "graph", "content": r.get("content", ""), 
                           "score": r.get("score", 0), "metadata": r.get("metadata", {})} 
                          for r in results]
            else:  # hybrid
                vector_results = await vector_search.search(request.query, request.max_results // 2)
                graph_results = await graph_search.search(request.query, request.max_results // 2)
                
                # Combine and synthesize results with enhanced components
                combined_results = {
                    "vector": vector_results,
                    "graph": graph_results
                }
                
                synthesized_context = await context_synthesizer.synthesize(
                    request.query, combined_results, ontology_manager, cross_reference_manager
                )
                
                sources = synthesized_context.get("sources", [])
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise HTTPException(status_code=500, detail="Search operation failed")
        
        # Generate answer using LLM
        try:
            if strategy == "hybrid":
                context = synthesized_context.get("context", "")
                confidence = synthesized_context.get("confidence", 0.5)
            else:
                context = "\n".join([s["content"] for s in sources])
                confidence = sum([s["score"] for s in sources]) / len(sources) if sources else 0
            
            answer = await llm_interface.generate_answer(
                request.query, context, sources
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate answer")
        
        # Generate reasoning if requested
        reasoning = None
        if request.include_reasoning:
            try:
                reasoning = await llm_interface.generate_reasoning(
                    request.query, context, answer, strategy
                )
            except Exception as e:
                logger.error(f"Reasoning generation failed: {e}")
                # Don't fail the entire request if reasoning fails
                reasoning = "Failed to generate reasoning"
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            strategy_used=strategy,
            confidence=confidence,
            reasoning=reasoning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/ingest")
async def ingest_documents(request: IngestRequest):
    """Ingest documents into both vector and graph databases"""
    try:
        logger.info(f"Ingesting {len(request.documents)} documents")
        
        # Validate that components are initialized
        if not all([data_ingestion, vector_search, graph_search]):
            raise HTTPException(status_code=503, detail="System components not initialized")
        
        # Validate document sizes
        total_size = sum(len(doc.content) for doc in request.documents)
        if total_size > 10_000_000:  # 10MB limit
            raise HTTPException(status_code=413, detail="Total document size too large")
        
        try:
            results = await data_ingestion.ingest_documents(
                request.documents, request.source
            )
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to ingest documents")
        
        return {
            "message": f"Successfully ingested {len(request.documents)} documents",
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/stats")
async def get_system_stats():
    """Get system statistics"""
    try:
        vector_stats = await vector_search.get_stats()
        graph_stats = await graph_search.get_stats()
        
        return {
            "vector_database": vector_stats,
            "graph_database": graph_stats,
            "total_documents": vector_stats.get("total_points", 0)
        }
        
    except Exception as e:
        logger.error(f"Stats retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/clear")
async def clear_databases():
    """Clear all data from both databases (use with caution)"""
    try:
        await vector_search.clear_all()
        await graph_search.clear_all()
        
        return {"message": "All databases cleared successfully"}
        
    except Exception as e:
        logger.error(f"Database clearing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)