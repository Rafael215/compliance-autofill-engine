from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

from bedrock_client import call_llm

app = FastAPI(title="Compliance Autofill Engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    # remove ```json ... ``` or ``` ... ``` fences
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```$", "", s)
    return s.strip()


def _try_json_loads(s: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
        return None
    except Exception:
        return None


def _json_repair_best_effort(s: str) -> str:
    """Best-effort cleanup for common LLM JSON issues (hackathon-safe)."""
    t = (s or "").strip()
    t = _strip_code_fences(t)

    # If there's leading/trailing junk, extract the first JSON object
    if not t.startswith("{"):
        m = _JSON_RE.search(t)
        if m:
            t = m.group(0)

    # remove trailing commas before } or ]
    t = re.sub(r",\s*([}\]])", r"\1", t)

    # normalize smart quotes (rare but happens)
    t = t.replace("“", '"').replace("”", '"').replace("’", "'")

    return t.strip()


def _extract_json(text: str) -> Dict[str, Any]:
    """Robust JSON extraction from a model response.

    Strategy:
    1) Strip code fences and try direct JSON parse
    2) Extract first JSON object and parse
    3) Apply lightweight repair and parse
    """
    raw = (text or "").strip()
    raw = _strip_code_fences(raw)

    # 1) direct parse
    direct = _try_json_loads(raw)
    if direct is not None:
        return direct

    # 2) extract first JSON object and parse
    m = _JSON_RE.search(raw)
    if m:
        extracted = m.group(0)
        extracted_obj = _try_json_loads(extracted)
        if extracted_obj is not None:
            return extracted_obj

    # 3) repair and parse
    repaired = _json_repair_best_effort(raw)
    repaired_obj = _try_json_loads(repaired)
    if repaired_obj is not None:
        return repaired_obj

    raise ValueError(f"Model did not return valid JSON. Raw output: {raw[:2000]}")


def _extract_json_largest_valid_prefix(text: str) -> Optional[Dict[str, Any]]:
    """Try to recover a valid JSON object from a truncated model output.

    We scan for closing braces '}' from the end and attempt to parse the largest
    prefix that forms a valid JSON object.
    """
    raw = (text or "").strip()
    raw = _strip_code_fences(raw)

    # If there's leading/trailing junk, attempt to start at the first '{'
    if not raw.startswith("{"):
        m = _JSON_RE.search(raw)
        if m:
            raw = m.group(0)

    # Fast path
    obj = _try_json_loads(raw)
    if obj is not None:
        return obj

    # Try progressively shorter prefixes ending at a '}'
    for i in range(len(raw) - 1, -1, -1):
        if raw[i] != "}":
            continue
        candidate = raw[: i + 1]
        candidate = _json_repair_best_effort(candidate)
        obj = _try_json_loads(candidate)
        if obj is not None:
            return obj

    return None


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return json.dumps(x, ensure_ascii=False)


# =========================
# Additional Helper
# =========================

def _looks_truncated_json(s: str) -> bool:
    """Heuristic: model started a JSON object but didn't finish it."""
    if not s:
        return False
    t = _strip_code_fences(s).strip()
    return t.startswith("{") and not t.endswith("}")


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
- Never include trailing commas.
- Never include comments.
- Never wrap the JSON in triple backticks.
- Keep outputs SHORT to avoid truncation:
  - explanations: max 1 short sentence per field (<= 120 chars)
  - risk_flags: max 5 items
  - missing_fields: max 10 items
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
        last_raw: str = ""
        data: Dict[str, Any] = {}

        def _reprint_prompt(bad: str) -> str:
            return (
                "You returned output that was invalid or truncated. "
                "Reprint the FULL JSON object only, matching the exact same schema.\n"
                "Requirements:\n"
                "- JSON only (no markdown/backticks)\n"
                "- No trailing commas\n"
                "- Keep explanations <= 160 chars each\n"
                "- citations values must always be JSON arrays (even if empty)\n\n"
                f"PREVIOUS_OUTPUT (for reference):\n{bad}\n"
            )

        # Retry a few times because LLMs can intermittently output invalid/truncated JSON
        for attempt in range(3):
            last_raw = call_llm(prompt)

            # If it looks truncated, immediately ask for a full reprint
            if _looks_truncated_json(last_raw):
                last_raw = call_llm(_reprint_prompt(last_raw))

            # 1) Try normal robust extraction
            try:
                data = _extract_json(last_raw)
                break
            except Exception:
                pass

            # 2) If truncated, try to salvage the largest valid JSON prefix
            recovered = _extract_json_largest_valid_prefix(last_raw)
            if recovered is not None:
                data = recovered
                break

            # 3) Ask the model to FIX/REPRINT its JSON (no new content)
            last_raw = call_llm(_reprint_prompt(last_raw))

            # Try again
            try:
                data = _extract_json(last_raw)
                break
            except Exception:
                recovered = _extract_json_largest_valid_prefix(last_raw)
                if recovered is not None:
                    data = recovered
                    break
                # continue to next attempt
                continue

        if not data:
            raise ValueError(f"Model did not return valid JSON after retries. Raw output: {last_raw[:2000]}")

        # minimal guardrails so the response always matches schema
        data.setdefault("form_type", req.form_type)
        data.setdefault("autofilled_fields", {})
        data.setdefault("missing_fields", [])
        data.setdefault("risk_flags", [])
        data.setdefault("explanations", {})
        data.setdefault("citations", {})

        # ensure citations keys exist for known fields and are always lists
        for key in [
            "client_age",
            "time_horizon_years",
            "risk_tolerance",
            "primary_goal",
            "recommended_action_summary",
            "risk_disclosure_summary",
        ]:
            val = data.get("citations", {}).get(key, [])
            if not isinstance(val, list):
                val = []
            data["citations"][key] = val

        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")


def _extract_pdf_text(upload: UploadFile) -> str:
    data = upload.file.read()
    if not data:
        return ""
    reader = PdfReader(BytesIO(data))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return " ".join(pages).strip()


@app.post("/autofill-from-pdf", response_model=AutofillResponse)
def autofill_from_pdf(
    file: UploadFile = File(...),
    form_type: str = Form(...),
    client_profile: Optional[str] = Form(None),
    advisor_notes: Optional[str] = Form(None),
    use_policy_docs: bool = Form(True),
    top_k_docs: int = Form(4),
):
    if file.content_type not in {"application/pdf"} and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        pdf_text = _extract_pdf_text(file)
        profile: Optional[Dict[str, Any]] = None
        if client_profile:
            profile = json.loads(client_profile)

        combined_notes = "\n\n".join([s for s in [advisor_notes, pdf_text] if s])
        if not combined_notes:
            raise HTTPException(status_code=400, detail="No text found in PDF or notes.")

        req = AutofillRequest(
            advisor_notes=combined_notes,
            client_profile=profile,
            form_type=form_type,
            use_policy_docs=use_policy_docs,
            top_k_docs=top_k_docs,
        )
        return autofill(req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF autofill failed: {e}")
