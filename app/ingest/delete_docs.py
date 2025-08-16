from dotenv import load_dotenv
load_dotenv()

import argparse
from typing import Iterable, List, Dict
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from app.settings import settings

ENDPOINT = settings.AZ_SEARCH_ENDPOINT
KEY      = settings.AZ_SEARCH_API_KEY
INDEX    = settings.AZ_SEARCH_INDEX

def _client() -> SearchClient:
    return SearchClient(ENDPOINT, INDEX, AzureKeyCredential(KEY))

def _chunk(iterable: Iterable, size: int) -> Iterable[List]:
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf

def delete_by_source(filename: str):
    sc = _client()
    print(f"Deleting docs with source == {filename} ...")
    ids = [d["id"] for d in sc.search(search_text="*", select=["id","source"]) if d.get("source") == filename]
    _delete_ids(sc, ids)

def delete_by_pattern(pattern: str):
    sc = _client()
    print(f"Deleting docs with source LIKE {pattern} ...")
    # Very simple contains-based match; adjust as you like
    ids = [d["id"] for d in sc.search(search_text="*", select=["id","source"]) if pattern.strip("*") in str(d.get("source",""))]
    _delete_ids(sc, ids)

def delete_all():
    sc = _client()
    print("Deleting ALL documents in the index ...")
    ids = [d["id"] for d in sc.search(search_text="*", select=["id"])]
    _delete_ids(sc, ids)

def _delete_ids(sc: SearchClient, ids: List[str]):
    if not ids:
        print("Nothing to delete.")
        return
    BATCH = 1000
    total = len(ids)
    for i, chunk in enumerate(_chunk(ids, BATCH), start=1):
        actions = [{"id": did} for did in chunk]
        res = sc.delete_documents(documents=actions)
        failed = [r for r in res if not r.succeeded]
        print(f"Batch {i}: deleted {len(actions) - len(failed)} / {len(actions)}")
        if failed:
            print(f"  ⚠ {len(failed)} failed (e.g., {failed[0]})")
    print(f"✅ Done. Deleted {total} docs.")

if __name__ == "__main__":
    if not ENDPOINT or not KEY:
        raise SystemExit("Set AZ_SEARCH_ENDPOINT and AZ_SEARCH_API_KEY in .env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--filename", help="delete all chunks from this exact source filename (e.g., about.docx)")
    ap.add_argument("--pattern",  help="delete chunks whose source contains this text (e.g., *.pdf)")
    ap.add_argument("--all",      action="store_true", help="delete ALL docs in the index")
    args = ap.parse_args()

    if args.all:
        delete_all()
    elif args.filename:
        delete_by_source(args.filename)
    elif args.pattern:
        delete_by_pattern(args.pattern)
    else:
        ap.error("Provide --all or --filename or --pattern")
