import json
from pathlib import Path
import numpy as np
import faiss


# ---- IMPORTANT ----
# This embed function MUST match the one used during ingestion,
# otherwise FAISS results will be nonsense.
def embed_texts(texts):
    vecs = []
    for t in texts:
        h = abs(hash(t)) % (10**8)
        rng = np.random.default_rng(h)
        vecs.append(rng.normal(size=(384,)).astype("float32"))
    return np.vstack(vecs)


class DocRetriever:
    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.index = faiss.read_index(str(index_dir / "faiss.index"))
        self.records = json.loads((index_dir / "chunks.json").read_text())

    def search(self, query: str, k: int = 4):
        qvec = embed_texts([query]).astype("float32")
        faiss.normalize_L2(qvec)

        scores, idxs = self.index.search(qvec, k)
        out = []
        for score, i in zip(scores[0].tolist(), idxs[0].tolist()):
            if i < 0:
                continue
            rec = self.records[i]
            out.append({
                "id": rec["id"],          # e.g. "34-86031.pdf::chunk_4"
                "source": rec["source"],  # pdf filename
                "text": rec["text"],
                "score": float(score),
            })
        return out


# Helper to locate repo-root /data/index from backend/
def default_retriever():
    backend_dir = Path(__file__).resolve().parents[1]         # .../backend
    repo_root = backend_dir.parent                            # .../compliance-autofill-engine
    index_dir = repo_root / "data" / "index"
    return DocRetriever(index_dir)