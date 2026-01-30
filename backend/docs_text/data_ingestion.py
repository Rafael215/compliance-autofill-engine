import os, json, re
from pathlib import Path
from pypdf import PdfReader
import numpy as np
import faiss

# Always resolve relative to this file's location
BASE_DIR = Path(__file__).resolve().parent        # .../backend/docs_text
BACKEND_DIR = BASE_DIR.parent                    # .../backend
ROOT_DIR = BACKEND_DIR.parent                    # .../project-root

DOCS_DIR = BACKEND_DIR / "docs"                  # .../backend/docs
OUT_DIR = ROOT_DIR / "data" / "index"            # .../project-root/data/index
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- simple chunking ----
def clean_text(t: str) -> str:
    t = t.replace("\x00", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def chunk_text(text: str, chunk_size=900, overlap=150):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += max(1, chunk_size - overlap)
    return chunks

# ---- TODO: replace this with Bedrock embeddings later ----
# For hackathon MVP, you can start with a fake embedding to prove pipeline,
# or plug in Bedrock Titan Embeddings when ready.
def embed_texts(texts):
    # placeholder deterministic vectors (NOT semantic)
    # Replace with real embeddings ASAP.
    vecs = []
    for t in texts:
        h = abs(hash(t)) % (10**8)
        rng = np.random.default_rng(h)
        vecs.append(rng.normal(size=(384,)).astype("float32"))
    return np.vstack(vecs)

def read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    return clean_text(" ".join(pages))

def main():
    records = []
    all_chunks = []

    for pdf in sorted(DOCS_DIR.glob("*.pdf")):
        text = read_pdf(pdf)
        chunks = chunk_text(text)

        for idx, ch in enumerate(chunks):
            rec = {
                "id": f"{pdf.name}::chunk_{idx}",
                "source": pdf.name,
                "chunk_index": idx,
                "text": ch,
            }
            records.append(rec)
            all_chunks.append(ch)

    print(f"Extracted {len(all_chunks)} chunks from {len(list(DOCS_DIR.glob('*.pdf')))} PDFs")

    # embeddings
    X = embed_texts(all_chunks)
    faiss.normalize_L2(X)

    # FAISS index
    dim = X.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(X)

    faiss.write_index(index, str(OUT_DIR / "faiss.index"))
    (OUT_DIR / "chunks.json").write_text(json.dumps(records, indent=2))

    print("Saved:")
    print(" - data/index/faiss.index")
    print(" - data/index/chunks.json")

if __name__ == "__main__":
    main()