from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import json

from bedrock_client import call_llm

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Go to /docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/health/bedrock")
def health_bedrock():
    out = call_llm('Return only JSON: {"ok":"true","tool":"bedrock"}')
    return {"model_output": out}


# ---------- Autofill MVP ----------

class AutofillRequest(BaseModel):
    advisor_notes: str
    client_profile: Dict[str, Any] = {}
    form_type: str = "generic_disclosure"  # you can add more later


class RiskFlag(BaseModel):
    field: str
    issue: str


class AutofillResponse(BaseModel):
    filled_fields: Dict[str, str]
    missing_fields: List[str]
    risk_flags: List[Dict[str, str]]
    citations: Dict[str, List[str]]


AUTOFILL_SYSTEM_PROMPT = """
You are a compliance assistant for financial advisors.
Your job: turn advisor notes + client profile into a partially completed compliance disclosure.

Rules:
- Output MUST be valid JSON only. No markdown, no explanations outside JSON.
- Use exactly these top-level keys:
  filled_fields (object of string->string),
  missing_fields (array of strings),
  risk_flags (array of objects {field, issue}),
  citations (object of string->array of strings)
- Be conservative: if information is not present, add it to missing_fields.
- In citations, use only these sources:
  "advisor_notes" or "client_profile".
"""

@app.post("/autofill")
def autofill(req: AutofillRequest):
    user_prompt = f"""
Advisor notes:
{req.advisor_notes}

Client profile (JSON):
{json.dumps(req.client_profile, indent=2)}

Form type: {req.form_type}

Return JSON with:
- filled_fields: suggested compliant text for relevant fields (short)
- missing_fields: what you still need
- risk_flags: any conflicts (example: conservative risk tolerance + aggressive strategy)
- citations: for each filled field, list ["advisor_notes"] and/or ["client_profile"]
"""

    try:
        raw = call_llm(AUTOFILL_SYSTEM_PROMPT + "\n\n" + user_prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    # Try to parse JSON. If the model returns extra text, this will fail (good to catch early).
    try:
        parsed = json.loads(raw)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Model did not return valid JSON. Raw output: {raw}"
        )

    # Light validation of keys
    required = {"filled_fields", "missing_fields", "risk_flags", "citations"}
    if not required.issubset(set(parsed.keys())):
        raise HTTPException(
            status_code=500,
            detail=f"Model JSON missing required keys. Got keys: {list(parsed.keys())}"
        )

    return parsed
