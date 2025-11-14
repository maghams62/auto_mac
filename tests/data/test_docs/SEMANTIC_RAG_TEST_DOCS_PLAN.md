# Semantic RAG Test Documents Plan

## Overview

This document describes the test documents created to showcase semantic RAG (Retrieval-Augmented Generation) capabilities across diverse topics. These documents are designed to test the system's ability to find relevant content using semantic search rather than simple keyword matching.

## Document Categories

### Technical Documents

1. **test_ai_machine_learning.txt**
   - Topics: Deep learning, neural networks, transformers, backpropagation, CNNs, RNNs, LSTMs
   - Purpose: Test semantic search for technical AI/ML concepts
   - Example queries: "How do neural networks learn?", "What are transformers?", "Explain backpropagation"

2. **test_quantum_physics.txt**
   - Topics: Quantum mechanics, wave-particle duality, uncertainty principle, quantum entanglement, quantum computing
   - Purpose: Test semantic search for complex scientific concepts
   - Example queries: "What is quantum entanglement?", "Explain the uncertainty principle", "How do quantum computers work?"

3. **test_financial_markets.txt**
   - Topics: Stock trading, portfolio management, market analysis, risk management, investment strategies
   - Purpose: Test semantic search for financial and economic concepts
   - Example queries: "Portfolio diversification strategies", "How does stock trading work?", "Risk management in investing"

4. **test_software_engineering.txt**
   - Topics: Design patterns, software architecture, best practices, SOLID principles, microservices
   - Purpose: Test semantic search for software development concepts
   - Example queries: "Design patterns for microservices", "What are SOLID principles?", "Software architecture best practices"

### Academic Documents

5. **test_nutrition_health.txt**
   - Topics: Dietary guidelines, macronutrients, vitamins, minerals, nutrition science
   - Purpose: Test semantic search for health and nutrition information
   - Example queries: "Protein requirements for athletes", "What are macronutrients?", "Dietary guidelines"

6. **test_ancient_history.txt**
   - Topics: Roman Empire, ancient civilizations, historical events, classical history
   - Purpose: Test semantic search for historical information
   - Example queries: "Fall of the Roman Empire", "Ancient Roman history", "Roman civilization"

7. **test_philosophy.txt**
   - Topics: Ethics, epistemology, existentialism, moral philosophy, knowledge theory
   - Purpose: Test semantic search for philosophical concepts
   - Example queries: "Moral philosophy and ethics", "What is epistemology?", "Existentialist philosophy"

8. **test_climate_science.txt**
   - Topics: Global warming, climate change, renewable energy, environmental policy
   - Purpose: Test semantic search for environmental and climate information
   - Example queries: "Climate change causes", "Renewable energy solutions", "Global warming impacts"

### Fun Demo Documents

9. **test_space_exploration.txt**
   - Topics: Mars missions, exoplanets, space travel, space exploration
   - Purpose: Test semantic search for space and astronomy topics (engaging for demos)
   - Example queries: "How to land on Mars?", "What are exoplanets?", "Space exploration missions"

10. **test_video_game_design.txt**
    - Topics: Game mechanics, level design, player psychology, game development
    - Purpose: Test semantic search for gaming and interactive media concepts
    - Example queries: "Game design principles", "Level design techniques", "Player psychology in games"

11. **test_coffee_culture.txt**
    - Topics: Brewing methods, coffee bean origins, espresso techniques, coffee culture
    - Purpose: Test semantic search for culinary and cultural topics
    - Example queries: "Best espresso extraction", "Coffee brewing methods", "Coffee bean origins"

12. **test_urban_legends.txt**
    - Topics: Famous myths, conspiracy theories, folklore, urban legends
    - Purpose: Test semantic search for cultural and social phenomena
    - Example queries: "Famous conspiracy theories", "Urban legends explained", "Modern folklore"

13. **test_cryptocurrency_nfts.txt**
    - Topics: Blockchain technology, digital art, DeFi, cryptocurrency
    - Purpose: Test semantic search for modern technology and finance topics
    - Example queries: "NFT marketplace trends", "How does blockchain work?", "What is DeFi?"

14. **test_extreme_sports.txt**
    - Topics: Rock climbing, BASE jumping, adventure travel, extreme sports
    - Purpose: Test semantic search for adventure and sports topics
    - Example queries: "Rock climbing safety", "BASE jumping techniques", "Adventure travel tips"

15. **test_music_production.txt**
    - Topics: Recording techniques, mixing, sound design, music production
    - Purpose: Test semantic search for creative and technical audio topics
    - Example queries: "Mixing and mastering tips", "Music recording techniques", "Sound design principles"

## Testing Strategy

### Semantic Search Testing

These documents are designed to test semantic search capabilities by:

1. **Concept Matching**: Queries using different terminology than the documents should still find relevant content
   - Example: Query "machine learning algorithms" should find content about "neural networks" and "deep learning"

2. **Contextual Understanding**: Queries about related concepts should retrieve appropriate documents
   - Example: Query "investment strategies" should find the financial markets document

3. **Cross-Domain Queries**: Some queries might relate to multiple documents, testing ranking and relevance
   - Example: "Technology trends" might relate to AI, software engineering, and cryptocurrency documents

### Query Examples by Category

**Technical Queries:**
- "How do neural networks learn?" → test_ai_machine_learning.txt
- "What is quantum entanglement?" → test_quantum_physics.txt
- "Portfolio diversification strategies" → test_financial_markets.txt
- "Design patterns for microservices" → test_software_engineering.txt

**Academic Queries:**
- "Protein requirements for athletes" → test_nutrition_health.txt
- "Fall of the Roman Empire" → test_ancient_history.txt
- "Moral philosophy and ethics" → test_philosophy.txt
- "Climate change solutions" → test_climate_science.txt

**Fun Demo Queries:**
- "How to land on Mars?" → test_space_exploration.txt
- "Game design principles" → test_video_game_design.txt
- "Best espresso extraction" → test_coffee_culture.txt
- "Famous conspiracy theories" → test_urban_legends.txt
- "NFT marketplace trends" → test_cryptocurrency_nfts.txt
- "Rock climbing safety" → test_extreme_sports.txt
- "Mixing and mastering tips" → test_music_production.txt

## Document Characteristics

- **Length**: Each document contains 500-2000 words of substantial content
- **Format**: Plain text (.txt) files for easy indexing
- **Content Quality**: Each document provides comprehensive coverage of its topic
- **Semantic Diversity**: Documents use distinct vocabulary and concepts to test search accuracy
- **Real-world Relevance**: Topics are engaging and demonstrate practical RAG applications

## Usage Instructions

1. **Indexing**: These documents should be indexed using the document indexer configured in `config.yaml`
2. **Testing**: Use semantic search queries to verify that relevant documents are retrieved
3. **Demonstration**: The fun demo documents are particularly useful for showcasing RAG capabilities to audiences
4. **Evaluation**: Compare search results to expected document matches to assess semantic search quality

## Location

All test documents are located in:
```
/Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/
```

This directory is configured in `config.yaml` under `documents.folders` for automatic indexing.

## Notes

- These are test documents created specifically for semantic RAG testing
- Content is designed to be informative but not necessarily authoritative
- Documents cover a wide range of topics to test cross-domain semantic understanding
- The mix of technical, academic, and fun topics makes these suitable for various demo scenarios

