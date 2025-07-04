**Hybrid RAG System: Vector + Knowledge Graph**

**Articles**

https://www.qed42.com/insights/how-knowledge-graphs-take-rag-beyond-retrieval

https://arxiv.org/pdf/2408.04948

https://learnprompting.org/docs/retrieval_augmented_generation/hybridrag?srsltid=AfmBOor9RpE8hbFT4Zff1cHvrOIUB902fpG8piRHViBIhU3lGfOn1TRQ

![image](assets/hybridRAG.png)

**System Architecture**

**Core Components**

1. **Vector Database**: Qdrant (fast, scalable, Docker-native)
2. **Knowledge Graph**: Neo4j (industry standard for graph databases)
3. **LLM Interface**: OpenAI API (GPT-4) or local models via Ollama
4. **Query Router**: Intelligent routing between vector and graph search
5. **Context Synthesizer**: Combines results from both sources
6. **API Gateway**: FastAPI-based REST interface

**Architecture Diagram**

User Query → Query Router → \[Vector Search\] + \[Graph Search\] → Context Synthesizer → LLM → Response

↓ ↓ ↓

FastAPI Qdrant Neo4j

**Technology Stack**

- **Backend**: Python with FastAPI
- **Vector Store**: Qdrant
- **Knowledge Graph**: Neo4j
- **Embeddings**: OpenAI text-embedding-3-large or local Sentence-BERT
- **LLM**: OpenAI GPT-4 or local Ollama
- **Orchestration**: Docker Compose
- **Frontend**: Streamlit (for demo UI)

**Key Features**

**1\. Dual Search Strategy**

- **Vector Search**: Semantic similarity for content retrieval
- **Graph Search**: Ontological relationships and entity connections
- **Hybrid Scoring**: Combines relevance scores from both sources

**2\. Query Classification**

- Determines optimal search strategy based on query type
- Entity-heavy queries → Graph-first
- Conceptual queries → Vector-first
- Complex queries → Hybrid approach

**3\. Context Enrichment**

- Graph traversal for related entities
- Vector expansion for semantic neighbors
- Relationship-aware context building

**Implementation Plan**

**Phase 1: Core Infrastructure**

1. Docker environment setup
2. Database initialization
3. Data ingestion pipeline

**Phase 2: Search Implementation**

1. Vector search with embeddings
2. Graph search with Cypher queries
3. Query routing logic

**Phase 3: Integration & UI**

1. Result synthesis
2. LLM integration
3. Web interface

**Phase 4: Optimization**

1. Performance tuning
2. Advanced query strategies
3. Evaluation metrics

**Data Model**

**Vector Store Schema**

python

{

"id": "doc_123",

"content": "text content",

"embedding": \[0.1, 0.2, ...\],

"metadata": {

"source": "document.pdf",

"entities": \["entity1", "entity2"\],

"timestamp": "2024-01-01"

}

}

**Knowledge Graph Schema**

cypher

_// Nodes_

(:Document {id, title, content, source})

(:Entity {name, type, description})

(:Concept {name, definition, domain})

_// Relationships_

(:Document)-\[:CONTAINS\]->(:Entity)

(:Entity)-\[:RELATED_TO\]->(:Entity)

(:Entity)-\[:INSTANCE_OF\]->(:Concept)

(:Concept)-\[:SUBCLASS_OF\]->(:Concept)

**Deployment Strategy**

**Docker Compose Services**

- **app**: FastAPI application
- **qdrant**: Vector database
- **neo4j**: Graph database
- **ollama**: Local LLM (optional)
- **streamlit**: Demo UI

**Environment Variables**

- API keys for external services
- Database connection strings
- Model configurations

**Success Metrics**

1. **Retrieval Quality**: Precision@K, Recall@K
2. **Response Relevance**: Human evaluation scores
3. **Context Completeness**: Entity coverage, relationship depth
4. **Performance**: Query latency, throughput
5. **Hybrid Effectiveness**: Improvement over single-source RAG

**Next Steps**

1. Set up the Docker environment
2. Implement the core search engines
3. Create the query routing logic
4. Build the synthesis layer
5. Develop the user interface
6. Test with sample data