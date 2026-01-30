from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bedrock_client import call_llm

app = FastAPI(title="Compliance Autofill Engine", version="0.2.0")


# =========================
# Models
# =========================

class AutofillRequest(BaseModel):
    advisor_notes: str = Field(..., min_length=5)
    client_profile: Optional[Dict[str, Any]] = None
    form_type: str = Field(..., min_length=3)

    # retrieval options
    use_policy_docs: bool = True
    top_k_docs: int = 4


class AutofillResponse(BaseModel):
    form_type: str
    autofilled_fields: Dict[str, Any]
    missing_fields: List[str]
    risk_flags: List[str]
    explanations: Dict[str, str]
    # citations[field] = ["source.pdf::chunk_12", ...]
    citations: Dict[str, List[str]]


# =========================
# Basic endpoints
# =========================

@app.get("/")
def root():
    return {"status": "ok", "service": "compliance-autofill-engine", "docs": "/docs"}


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


# =========================
# Helpers
# =========================

_JSON_RE = re.compile(r"\{.*\}", flags=re.DOTALL)


def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction from a model response."""
    t = (text or "").strip()

    # direct parse
    if t.startswith("{"):
        return json.loads(t)

    # find first JSON object
    m = _JSON_RE.search(t)
    if m:
        return json.loads(m.group(0))

    raise ValueError("No JSON object found in model output")


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return json.dumps(x, ensure_ascii=False)


# =========================
# Policy doc retrieval (MVP)
# =========================
#
# You already ingested PDFs into:
#   <repo_root>/data/index/chunks.json
#   <repo_root>/data/index/faiss.index
#
# For hackathon reliability, this server uses a SIMPLE lexical retriever over chunks.json.
# (FAISS embeddings can be plugged in later once you add real embeddings.)
#

REPO_ROOT = Path(__file__).resolve().parents[1]  # .../compliance-autofill-engine
INDEX_DIR = REPO_ROOT / "data" / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

_DOC_CHUNKS: List[Dict[str, Any]] = []


def _load_chunks() -> None:
    global _DOC_CHUNKS
    if not CHUNKS_PATH.exists():
        _DOC_CHUNKS = []
        return
    _DOC_CHUNKS = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


def _tokenize(s: str) -> List[str]:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return [w for w in s.split() if len(w) >= 3]


def retrieve_policy_context(query: str, k: int = 4) -> List[Tuple[str, str]]:
    """Return [(chunk_id, chunk_text), ...] best matching chunks by token overlap."""
    if not _DOC_CHUNKS:
        return []

    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return []

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for rec in _DOC_CHUNKS:
        text = _safe_str(rec.get("text"))
        t_tokens = set(_tokenize(text))
        score = len(q_tokens.intersection(t_tokens))
        if score > 0:
            scored.append((score, rec))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: List[Tuple[str, str]] = []
    for score, rec in scored[: max(1, min(k, 10))]:
        chunk_id = _safe_str(rec.get("id"))
        chunk_text = _safe_str(rec.get("text"))
        results.append((chunk_id, chunk_text))

    return results


@app.post("/docs/reload")
def reload_docs():
    """Reload chunks.json without restarting the server."""
    _load_chunks()
    return {"status": "ok", "chunks_loaded": len(_DOC_CHUNKS), "chunks_path": str(CHUNKS_PATH)}


# Load docs at startup
_load_chunks()


# =========================
# Autofill endpoint
# =========================

@app.post("/autofill", response_model=AutofillResponse)
def autofill(req: AutofillRequest):
    client_profile = req.client_profile or {}

    # Build a retrieval query from the user input
    retrieval_query = f"form_type={req.form_type} advisor_notes={req.advisor_notes} client_profile={json.dumps(client_profile)}"

    retrieved = []
    if req.use_policy_docs:
        retrieved = retrieve_policy_context(retrieval_query, k=req.top_k_docs)

    retrieved_block = "\n\n".join(
        [f"SOURCE_ID: {cid}\nEXCERPT: {ctxt}" for cid, ctxt in retrieved]
    )

    prompt = f"""
You are a financial compliance assistant.

Return ONLY valid JSON (no markdown, no extra text).
Follow this exact JSON schema:

{{
  \"form_type\": \"{req.form_type}\",
  \"autofilled_fields\": {{
    \"client_age\": 0,
    \"time_horizon_years\": 0,
    \"risk_tolerance\": \"\",
    \"primary_goal\": \"\",
    \"recommended_action_summary\": \"\",
    \"risk_disclosure_summary\": \"\"
  }},
  \"missing_fields\": [\"...\"],
  \"risk_flags\": [\"...\"],
  \"explanations\": {{
    \"client_age\": \"\",
    \"time_horizon_years\": \"\",
    \"risk_tolerance\": \"\",
    \"primary_goal\": \"\",
    \"recommended_action_summary\": \"\",
    \"risk_disclosure_summary\": \"\"
  }},
  \"citations\": {{
    \"client_age\": [],
    \"time_horizon_years\": [],
    \"risk_tolerance\": [],
    \"primary_goal\": [],
    \"recommended_action_summary\": [],
    \"risk_disclosure_summary\": []
  }}
}}

RULES:
- Use advisor_notes + client_profile when available.
- You MAY also use the POLICY EXCERPTS below (they come from public SEC/FINRA documents).
- Be conservative: if information is missing, put the field name in missing_fields.
- risk_flags should identify potential compliance issues (e.g. mismatch between risk tolerance and recommendation).
- citations must be a list of strings for each field.
  Allowed citation strings are only:
  - \"advisor_notes\"
  - \"client_profile\"
  - any SOURCE_ID from POLICY EXCERPTS (exactly as shown)
- If you did not use a source for a field, leave its citations list empty.

INPUT:
advisor_notes: {req.advisor_notes}
client_profile: {json.dumps(client_profile, ensure_ascii=False)}

POLICY EXCERPTS:
{retrieved_block if retrieved_block else "(none)"}
""".strip()

    try:
        raw = call_llm(prompt)
        data = _extract_json(raw)

        # minimal guardrails so the response always matches schema
        data.setdefault("form_type", req.form_type)
        data.setdefault("autofilled_fields", {})
        data.setdefault("missing_fields", [])
        data.setdefault("risk_flags", [])
        data.setdefault("explanations", {})
        data.setdefault("citations", {})

        # ensure citations keys exist for known fields
        for key in [
            "client_age",
            "time_horizon_years",
            "risk_tolerance",
            "primary_goal",
            "recommended_action_summary",
            "risk_disclosure_summary",
        ]:
            data["citations"].setdefault(key, [])

        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")