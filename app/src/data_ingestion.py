"""
Data Ingestion for Hybrid RAG System
Handles document processing and ingestion into both vector and graph databases
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import json
from datetime import datetime
import re
from dataclasses import dataclass
import spacy
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

@dataclass
class ProcessedDocument:
    """Represents a processed document ready for ingestion"""
    id: str
    content: str
    chunks: List[str]
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    embeddings: Optional[List[List[float]]] = None

class DataIngestion:
    """
    Handles document processing and ingestion into vector and graph databases
    """
    
    def __init__(self, vector_search, graph_search, settings, ontology_manager=None, cross_reference_manager=None):
        self.vector_search = vector_search
        self.graph_search = graph_search
        self.settings = settings
        self.ontology_manager = ontology_manager
        self.cross_reference_manager = cross_reference_manager
        
        # Configuration
        self.chunk_size = getattr(settings, 'CHUNK_SIZE', 1000)
        self.chunk_overlap = getattr(settings, 'CHUNK_OVERLAP', 200)
        self.max_entities_per_chunk = getattr(settings, 'MAX_ENTITIES_PER_CHUNK', 10)
        
        # Models
        self.nlp = None
        self.embedding_model = None
        
        # Entity extraction settings
        self.entity_types = [
            'PERSON', 'ORG', 'GPE', 'EVENT', 'PRODUCT', 
            'WORK_OF_ART', 'LAW', 'LANGUAGE', 'DATE', 'TIME',
            'MONEY', 'QUANTITY', 'ORDINAL', 'CARDINAL'
        ]
        
    async def initialize(self):
        """Initialize NLP models and components"""
        try:
            # Load spaCy model
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy model: en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found. Installing...")
                # In production, you'd want to handle this differently
                self.nlp = None
                
            # Load sentence transformer
            model_name = getattr(self.settings, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            self.embedding_model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize data ingestion components: {e}")
            raise
    
    async def ingest_documents(self, documents: List[Dict[str, Any]], source: str = "api") -> Dict[str, Any]:
        """
        Ingest a batch of documents into both vector and graph databases
        
        Args:
            documents: List of document dictionaries
            source: Source identifier for the documents
            
        Returns:
            Dictionary with ingestion results
        """
        try:
            logger.info(f"Starting ingestion of {len(documents)} documents from source: {source}")
            
            results = {
                'total_documents': len(documents),
                'successful_ingestions': 0,
                'failed_ingestions': 0,
                'vector_ingestions': 0,
                'graph_ingestions': 0,
                'errors': []
            }
            
            # Process documents in batches
            batch_size = getattr(self.settings, 'INGESTION_BATCH_SIZE', 10)
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_results = await self._process_document_batch(batch, source)
                
                # Aggregate results
                results['successful_ingestions'] += batch_results['successful_ingestions']
                results['failed_ingestions'] += batch_results['failed_ingestions']
                results['vector_ingestions'] += batch_results['vector_ingestions']
                results['graph_ingestions'] += batch_results['graph_ingestions']
                results['errors'].extend(batch_results['errors'])
                
                # Brief pause between batches
                await asyncio.sleep(0.1)
            
            logger.info(f"Ingestion completed: {results['successful_ingestions']}/{results['total_documents']} successful")
            return results
            
        except Exception as e:
            logger.error(f"Document ingestion error: {e}")
            raise
    
    async def _process_document_batch(self, documents: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        """Process a batch of documents"""
        
        results = {
            'successful_ingestions': 0,
            'failed_ingestions': 0,
            'vector_ingestions': 0,
            'graph_ingestions': 0,
            'errors': []
        }
        
        for doc in documents:
            try:
                # Process the document
                processed_doc = await self._process_document(doc, source)
                
                # Ingest into vector database
                vector_success = await self._ingest_to_vector_db(processed_doc)
                if vector_success:
                    results['vector_ingestions'] += 1
                
                # Ingest into graph database
                graph_success = await self._ingest_to_graph_db(processed_doc)
                if graph_success:
                    results['graph_ingestions'] += 1
                
                # Create cross-references if both ingestions were successful
                if vector_success and graph_success and self.cross_reference_manager:
                    await self._create_cross_references(processed_doc)
                
                if vector_success or graph_success:
                    results['successful_ingestions'] += 1
                else:
                    results['failed_ingestions'] += 1
                    
            except Exception as e:
                error_msg = f"Error processing document: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                results['failed_ingestions'] += 1
        
        return results
    
    async def _process_document(self, doc: Dict[str, Any], source: str) -> ProcessedDocument:
        """Process a single document"""
        
        # Extract basic information
        content = doc.get('content', '')
        metadata = doc.get('metadata', {})
        provided_entities = doc.get('entities', [])
        
        # Generate document ID
        doc_id = self._generate_document_id(content, metadata)
        
        # Add source and timestamp to metadata
        metadata.update({
            'source': source,
            'ingestion_timestamp': datetime.now().isoformat(),
            'content_length': len(content),
            'doc_id': doc_id
        })
        
        # Chunk the document
        chunks = await self._chunk_document(content)
        
        # Extract entities and relationships
        entities = await self._extract_entities(content, provided_entities)
        relationships = await self._extract_relationships(content, entities)
        
        # Generate embeddings
        embeddings = None
        if self.embedding_model:
            embeddings = await self._generate_embeddings(chunks)
        
        # Create ontological concepts if ontology manager is available
        ontological_concepts = []
        if self.ontology_manager:
            ontological_concepts = await self._create_ontological_concepts(entities, content)
        
        return ProcessedDocument(
            id=doc_id,
            content=content,
            chunks=chunks,
            entities=entities,
            relationships=relationships,
            metadata=metadata,
            embeddings=embeddings
        )
    
    def _generate_document_id(self, content: str, metadata: Dict[str, Any]) -> str:
        """Generate a unique document ID"""
        # Use content hash and metadata for uniqueness
        content_hash = hashlib.md5(content.encode()).hexdigest()
        metadata_str = json.dumps(metadata, sort_keys=True)
        metadata_hash = hashlib.md5(metadata_str.encode()).hexdigest()
        
        return f"doc_{content_hash[:8]}_{metadata_hash[:8]}"
    
    async def _chunk_document(self, content: str) -> List[str]:
        """Split document into chunks with overlap"""
        
        if not content:
            return []
        
        # Simple sentence-based chunking
        sentences = self._split_into_sentences(content)
        chunks = []
        
        current_chunk = ""
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence would exceed chunk size, start a new chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, self.chunk_overlap)
                current_chunk = overlap_text + " " + sentence
                current_length = len(current_chunk)
            else:
                current_chunk += " " + sentence
                current_length += sentence_length
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting using regex
        sentence_pattern = r'[.!?]+[\s]+'
        sentences = re.split(sentence_pattern, text)
        
        # Clean up sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # Minimum sentence length
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _get_overlap_text(self, chunk: str, overlap_length: int) -> str:
        """Get overlap text from the end of a chunk"""
        if len(chunk) <= overlap_length:
            return chunk
        
        # Try to find a good break point (sentence boundary)
        overlap_text = chunk[-overlap_length:]
        
        # Find the first sentence boundary
        sentence_start = re.search(r'[.!?]\s+', overlap_text)
        if sentence_start:
            return overlap_text[sentence_start.end():]
        
        return overlap_text
    
    async def _extract_entities(self, content: str, provided_entities: List[str] = None) -> List[Dict[str, Any]]:
        """Extract named entities from content"""
        
        entities = []
        
        # Add provided entities
        if provided_entities:
            for entity in provided_entities:
                entities.append({
                    'text': entity,
                    'label': 'PROVIDED',
                    'confidence': 1.0,
                    'start': 0,
                    'end': 0
                })
        
        # Extract entities using spaCy if available
        if self.nlp and content:
            try:
                # Use executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                doc = await loop.run_in_executor(
                    None,  # Use default executor
                    self.nlp,
                    content
                )
                
                for ent in doc.ents:
                    if ent.label_ in self.entity_types:
                        entities.append({
                            'text': ent.text,
                            'label': ent.label_,
                            'confidence': 1.0,  # spaCy doesn't provide confidence scores
                            'start': ent.start_char,
                            'end': ent.end_char
                        })
            
            except Exception as e:
                logger.warning(f"Entity extraction error: {e}")
        
        # Remove duplicates and limit number
        unique_entities = []
        seen_texts = set()
        
        for entity in entities:
            entity_text = entity['text'].lower()
            if entity_text not in seen_texts:
                seen_texts.add(entity_text)
                unique_entities.append(entity)
                
                if len(unique_entities) >= self.max_entities_per_chunk:
                    break
        
        return unique_entities
    
    async def _extract_relationships(self, content: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between entities"""
        
        relationships = []
        
        if not entities or len(entities) < 2:
            return relationships
        
        # Simple co-occurrence based relationship extraction
        entity_texts = [entity['text'] for entity in entities]
        
        for i, entity1 in enumerate(entities):
            for j, entity2 in enumerate(entities):
                if i >= j:  # Avoid duplicates and self-relationships
                    continue
                
                # Check if entities co-occur in the same sentence
                if self._entities_cooccur(content, entity1['text'], entity2['text']):
                    relationships.append({
                        'source': entity1['text'],
                        'target': entity2['text'],
                        'relation': 'CO_OCCURS',
                        'confidence': 0.7,
                        'context': self._get_relationship_context(content, entity1['text'], entity2['text'])
                    })
        
        return relationships
    
    def _entities_cooccur(self, content: str, entity1: str, entity2: str) -> bool:
        """Check if two entities co-occur in the same sentence"""
        sentences = self._split_into_sentences(content)
        
        for sentence in sentences:
            if entity1.lower() in sentence.lower() and entity2.lower() in sentence.lower():
                return True
        
        return False
    
    def _get_relationship_context(self, content: str, entity1: str, entity2: str) -> str:
        """Get context for a relationship between two entities"""
        sentences = self._split_into_sentences(content)
        
        for sentence in sentences:
            if entity1.lower() in sentence.lower() and entity2.lower() in sentence.lower():
                return sentence[:200]  # Limit context length
        
        return ""
    
    async def _generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Generate embeddings for document chunks"""
        
        if not self.embedding_model or not chunks:
            return []
        
        try:
            # Use executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,  # Use default executor
                self.embedding_model.encode,
                chunks
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return []
    
    async def _create_ontological_concepts(self, entities: List[Dict[str, Any]], content: str) -> List[str]:
        """Create ontological concepts from entities and content"""
        try:
            if not self.ontology_manager:
                return []
            
            concept_ids = []
            
            # Create concepts for each entity
            for entity in entities:
                entity_name = entity.get("text", "")
                entity_type = entity.get("label", "")
                
                if entity_name:
                    # Create concept with description from context
                    description = await self._extract_entity_description(content, entity_name)
                    
                    concept_id = await self.ontology_manager.add_concept(
                        name=entity_name,
                        description=description
                    )
                    concept_ids.append(concept_id)
            
            # Create higher-level concepts based on entity types
            type_concepts = {}
            for entity in entities:
                entity_type = entity.get("label", "")
                if entity_type and entity_type not in type_concepts:
                    type_concept_id = await self.ontology_manager.add_concept(
                        name=entity_type,
                        description=f"Category of {entity_type} entities"
                    )
                    type_concepts[entity_type] = type_concept_id
                    concept_ids.append(type_concept_id)
            
            return concept_ids
            
        except Exception as e:
            logger.error(f"Failed to create ontological concepts: {e}")
            return []
    
    async def _extract_entity_description(self, content: str, entity_name: str) -> str:
        """Extract description of an entity from content"""
        try:
            # Find sentences containing the entity
            sentences = content.split('.')
            entity_sentences = []
            
            for sentence in sentences:
                if entity_name.lower() in sentence.lower():
                    entity_sentences.append(sentence.strip())
            
            # Return the first sentence that mentions the entity
            if entity_sentences:
                return entity_sentences[0][:200] + "..."  # Limit length
            
            return f"Entity: {entity_name}"
            
        except Exception as e:
            logger.error(f"Failed to extract entity description: {e}")
            return f"Entity: {entity_name}"
    
    async def _create_cross_references(self, processed_doc: ProcessedDocument):
        """Create cross-references between vector and graph data"""
        try:
            if not self.cross_reference_manager:
                return
            
            # For each chunk in the vector database, create cross-references to graph entities
            for i, chunk in enumerate(processed_doc.chunks):
                vector_doc_id = f"{processed_doc.id}_{i}"
                
                # Find entities mentioned in this chunk
                chunk_entities = []
                for entity in processed_doc.entities:
                    if entity.get("text", "").lower() in chunk.lower():
                        chunk_entities.append(entity)
                
                # Create cross-references for each entity
                for entity in chunk_entities:
                    entity_id = f"entity_{hashlib.md5(entity['text'].encode()).hexdigest()[:8]}"
                    
                    await self.cross_reference_manager.add_cross_reference(
                        vector_doc_id=vector_doc_id,
                        graph_entity_id=entity_id,
                        relationship_type="MENTIONS",
                        confidence=entity.get("confidence", 0.8),
                        evidence=f"Entity '{entity['text']}' found in document chunk"
                    )
            
            logger.info(f"Created cross-references for document {processed_doc.id}")
            
        except Exception as e:
            logger.error(f"Failed to create cross-references: {e}")
    
    async def _ingest_to_vector_db(self, processed_doc: ProcessedDocument) -> bool:
        """Ingest processed document into vector database"""
        
        try:
            if not processed_doc.chunks:
                return False
            
            # Prepare points for vector database
            points = []
            
            for i, chunk in enumerate(processed_doc.chunks):
                # Get embedding for this chunk
                embedding = None
                if processed_doc.embeddings and i < len(processed_doc.embeddings):
                    embedding = processed_doc.embeddings[i]
                elif self.embedding_model:
                    # Use executor to avoid blocking the event loop
                    loop = asyncio.get_event_loop()
                    embedding = await loop.run_in_executor(
                        None,  # Use default executor
                        self.embedding_model.encode,
                        [chunk]
                    )
                    embedding = embedding[0].tolist()
                
                if embedding:
                    point_id = f"{processed_doc.id}_{i}"
                    
                    payload = {
                        'content': chunk,
                        'doc_id': processed_doc.id,
                        'chunk_index': i,
                        'metadata': processed_doc.metadata,
                        'entities': [e['text'] for e in processed_doc.entities],
                        'chunk_length': len(chunk)
                    }
                    
                    points.append({
                        'id': point_id,
                        'vector': embedding,
                        'payload': payload
                    })
            
            if points:
                # Use the vector search's upsert method
                await self.vector_search.upsert_points(points)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Vector database ingestion error: {e}")
            return False
    
    async def _ingest_to_graph_db(self, processed_doc: ProcessedDocument) -> bool:
        """Ingest processed document into graph database"""
        
        try:
            # Create document node
            doc_node = {
                'id': processed_doc.id,
                'type': 'document',
                'content': processed_doc.content[:1000],  # Limit content length
                'metadata': processed_doc.metadata,
                'chunk_count': len(processed_doc.chunks)
            }
            
            # Create entity nodes
            entity_nodes = []
            for entity in processed_doc.entities:
                entity_node = {
                    'id': f"entity_{hashlib.md5(entity['text'].encode()).hexdigest()[:8]}",
                    'type': 'entity',
                    'text': entity['text'],
                    'label': entity['label'],
                    'confidence': entity['confidence']
                }
                entity_nodes.append(entity_node)
            
            # Create relationships
            relationships = []
            
            # Document-entity relationships
            for entity in processed_doc.entities:
                entity_id = f"entity_{hashlib.md5(entity['text'].encode()).hexdigest()[:8]}"
                relationships.append({
                    'source': processed_doc.id,
                    'target': entity_id,
                    'relation': 'CONTAINS',
                    'metadata': {'confidence': entity['confidence']}
                })
            
            # Entity-entity relationships
            for relationship in processed_doc.relationships:
                source_id = f"entity_{hashlib.md5(relationship['source'].encode()).hexdigest()[:8]}"
                target_id = f"entity_{hashlib.md5(relationship['target'].encode()).hexdigest()[:8]}"
                
                relationships.append({
                    'source': source_id,
                    'target': target_id,
                    'relation': relationship['relation'],
                    'metadata': {
                        'confidence': relationship['confidence'],
                        'context': relationship['context']
                    }
                })
            
            # Ingest into graph database
            success = await self.graph_search.ingest_graph_data(
                nodes=[doc_node] + entity_nodes,
                relationships=relationships
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Graph database ingestion error: {e}")
            return False
    
    async def update_document(self, doc_id: str, updated_doc: Dict[str, Any]) -> bool:
        """Update an existing document"""
        
        try:
            # First, remove the old document
            await self.delete_document(doc_id)
            
            # Then, ingest the updated document
            result = await self.ingest_documents([updated_doc], source="update")
            
            return result['successful_ingestions'] > 0
            
        except Exception as e:
            logger.error(f"Document update error: {e}")
            return False
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from both databases"""
        
        try:
            # Delete from vector database
            vector_success = await self.vector_search.delete_document(doc_id)
            
            # Delete from graph database
            graph_success = await self.graph_search.delete_document(doc_id)
            
            return vector_success or graph_success
            
        except Exception as e:
            logger.error(f"Document deletion error: {e}")
            return False
    
    async def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics about ingested documents"""
        
        try:
            vector_stats = await self.vector_search.get_stats()
            graph_stats = await self.graph_search.get_stats()
            
            return {
                'vector_documents': vector_stats.get('total_points', 0),
                'graph_nodes': graph_stats.get('total_nodes', 0),
                'graph_relationships': graph_stats.get('total_relationships', 0),
                'last_ingestion': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Stats retrieval error: {e}")
            return {}
    
    async def close(self):
        """Cleanup resources"""
        # Clean up NLP models
        self.nlp = None
        self.embedding_model = None
        logger.info("Data ingestion closed")