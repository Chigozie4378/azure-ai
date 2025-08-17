from typing import List, Tuple
from langchain_community.retrievers.azure_ai_search import AzureAISearchRetriever
from langchain.schema import Document
from openai import OpenAI
from app.settings import settings

# --- Guardrail thresholds ---
MIN_DOCS = 1          # refuse if fewer than this many chunks retrieved
MIN_SCORE = 0.35      # refuse if top score lower than this (if scores exist)
_REFUSAL = "NOCONTEXT"

class NoContextError(Exception):
    """Raised when retrieval returns insufficient/low-confidence context OR model refuses."""
    pass

class MissingCitationsError(Exception):
    """Raised when the LLM answer does not include required citations."""
    pass

def _retriever() -> AzureAISearchRetriever:
    service_name = settings.AZ_SEARCH_ENDPOINT.replace("https://", "").split(".")[0]
    return AzureAISearchRetriever(
        api_key=settings.AZ_SEARCH_API_KEY,
        service_name=service_name,
        index_name=settings.AZ_SEARCH_INDEX,
        api_version="2023-11-01",
    )

def _extract_sources(docs: List[Document]) -> List[str]:
    out = []
    for d in docs:
        meta = getattr(d, "metadata", {}) or {}
        src = meta.get("source") or getattr(d, "id", None) or "unknown"
        src = src.split("/")[-1].split("\\")[-1]
        if src not in out:
            out.append(src)
    return out

def _best_score(docs: List[Document]) -> float:
    # Azure Search often returns '@search.score' (or 'score' depending on client)
    try:
        meta = getattr(docs[0], "metadata", {}) or {}
        return float(meta.get("@search.score", meta.get("score", 1.0)))
    except Exception:
        return 1.0

def _make_citation_suffix(sources: List[str]) -> str:
    if not sources:
        return ""
    tags = " ".join(f"[source:{s}]" for s in sources)
    return f"\n\nCitations: {tags}"

def answer_query(q: str) -> Tuple[str, List[str]]:
    retriever = _retriever()
    docs: List[Document] = retriever.invoke(q)

    # --- Guardrail 1: refuse if retrieval is weak/empty ---
    if not docs or len(docs) < MIN_DOCS:
        raise NoContextError("No relevant context found for this query.")
    if _best_score(docs) < MIN_SCORE:
        raise NoContextError("Retrieved context confidence too low.")

    # Build context + sources
    top_docs = docs[:6]
    context = "\n\n".join(d.page_content for d in top_docs)
    sources = _extract_sources(top_docs)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    system_msg = (
        "You are a careful assistant for a Retrieval-Augmented Generation (RAG) API. "
        "Answer ONLY using the provided context. "
        f"If the answer is not in the context, reply exactly: {_REFUSAL}. "
        "Always include inline citations of the form [source:<filename>] at the end of your answer "
        "using the provided sources list."
    )
    user_prompt = (
        f"Question: {q}\n\n"
        f"Context:\n{context}\n\n"
        f"Available sources (filenames for citation): {', '.join(sources)}\n\n"
        "Answer (remember to include [source:<filename>] citations):"
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,  # deterministic for evaluation
    )
    answer = resp.choices[0].message.content.strip()

    # If the model refused, surface as NoContextError to the API
    if answer.upper().startswith(_REFUSAL):
        raise NoContextError("Model refused due to missing context.")

    # --- Guardrail 2: enforce citations in output ---
    has_citation = any(f"[source:{s}]" in answer for s in sources)
    if not has_citation:
        # Append minimal citation block once
        answer = answer + _make_citation_suffix(sources)
        if "[source:" not in answer:
            raise MissingCitationsError("Answer missing citations.")

    return answer, sources
