"""
Project-wide settings for the local Wikipedia RAG assistant.
Most values that may need tuning are kept in this file.
"""

import os

# Local storage paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_PERSIST_DIR = os.path.join(DATA_DIR, "chroma")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "wiki_rag.db")

# Ollama models and endpoint
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "llama3.2:3b"
EMBED_MODEL = "nomic-embed-text"

# Chunking parameters
CHUNK_SIZE = 1500         # target characters in one chunk
CHUNK_OVERLAP = 200       # repeated context between neighboring chunks
MAX_ARTICLE_LENGTH = 15000  # article text kept from the intro and early sections

# Retrieval parameters
TOP_K = 5                 # chunks passed to the generator for each query
COLLECTION_NAME = "wiki_chunks"

# Entity lists used during ingestion
PEOPLE = [
    # Required entities from the assignment
    "Albert Einstein",
    "Marie Curie",
    "Leonardo da Vinci",
    "William Shakespeare",
    "Ada Lovelace",
    "Nikola Tesla",
    "Lionel Messi",
    "Cristiano Ronaldo",
    "Taylor Swift",
    "Frida Kahlo",
    # Extra people added to reach 20
    "Cleopatra",
    "Mahatma Gandhi",
    "Nelson Mandela",
    "Wolfgang Amadeus Mozart",
    "Isaac Newton",
    "Charles Darwin",
    "Pablo Picasso",
    "Aristotle",
    "Napoleon Bonaparte",
    "Amelia Earhart",
]

PLACES = [
    # Required places from the assignment
    "Eiffel Tower",
    "Great Wall of China",
    "Taj Mahal",
    "Grand Canyon",
    "Machu Picchu",
    "Colosseum",
    "Hagia Sophia",
    "Statue of Liberty",
    "Pyramids of Giza",
    "Mount Everest",
    # Extra places added to reach 20
    "Stonehenge",
    "Petra",
    "Angkor Wat",
    "Great Barrier Reef",
    "Niagara Falls",
    "Santorini",
    "Galápagos Islands",
    "Chichen Itza",
    "Mount Fuji",
    "Amazon rainforest",
]

# System prompt used for grounded answer generation
SYSTEM_PROMPT = """You are a knowledgeable assistant that answers questions using ONLY the provided context from Wikipedia articles.

Rules:
1. Base your answer strictly on the context provided below.
2. If the context does not contain enough information to answer, say "I don't have enough information to answer that question."
3. Do not make up facts or hallucinate information.
4. When referencing information, mention which entity (person or place) it comes from.
5. Keep answers clear, concise, and well-structured.
6. For comparison questions, organize your answer with clear sections for each entity."""
