from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

from src.query_router import QueryRouter
from src.vector_search import VectorSearch
from src.graph_search import GraphSearch
from src.context_synthesizer import ContextSynthesizer
from src.llm_interface import LLMInterface
from src.data_ingestion import DataIngestion
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup"""
    global query_router, vector_search, graph_search, context_synthesizer, llm_interface, data_ingestion
    
    try:
        logger.info("Initializing hybrid RAG system components...")
        
        # Initialize vector search
        vector_search = VectorSearch(settings)
        await vector_search.initialize()
        
        # Initialize graph search
        graph_search = GraphSearch(settings)
        await graph_search.initialize()
        
        # Initialize LLM interface
        llm_interface = LLMInterface(settings)
        
        # Initialize context synthesizer
        context_synthesizer = ContextSynthesizer(settings)
        
        # Initialize query router
        query_router = QueryRouter(settings)
        
        # Initialize data ingestion
        data_ingestion = DataIngestion(vector_search, graph_search, settings)
        
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

# Pydantic models
class QueryRequest(BaseModel):
    query: str
    max_results: Optional[int] = 10
    search_strategy: Optional[str] = "auto"  # "auto", "vector", "graph", "hybrid"
    include_reasoning: Optional[bool] = False

class Document(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = {}
    entities: Optional[List[str]] = []
    
class IngestRequest(BaseModel):
    documents: List[Document]
    source: Optional[str] = "api"

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    strategy_used: str
    confidence: float
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
        
        # Route the query to determine search strategy
        strategy = await query_router.route_query(request.query, request.search_strategy)
        
        # Perform search based on strategy
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
            
            # Combine and synthesize results
            combined_results = {
                "vector": vector_results,
                "graph": graph_results
            }
            
            synthesized_context = await context_synthesizer.synthesize(
                request.query, combined_results
            )
            
            sources = synthesized_context.get("sources", [])
        
        # Generate answer using LLM
        if strategy == "hybrid":
            context = synthesized_context.get("context", "")
            confidence = synthesized_context.get("confidence", 0.5)
        else:
            context = "\n".join([s["content"] for s in sources])
            confidence = sum([s["score"] for s in sources]) / len(sources) if sources else 0
        
        answer = await llm_interface.generate_answer(
            request.query, context, sources
        )
        
        # Generate reasoning if requested
        reasoning = None
        if request.include_reasoning:
            reasoning = await llm_interface.generate_reasoning(
                request.query, context, answer, strategy
            )
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            strategy_used=strategy,
            confidence=confidence,
            reasoning=reasoning
        )
        
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest")
async def ingest_documents(request: IngestRequest):
    """Ingest documents into both vector and graph databases"""
    try:
        logger.info(f"Ingesting {len(request.documents)} documents")
        
        results = await data_ingestion.ingest_documents(
            request.documents, request.source
        )
        
        return {
            "message": f"Successfully ingested {len(request.documents)} documents",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Document ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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