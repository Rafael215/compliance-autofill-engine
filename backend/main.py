from fastapi import FastAPI
from bedrock_client import call_llm

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/health/bedrock")
def health_bedrock():
    out = call_llm('Return only JSON: {"ok":"true","tool":"bedrock"}')
    return {"model_output": out}
