"""
Streamlit interface for the local Wikipedia RAG assistant.

Start it with:
    streamlit run app.py
"""

import time
import uuid
import streamlit as st
from core.vector_store import VectorStore
from core.retriever import retrieve
from core.generator import generate_stream
from core.database import (
    init_db,
    get_ingestion_stats,
    save_message,
    get_chat_history,
    clear_chat_history,
)

# Page setup
st.set_page_config(
    page_title="WikiRAG — Local Wikipedia Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Styling used by the Streamlit page
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');

    /* Base font */
    .stApp {
        font-family: 'DM Sans', sans-serif;
    }

    /* Top banner */
    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 2rem 2.5rem;
        border-radius: 20px;
        margin-bottom: 1.75rem;
        color: white;
        text-align: center;
        border: 1px solid rgba(56, 189, 248, 0.2);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -0.03em;
    }
    .main-header p {
        margin: 0.6rem 0 0 0;
        opacity: 0.75;
        font-size: 0.95rem;
        font-weight: 300;
    }
    .main-header .badge {
        display: inline-block;
        background: rgba(56, 189, 248, 0.15);
        border: 1px solid rgba(56, 189, 248, 0.4);
        color: #38bdf8;
        padding: 0.2rem 0.75rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
    }

    /* Sidebar cards */
    .stat-card {
        background: linear-gradient(145deg, #0d1117 0%, #161b22 100%);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.6rem;
        color: #c9d1d9;
        transition: border-color 0.2s;
    }
    .stat-card:hover {
        border-color: rgba(56, 189, 248, 0.45);
    }
    .stat-card .stat-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6e7681;
        margin-bottom: 0.3rem;
    }
    .stat-card .stat-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #38bdf8;
    }

    /* Retrieved source cards */
    .source-chunk {
        background: #0d1117;
        border: 1px solid #21262d;
        border-left: 3px solid #38bdf8;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 10px 10px 0;
        font-size: 0.84rem;
        line-height: 1.6;
        color: #c9d1d9;
    }
    .source-entity {
        font-weight: 600;
        color: #38bdf8;
        font-size: 0.78rem;
        margin-bottom: 0.4rem;
    }

    /* Response time label */
    .latency-badge {
        display: inline-block;
        background: rgba(56, 189, 248, 0.08);
        border: 1px solid rgba(56, 189, 248, 0.25);
        color: #38bdf8;
        padding: 0.18rem 0.65rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-top: 0.35rem;
    }

    /* Hide Streamlit chrome for a cleaner page */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize storage and shared resources
init_db()


@st.cache_resource
def get_vector_store():
    """Keep one VectorStore instance between Streamlit reruns."""
    return VectorStore()


store = get_vector_store()

