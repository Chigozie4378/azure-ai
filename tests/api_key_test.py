import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
c = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
try:
    models = c.models.list()
    print("Works! Found", len(models.data), "models.")
except Exception as e:
    print("Failed:", e)
