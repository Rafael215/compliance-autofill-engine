from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
from bedrock_client import call_llm
import json
import re

app = FastAPI(title="Compliance Autofill Engine", version="0.1.0")


class AutofillRequest(BaseModel):
    advisor_notes: str = Field(..., min_length=5)
    client_profile: Optional[Dict[str, Any]] = None
    form_type: str = Field(..., min_length=3)


class AutofillResponse(BaseModel):
    form_type: str
    autofilled_fields: Dict[str, Any]
    missing_fields: List[str]
    risk_flags: List[str]
    explanations: Dict[str, str]


@app.get("/")
def root():
    return {"status": "ok", "service": "compliance-autofill-engine"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/health/bedrock")
def health_bedrock():
    try:
        out = call_llm("Reply with exactly: BEDROCK_OK")
        return {"status": "ok", "model_reply": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bedrock failed: {e}")


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Claude sometimes returns extra text. This tries:
    1) direct json.loads
    2) extract first {...} block and loads it
    """
    t = text.strip()

    # direct parse
    if t.startswith("{"):
        return json.loads(t)

    # find a JSON object in the output
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if m:
        return json.loads(m.group(0))

    raise ValueError("No JSON object found in model output")


@app.post("/autofill", response_model=AutofillResponse)
def autofill(req: AutofillRequest):
    prompt = f"""
You are a financial compliance assistant.

Return ONLY valid JSON (no markdown, no extra text).
Follow this exact JSON schema:

{{
  "form_type": "{req.form_type}",
  "autofilled_fields": {{
    "client_age": 0,
    "time_horizon_years": 0,
    "risk_tolerance": "",
    "primary_goal": "",
    "recommended_action_summary": "",
    "risk_disclosure_summary": ""
  }},
  "missing_fields": ["..."],
  "risk_flags": ["..."],
  "explanations": {{
    "client_age": "",
    "time_horizon_years": "",
    "risk_tolerance": "",
    "primary_goal": "",
    "recommended_action_summary": "",
    "risk_disclosure_summary": ""
  }}
}}

RULES:
- Use advisor_notes + client_profile when available.
- "missing_fields" should list fields usually required for suitability/compliance that are not present.
- "risk_flags" should identify potential compliance issues (e.g. mismatch between risk tolerance and product).
- Keep explanations short and clear.

INPUT:
advisor_notes: {req.advisor_notes}
client_profile: {req.client_profile}
"""

    try:
        raw = call_llm(prompt)
        data = _extract_json(raw)

        # minimal guardrails so the response always matches schema
        data.setdefault("form_type", req.form_type)
        data.setdefault("autofilled_fields", {})
        data.setdefault("missing_fields", [])
        data.setdefault("risk_flags", [])
        data.setdefault("explanations", {})

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")
