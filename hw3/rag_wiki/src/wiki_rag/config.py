"""Project defaults and entity lists for the local Wikipedia RAG system."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CHROMA_DIR = DATA_DIR / "chroma"

DEFAULT_COLLECTION = "wikipedia_rag"
DEFAULT_LLM_MODEL = "llama3.2:3b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

CHUNK_WORDS = 220
CHUNK_OVERLAP = 45

PEOPLE = [
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
    "Isaac Newton",
    "Charles Darwin",
    "Mahatma Gandhi",
    "Nelson Mandela",
    "Cleopatra",
    "Wolfgang Amadeus Mozart",
    "Jane Austen",
    "Pablo Picasso",
    "Amelia Earhart",
    "Martin Luther King Jr.",
]

PLACES = [
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
    "Acropolis of Athens",
    "Angkor Wat",
    "Petra",
    "Stonehenge",
    "Sydney Opera House",
    "Sagrada Familia",
    "Niagara Falls",
    "Mount Fuji",
    "Louvre",
    "Buckingham Palace",
]