# Session state defaults
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    # Restore this session's saved messages.
    st.session_state.messages = get_chat_history(st.session_state.session_id)
    if not st.session_state.messages:
        st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.markdown("## 🛰️ System Status")

    stats = get_ingestion_stats()
    vs_stats = store.get_stats()

    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">Total Entities</div>
        <div class="stat-value">{stats['total_entities']}</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">People</div>
            <div class="stat-value">{stats['people']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Places</div>
            <div class="stat-value">{stats['places']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">Vector DB Chunks</div>
        <div class="stat-value">{vs_stats['total_chunks']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("## ⚙️ Model Config")
    st.markdown(f"""
    - **LLM**: `llama3.2:3b`
    - **Embeddings**: `nomic-embed-text`
    - **Vector DB**: NumPy + JSON
    - **Top-K**: 5
    """)

    st.divider()

    # Chat controls
    if st.button("🗑️ Clear Chat", use_container_width=True):
        clear_chat_history(st.session_state.session_id)
        st.session_state.messages = []
        st.rerun()

    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.markdown("### 💬 Try Asking")
    examples = [
        "Who was Albert Einstein?",
        "What did Marie Curie discover?",
        "Where is the Eiffel Tower?",
        "Compare Messi and Ronaldo",
        "Which famous place is in Turkey?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state.pending_question = ex
            st.rerun()

# Header
st.markdown("""
<div class="main-header">
    <div class="badge">Local AI · No Cloud · Privacy First</div>
    <h1>🔍 WikiRAG Assistant</h1>
    <p>Explore knowledge about famous people and places — fully offline, powered by local LLM</p>
</div>
""", unsafe_allow_html=True)

# Warn when the knowledge base has not been built yet.
if stats["total_entities"] == 0:
    st.warning(
        "No data loaded yet — run `python ingest.py` to populate the knowledge base with Wikipedia articles."
    )

# Existing chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show saved source snippets when they exist.
        if msg.get("metadata") and msg["metadata"].get("sources"):
            with st.expander("📄 View Sources", expanded=False):
                for src in msg["metadata"]["sources"]:
                    entity = src.get("entity_name", "Unknown")
                    entity_type = src.get("type", "")
                    text_preview = src.get("text", "")[:200] + "..."
                    st.markdown(
                        f'<div class="source-chunk">'
                        f'<div class="source-entity">📌 {entity} ({entity_type})</div>'
                        f'{text_preview}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # Show the stored latency for older assistant messages.
            if msg["metadata"].get("latency"):
                st.markdown(
                    f'<span class="latency-badge">⚡ {msg["metadata"]["latency"]:.1f}s</span>',
                    unsafe_allow_html=True,
                )

# Sidebar example clicks are handled as pending questions.
pending = st.session_state.pop("pending_question", None)

# Chat input
user_input = st.chat_input("Ask about famous people or places...")

# Prefer a clicked example unless the user typed a new prompt.
query = pending or user_input

if query:
    # Add and persist the user's message.
    st.session_state.messages.append({"role": "user", "content": query})
    save_message(st.session_state.session_id, "user", query)

    with st.chat_message("user"):
        st.markdown(query)

    # Retrieve context and stream the answer.
    with st.chat_message("assistant"):
        start_time = time.time()

        # Search the local knowledge base.
        with st.spinner("Searching knowledge base..."):
            retrieval_result = retrieve(query, store)
            chunks = retrieval_result["chunks"]
            query_type = retrieval_result["query_type"]

        # Display a small retrieval summary above the answer.
        st.caption(f"Classified as **{query_type}** · **{len(chunks)}** chunks retrieved")

        # Send previous turns as short context, excluding the current question.
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]  # current question is added separately
        ]

        # Stream tokens into one placeholder.
        response_placeholder = st.empty()
        full_response = ""

        for token in generate_stream(query, chunks, history):
            full_response += token
            response_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)

        latency = time.time() - start_time

        # Collect and display retrieved chunks.
        sources_meta = []
        if chunks:
            with st.expander("📄 View Sources", expanded=False):
                for chunk in chunks:
                    meta = chunk.get("metadata", {})
                    entity = meta.get("entity_name", "Unknown")
                    entity_type = meta.get("type", "")
                    text_preview = chunk["text"][:200] + "..."
                    distance = chunk.get("distance", 0)
                    st.markdown(
                        f'<div class="source-chunk">'
                        f'<div class="source-entity">📌 {entity} ({entity_type}) — similarity: {1 - distance:.3f}</div>'
                        f'{text_preview}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    sources_meta.append({
                        "entity_name": entity,
                        "type": entity_type,
                        "text": chunk["text"][:200],
                    })

        # Display total response time.
        st.markdown(
            f'<span class="latency-badge">⚡ {latency:.1f}s</span>',
            unsafe_allow_html=True,
        )

    # Persist the assistant reply and its metadata.
    msg_meta = {"sources": sources_meta, "latency": latency, "query_type": query_type}
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "metadata": msg_meta,
    })
    save_message(st.session_state.session_id, "assistant", full_response, msg_meta)
