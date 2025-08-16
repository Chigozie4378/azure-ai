from langchain_community.retrievers.azure_ai_search import AzureAISearchRetriever
from openai import OpenAI
from app.settings import settings

def _retriever() -> AzureAISearchRetriever:
    service_name = settings.AZ_SEARCH_ENDPOINT.replace("https://", "").split(".")[0]
    return AzureAISearchRetriever(
        api_key=settings.AZ_SEARCH_API_KEY,
        service_name=service_name,
        index_name=settings.AZ_SEARCH_INDEX,
        api_version="2023-11-01",
    )

def answer_query(q: str):
    retriever = _retriever()
    docs = retriever.invoke(q)  # new API (no deprecation warning)

    # context + sources
    top_docs = docs[:6]
    context = "\n\n".join(d.page_content for d in top_docs) or "No relevant context."
    sources = [
        (getattr(d, "metadata", {}) or {}).get("source")
        or getattr(d, "id", None)
        for d in top_docs
    ]

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    prompt = (
        "Use the context to answer the question. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context}\n\nQuestion: {q}\nAnswer:"
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip(), [s for s in sources if s]
