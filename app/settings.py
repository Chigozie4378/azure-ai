# app/settings.py
import os
from dotenv import load_dotenv
load_dotenv()  # <-- add this

class Settings:
    PROJECT_NAME = "rag-azure"
    # Auth
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change")
    JWT_ALG    = os.getenv("JWT_ALG", "HS256")
    # Azure AI Search
    AZ_SEARCH_ENDPOINT = os.getenv("AZ_SEARCH_ENDPOINT")
    AZ_SEARCH_API_KEY  = os.getenv("AZ_SEARCH_API_KEY")
    AZ_SEARCH_INDEX    = os.getenv("AZ_SEARCH_INDEX", "docs-index")
    # LLMs
    AZ_OPENAI_ENDPOINT = os.getenv("AZ_OPENAI_ENDPOINT")
    AZ_OPENAI_API_KEY  = os.getenv("AZ_OPENAI_API_KEY")
    OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")

settings = Settings()

# optional: quick visibility in your terminal
print("[settings] loaded:", {
    "AZ_SEARCH_ENDPOINT": bool(settings.AZ_SEARCH_ENDPOINT),
    "AZ_SEARCH_API_KEY":  bool(settings.AZ_SEARCH_API_KEY),
    "OPENAI_API_KEY":     bool(settings.OPENAI_API_KEY),
})
