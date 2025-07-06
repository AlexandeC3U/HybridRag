from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import logging
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from src.config import Settings

logger = logging.getLogger(__name__)

class VectorSearch:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.embedding_model = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def initialize(self):
        """Initialize the vector search client and embedding model"""
        try:
            # Initialize Qdrant client
            self.client = QdrantClient(
                host=self.settings.qdrant_host,
                port=self.settings.qdrant_port
            )
            
            # Initialize embedding model
            if self.settings.use_openai:
                # Will be handled in the embedding method
                pass
            else:
                # Use local sentence transformer
                self.embedding_model = SentenceTransformer(self.settings.embedding_model)
                
            # Create collection if it doesn't exist
            await self._create_collection()
            
            logger.info("Vector search initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector search: {e}")
            raise
            
    async def _create_collection(self):
        """Create the vector collection if it doesn't exist"""
        try:
            # Run synchronous Qdrant operations in executor
            loop = asyncio.get_event_loop()
            
            def create_collection_sync():
                collections = self.client.get_collections()
                collection_names = [c.name for c in collections.collections]
                
                if self.settings.qdrant_collection_name not in collection_names:
                    self.client.create_collection(
                        collection_name=self.settings.qdrant_collection_name,
                        vectors_config=VectorParams(
                            size=self.settings.embedding_dimension,
                            distance=Distance.COSINE
                        )
                    )
                    return True
                return False
            
            created = await loop.run_in_executor(self.executor, create_collection_sync)
            if created:
                logger.info(f"Created collection: {self.settings.qdrant_collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
            
    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text"""
        try:
            if self.settings.use_openai:
                import openai
                client = openai.OpenAI(api_key=self.settings.openai_api_key)
                response = client.embeddings.create(
                    model=self.settings.openai_embedding_model,
                    input=text
                )
                return response.data[0].embedding
            else:
                # Use local model
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    self.executor, self.embedding_model.encode, text
                )
                return embedding.tolist()
                
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise
            
    async def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Add documents to the vector store"""
        try:
            points = []
            document_ids = []
            
            for doc in documents:
                doc_id = str(uuid.uuid4())
                document_ids.append(doc_id)
                
                # Get embedding for the document content
                embedding = await self._get_embedding(doc["content"])
                
                # Create point
                point = PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload={
                        "content": doc["content"],
                        "metadata": doc.get("metadata", {}),
                        "entities": doc.get("entities", []),
                        "source": doc.get("source", "unknown")
                    }
                )
                points.append(point)
                
            # Upload points to Qdrant
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self.client.upsert,
                collection_name=self.settings.qdrant_collection_name,
                points=points
            )
            
            logger.info(f"Added {len(documents)} documents to vector store")
            return document_ids
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise
            
    async def search(self, query: str, limit: int = 10, 
                    filter_conditions: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search for similar documents"""
        try:
            # Get query embedding
            query_embedding = await self._get_embedding(query)
            
            # Build filter if provided
            search_filter = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                search_filter = Filter(must=conditions)
                
            # Perform search
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self.executor,
                self.client.search,
                collection_name=self.settings.qdrant_collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=self.settings.similarity_threshold
            )
            
            logger.info(f"Vector search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
            
    async def get_similar_documents(self, document_id: str, limit: int = 5) -> List[Any]:
        """Get documents similar to a given document"""
        try:
            # Get the document
            doc = self.client.retrieve(
                collection_name=self.settings.qdrant_collection_name,
                ids=[document_id]
            )
            
            if not doc:
                return []
                
            # Use the document's vector for similarity search
            results = self.client.search(
                collection_name=self.settings.qdrant_collection_name,
                query_vector=doc[0].vector,
                limit=limit + 1  # +1 to exclude the document itself
            )
            
            # Filter out the original document
            filtered_results = [r for r in results if r.id != document_id]
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get similar documents: {e}")
            raise
            
    async def update_document(self, document_id: str, updated_content: str, 
                            updated_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update a document in the vector store"""
        try:
            # Get new embedding
            new_embedding = await self._get_embedding(updated_content)
            
            # Get existing document to preserve other fields
            existing = self.client.retrieve(
                collection_name=self.settings.qdrant_collection_name,
                ids=[document_id]
            )
            
            if not existing:
                return False
                
            # Update payload
            payload = existing[0].payload
            payload["content"] = updated_content
            if updated_metadata:
                payload["metadata"].update(updated_metadata)
                
            # Update point
            self.client.upsert(
                collection_name=self.settings.qdrant_collection_name,
                points=[PointStruct(
                    id=document_id,
                    vector=new_embedding,
                    payload=payload
                )]
            )
            
            logger.info(f"Updated document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            return False
            
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the vector store"""
        try:
            self.client.delete(
                collection_name=self.settings.qdrant_collection_name,
                points_selector=models.PointIdsList(
                    points=[document_id]
                )
            )
            
            logger.info(f"Deleted document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector database statistics"""
        try:
            collection_info = self.client.get_collection(
                collection_name=self.settings.qdrant_collection_name
            )
            
            return {
                "total_points": collection_info.points_count,
                "vector_dimension": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
            
    async def clear_all(self) -> bool:
        """Clear all documents from the collection"""
        try:
            self.client.delete_collection(self.settings.qdrant_collection_name)
            await self._create_collection()
            
            logger.info("Cleared all documents from vector store")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear vector store: {e}")
            return False
            
    async def close(self):
        """Close connections and cleanup"""
        try:
            if self.client:
                self.client.close()
            if self.executor:
                self.executor.shutdown(wait=True)
                
        except Exception as e:
            logger.error(f"Error closing vector search: {e}")