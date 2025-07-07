#!/bin/bash
set -e

# Variables (edit as needed)
NEO4J_CONTAINER=uns-neo4j
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-uns_password}

# Copy ontology file into Neo4j container
cp uns_ontology.ttl ./neo4j/init/uns_ontology.ttl

# Copy Cypher script into Neo4j container
cp scripts/init-ontology.cypher ./neo4j/init/init-ontology.cypher

# Wait for Neo4j to be ready
sleep 10

docker exec -i $NEO4J_CONTAINER cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD -f /docker-entrypoint-initdb.d/init-ontology.cypher

echo "UNS ontology imported and mapped successfully." 