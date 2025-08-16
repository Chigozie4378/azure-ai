from dotenv import load_dotenv
load_dotenv()

import os, json, glob, re, base64
from typing import List, Dict

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex

from langchain_openai import OpenAIEmbeddings

from app.settings import settings
from app.ingest.chunkers import chunk_text
from app.ingest.readers import load_text

ENDPOINT = settings.AZ_SEARCH_ENDPOINT
KEY      = settings.AZ_SEARCH_API_KEY
INDEX    = settings.AZ_SEARCH_INDEX


# ---------- Helpers ----------

def log(msg: str) -> None:
    print(msg, flush=True)

# Azure key rules: letters, digits, underscore, dash, equal sign
def make_id(filename: str, idx: int) -> str:
    stem = os.path.basename(filename)
    stem = re.sub(r"[^A-Za-z0-9_\-=]", "-", stem)
    return f"{stem}-{idx}"

def ensure_index() -> None:
    idx_client = SearchIndexClient(ENDPOINT, AzureKeyCredential(KEY))
    try:
        idx_client.get_index(INDEX)
        log(f"Index '{INDEX}' already exists.")
        return
    except Exception:
        pass

    schema_path = os.path.join(os.path.dirname(__file__), "index_schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    schema["name"] = INDEX
    idx_client.create_index(SearchIndex.deserialize(schema))
    log(f"Created index '{INDEX}'.")

def make_embeddings():
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set; add it to .env")
    return OpenAIEmbeddings(model="text-embedding-3-small",
                            api_key=settings.OPENAI_API_KEY)

def build_docs(path_glob: str = "data/*.*") -> List[Dict]:
    embeddings = make_embeddings()
    out: List[Dict] = []
    for path in glob.glob(path_glob):
        text, fname = load_text(path)
        chunks = chunk_text(text)
        log(f"Prepared {len(chunks)} chunks from {fname}")
        for i, ch in enumerate(chunks):
            vec = embeddings.embed_query(ch)
            out.append({
                "id": make_id(fname, i),
                "content": ch,
                "embedding": vec,
                "source": fname,
            })
    return out

def upload_docs(docs: List[Dict]) -> None:
    sc = SearchClient(ENDPOINT, INDEX, AzureKeyCredential(KEY))
    BATCH = 500
    total = len(docs)
    for i in range(0, total, BATCH):
        batch = docs[i:i+BATCH]
        results = sc.merge_or_upload_documents(batch)  # idempotent upsert
        failed = [r for r in results if not r.succeeded]
        if failed:
            log(f"⚠️  {len(failed)} docs failed in batch starting at {i}. Example: {failed[0]}")
        log(f"Uploaded {min(i+BATCH, total)}/{total} documents")


# ---------- Main ----------

if __name__ == "__main__":
    if not ENDPOINT or not KEY:
        raise SystemExit("Set AZ_SEARCH_ENDPOINT and AZ_SEARCH_API_KEY in .env")

    log(f"OPENAI_API_KEY loaded? {bool(settings.OPENAI_API_KEY)}")

    ensure_index()
    # Let you override the glob without editing code:
    pattern = os.environ.get("INGEST_GLOB", "data/*.*")
    docs = build_docs(pattern)

    if docs:
        upload_docs(docs)
        log(f"✅ Done. Uploaded {len(docs)} docs to index '{INDEX}'.")
    else:
        log("No docs prepared. Put files in ./data and try again.")
