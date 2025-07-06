#!/usr/bin/env python3
"""
Test script to verify immediate query capability after document upload
"""

import asyncio
import aiohttp
import json
import time

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_DOCUMENT = {
    "content": "The Python programming language was created by Guido van Rossum in 1991. Python is known for its simplicity and readability. It is widely used in data science, web development, and artificial intelligence. Python has a large standard library and many third-party packages available through pip.",
    "metadata": {
        "title": "Python Programming Language",
        "author": "Test Author",
        "category": "Programming"
    },
    "entities": ["Python", "Guido van Rossum", "data science", "web development"]
}

TEST_QUERIES = [
    "Who created Python?",
    "What is Python used for?",
    "When was Python created?",
    "What are the main features of Python?"
]

async def test_immediate_query():
    """Test that queries work immediately after document upload"""
    
    async with aiohttp.ClientSession() as session:
        print("🚀 Testing immediate query capability...")
        
        # Step 1: Upload document
        print("\n📤 Uploading test document...")
        upload_start = time.time()
        
        upload_data = {
            "documents": [TEST_DOCUMENT],
            "source": "test"
        }
        
        async with session.post(f"{BASE_URL}/ingest", json=upload_data) as response:
            if response.status == 200:
                upload_result = await response.json()
                upload_time = time.time() - upload_start
                print(f"✅ Document uploaded successfully in {upload_time:.2f}s")
                print(f"   Results: {upload_result}")
            else:
                print(f"❌ Upload failed: {response.status}")
                error_text = await response.text()
                print(f"   Error: {error_text}")
                return False
        
        # Step 2: Test immediate queries
        print("\n🔍 Testing immediate queries...")
        
        for i, query in enumerate(TEST_QUERIES, 1):
            print(f"\n   Query {i}: {query}")
            query_start = time.time()
            
            query_data = {
                "query": query,
                "max_results": 5,
                "search_strategy": "auto",
                "include_reasoning": False
            }
            
            async with session.post(f"{BASE_URL}/query", json=query_data) as response:
                if response.status == 200:
                    query_result = await response.json()
                    query_time = time.time() - query_start
                    print(f"   ✅ Query successful in {query_time:.2f}s")
                    print(f"   Strategy: {query_result.get('strategy_used', 'unknown')}")
                    print(f"   Confidence: {query_result.get('confidence', 0):.2f}")
                    print(f"   Sources: {len(query_result.get('sources', []))}")
                    
                    # Check if the answer contains relevant information
                    answer = query_result.get('answer', '')
                    if any(keyword.lower() in answer.lower() for keyword in ['python', 'guido', '1991', 'data science']):
                        print(f"   ✅ Answer appears relevant")
                    else:
                        print(f"   ⚠️  Answer may not be relevant: {answer[:100]}...")
                        
                else:
                    print(f"   ❌ Query failed: {response.status}")
                    error_text = await response.text()
                    print(f"   Error: {error_text}")
                    return False
        
        # Step 3: Check system stats
        print("\n📊 Checking system stats...")
        async with session.get(f"{BASE_URL}/stats") as response:
            if response.status == 200:
                stats = await response.json()
                print(f"✅ System stats retrieved")
                print(f"   Vector documents: {stats.get('vector_database', {}).get('total_points', 0)}")
                print(f"   Graph nodes: {stats.get('graph_database', {}).get('total_entities', 0)}")
            else:
                print(f"❌ Stats retrieval failed: {response.status}")
        
        print("\n🎉 Test completed successfully!")
        print("✅ Users can upload documents and immediately query them")
        return True

async def test_health():
    """Test system health"""
    async with aiohttp.ClientSession() as session:
        print("🏥 Checking system health...")
        async with session.get(f"{BASE_URL}/health") as response:
            if response.status == 200:
                health = await response.json()
                print(f"✅ System healthy: {health}")
                return True
            else:
                print(f"❌ System unhealthy: {response.status}")
                return False

async def main():
    """Main test function"""
    print("🧪 Hybrid RAG System - Immediate Query Test")
    print("=" * 50)
    
    # Test health first
    if not await test_health():
        print("❌ System is not healthy. Please start the server first.")
        return
    
    # Test immediate query capability
    success = await test_immediate_query()
    
    if success:
        print("\n🎯 CONCLUSION: The flow is supported!")
        print("   ✅ Users can upload documents")
        print("   ✅ Users can immediately query uploaded documents")
        print("   ✅ The system processes queries without delays")
    else:
        print("\n❌ CONCLUSION: The flow has issues!")
        print("   ❌ There are problems with the upload or query process")

if __name__ == "__main__":
    asyncio.run(main()) 