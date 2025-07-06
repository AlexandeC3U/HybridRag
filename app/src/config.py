from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password123"
    
    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "hybrid_rag_documents"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_embedding_model: str = "text-embedding-3-large"
    
    # Ollama Configuration (for local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2:7b-chat-q4_0"
    ollama_embedding_model: str = "nomic-embed-text"
    
    # Embedding Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Search Configuration
    max_search_results: int = 10
    similarity_threshold: float = 0.7
    
    # Context Synthesis Configuration
    max_context_length: int = 4000
    context_overlap: int = 200
    
    # Reranking Configuration
    enable_reranking: bool = True
    
    # Query Router Configuration
    entity_extraction_threshold: float = 0.5
    graph_query_indicators: list = [
        "relationship", "connected", "related", "similar", 
        "compare", "difference", "hierarchy", "parent", "child"
    ]
    
    # System Configuration
    log_level: str = "INFO"
    max_concurrent_requests: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Environment variable mappings
        env_prefix = ""
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Override with environment variables
        self.neo4j_uri = os.getenv("NEO4J_URI", self.neo4j_uri)
        self.neo4j_username = os.getenv("NEO4J_USERNAME", self.neo4j_username)
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", self.neo4j_password)
        
        self.qdrant_host = os.getenv("QDRANT_HOST", self.qdrant_host)
        self.qdrant_port = int(os.getenv("QDRANT_PORT", self.qdrant_port))
        
        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key)
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", self.ollama_base_url)
        
    @property
    def use_openai(self) -> bool:
        """Check if OpenAI API key is available"""
        return self.openai_api_key is not None and self.openai_api_key.strip() != ""
    
    @property
    def vector_config(self) -> dict:
        """Get vector database configuration"""
        return {
            "host": self.qdrant_host,
            "port": self.qdrant_port,
            "collection_name": self.qdrant_collection_name,
            "embedding_dimension": self.embedding_dimension
        }
    
    @property
    def graph_config(self) -> dict:
        """Get graph database configuration"""
        return {
            "uri": self.neo4j_uri,
            "username": self.neo4j_username,
            "password": self.neo4j_password
        }
    
    @property
    def llm_config(self) -> dict:
        """Get LLM configuration"""
        if self.use_openai:
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "embedding_model": self.openai_embedding_model
            }
        else:
            return {
                "provider": "ollama",
                "base_url": self.ollama_base_url,
                "model": self.ollama_model,
                "embedding_model": self.ollama_embedding_model
            }