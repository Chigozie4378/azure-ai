# app/main.py
from fastapi import FastAPI, Depends, Form, HTTPException
from app.auth import create_token, verify_token
from app.rag import answer_query
import logging, traceback

app = FastAPI(title="RAG on Azure", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/token")
def login(username: str = Form(...), password: str = Form(...)):
    if not username or not password:
        raise HTTPException(status_code=400, detail="Invalid creds")
    return {"access_token": create_token(username), "token_type": "bearer"}

@app.post("/query")
def query(q: str, user=Depends(verify_token)):
    try:
        answer, sources = answer_query(q)
        return {"user": user, "answer": answer, "sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
