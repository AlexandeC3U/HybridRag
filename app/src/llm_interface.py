"""
LLM Interface for Hybrid RAG System
Handles interaction with language models for answer generation
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
import openai
from openai import AsyncOpenAI
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMInterface:
    """
    Interface for interacting with language models
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.client = None
        self.model = getattr(settings, 'LLM_MODEL', 'gpt-3.5-turbo')
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.max_tokens = getattr(settings, 'MAX_TOKENS', 1000)
        self.temperature = getattr(settings, 'TEMPERATURE', 0.7)
        self.max_retries = getattr(settings, 'MAX_RETRIES', 3)
        
        # Initialize OpenAI client
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            logger.warning("No OpenAI API key provided. LLM functionality will be limited.")
    
    async def generate_answer(self, query: str, context: str, sources: List[Dict[str, Any]]) -> str:
        """
        Generate an answer based on query and context
        
        Args:
            query: User's question
            context: Retrieved context from search
            sources: List of source documents
            
        Returns:
            Generated answer string
        """
        try:
            if not self.client:
                return await self._generate_fallback_answer(query, context, sources)
            
            # Prepare the prompt
            prompt = await self._build_answer_prompt(query, context, sources)
            
            # Generate response
            response = await self._call_llm(prompt, self.max_tokens)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Answer generation error: {e}")
            return await self._generate_fallback_answer(query, context, sources)
    
    async def generate_reasoning(self, query: str, context: str, answer: str, strategy: str) -> str:
        """
        Generate reasoning explanation for the answer
        
        Args:
            query: User's question
            context: Retrieved context
            answer: Generated answer
            strategy: Search strategy used
            
        Returns:
            Reasoning explanation
        """
        try:
            if not self.client:
                return await self._generate_fallback_reasoning(query, context, answer, strategy)
            
            # Prepare reasoning prompt
            prompt = await self._build_reasoning_prompt(query, context, answer, strategy)
            
            # Generate reasoning
            response = await self._call_llm(prompt, 500)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Reasoning generation error: {e}")
            return await self._generate_fallback_reasoning(query, context, answer, strategy)
    
    async def _build_answer_prompt(self, query: str, context: str, sources: List[Dict[str, Any]]) -> str:
        """Build prompt for answer generation"""
        
        # Count sources by type
        source_counts = {}
        for source in sources:
            source_type = source.get('type', 'unknown')
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
        
        source_info = ", ".join([f"{count} {stype}" for stype, count in source_counts.items()])
        
        prompt = f"""You are an AI assistant that provides accurate, helpful answers based on the given context. 

QUERY: {query}

CONTEXT:
{context}

SOURCES: {source_info} sources were used to gather this information.

INSTRUCTIONS:
1. Answer the query based ONLY on the information provided in the context
2. If the context doesn't contain enough information to answer the query, say so clearly
3. Provide a comprehensive but concise answer
4. Use specific details from the context when relevant
5. If there are conflicting information in the context, acknowledge this
6. Do not add information not present in the context
7. Structure your answer clearly with proper formatting when appropriate

ANSWER:"""
        
        return prompt
    
    async def _build_reasoning_prompt(self, query: str, context: str, answer: str, strategy: str) -> str:
        """Build prompt for reasoning generation"""
        
        prompt = f"""Explain the reasoning behind the answer provided for the given query.

QUERY: {query}

CONTEXT USED:
{context[:1000]}...

ANSWER PROVIDED:
{answer}

SEARCH STRATEGY: {strategy}

Please provide a brief explanation of:
1. How the search strategy was appropriate for this query
2. What key information from the context supported the answer
3. Any limitations or uncertainties in the answer
4. How confident you are in the answer based on the available information

REASONING:"""
        
        return prompt
    
    async def _call_llm(self, prompt: str, max_tokens: int) -> str:
        """Make API call to language model with retry logic"""
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI assistant that provides accurate information based on given context."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                
                return response.choices[0].message.content
                
            except openai.RateLimitError:
                wait_time = 2 ** attempt
                logger.warning(f"Rate limit hit, waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                
            except openai.APIError as e:
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Unexpected error in LLM call (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)
        
        raise Exception("Max retries exceeded for LLM call")
    
    async def _generate_fallback_answer(self, query: str, context: str, sources: List[Dict[str, Any]]) -> str:
        """Generate a fallback answer when LLM is not available"""
        
        if not context:
            return "I don't have enough information to answer your question. Please try rephrasing your query or providing more context."
        
        # Simple extractive answer - return most relevant context snippets
        context_snippets = context.split('\n\n')
        
        # Filter out empty snippets and limit length
        relevant_snippets = []
        for snippet in context_snippets[:3]:  # Take first 3 snippets
            if snippet.strip() and len(snippet) > 20:
                relevant_snippets.append(snippet.strip())
        
        if relevant_snippets:
            answer = f"Based on the available information:\n\n"
            for i, snippet in enumerate(relevant_snippets):
                answer += f"{i+1}. {snippet}\n\n"
            
            answer += f"This information comes from {len(sources)} sources. "
            answer += "Please note that this is a simplified response due to limited processing capabilities."
            
            return answer
        else:
            return "I found some relevant information but couldn't process it effectively. Please try rephrasing your question."
    
    async def _generate_fallback_reasoning(self, query: str, context: str, answer: str, strategy: str) -> str:
        """Generate fallback reasoning when LLM is not available"""
        
        reasoning = f"Search Strategy: {strategy}\n\n"
        reasoning += f"The answer was generated based on the available context from the {strategy} search approach. "
        reasoning += f"The context contained {len(context.split())} words of relevant information. "
        reasoning += "Due to limited processing capabilities, a detailed reasoning analysis is not available. "
        reasoning += "The answer reflects the most relevant information found in the search results."
        
        return reasoning
    
    async def summarize_context(self, context: str, max_length: int = 500) -> str:
        """
        Summarize long context to fit within token limits
        
        Args:
            context: Long context string
            max_length: Maximum length for summary
            
        Returns:
            Summarized context
        """
        try:
            if len(context) <= max_length:
                return context
                
            if not self.client:
                # Simple truncation fallback
                return context[:max_length] + "..."
            
            prompt = f"""Summarize the following context while preserving the most important information for answering questions:

CONTEXT:
{context}

Provide a concise summary that captures the key facts, figures, and main points. Maximum length: {max_length} characters.

SUMMARY:"""
            
            summary = await self._call_llm(prompt, 200)
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Context summarization error: {e}")
            return context[:max_length] + "..."
    
    async def extract_entities(self, text: str) -> List[str]:
        """
        Extract named entities from text
        
        Args:
            text: Input text
            
        Returns:
            List of extracted entities
        """
        try:
            if not self.client:
                return []
            
            prompt = f"""Extract the main named entities (people, organizations, locations, products, concepts) from the following text:

TEXT:
{text}

Return only the entities as a JSON list of strings, for example: ["Entity1", "Entity2", "Entity3"]

ENTITIES:"""
            
            response = await self._call_llm(prompt, 200)
            
            # Try to parse JSON response
            try:
                entities = json.loads(response.strip())
                return entities if isinstance(entities, list) else []
            except json.JSONDecodeError:
                # Fallback: extract entities from plain text response
                lines = response.strip().split('\n')
                entities = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('[') and not line.startswith('{'):
                        # Remove common prefixes and clean up
                        line = line.replace('- ', '').replace('* ', '').replace('"', '')
                        if line:
                            entities.append(line)
                return entities[:10]  # Limit to 10 entities
                
        except Exception as e:
            logger.error(f"Entity extraction error: {e}")
            return []
    
    async def close(self):
        """Cleanup resources"""
        if self.client:
            await self.client.close()
        logger.info("LLM interface closed")