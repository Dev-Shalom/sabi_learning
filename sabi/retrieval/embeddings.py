"""Embedding providers.

Two implementations behind one interface:

* `LocalLSAEmbedder` -- TF-IDF over the corpus reduced by truncated SVD. Pure
  numpy, deterministic, no network, no API key. This is what CI and the eval
  harness run against, which means the evaluation numbers in EVALUATION.md are
  reproducible by anyone who clones the repo with no secrets at all.
* `VoyageEmbedder` -- voyage-3.5-lite over HTTP, the production choice. See
  DECISIONS.md for why Voyage rather than OpenAI.

The trade-off is written down honestly rather than hidden: LSA is fitted on the
corpus, so it is a genuinely semantic method but a weaker one than a trained
embedding model, and it must be refitted when the corpus changes materially.
The production embedder is stateless and has neither property. `sabi reindex`
exists because of this, and the ingest path refuses to run if the stored
embedder identity does not match the configured one.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from sabi.config import settings

TOKEN = re.compile(r"[a-z0-9]+")

# Words that carry no retrieval signal in a maths corpus where every document
# says "the", "of", "a" constantly. Deliberately short: aggressive stopword
# lists remove real signal ("no", "not", "less" all matter here).
STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or that the
    to was were will with this these those there their then than so such but if we you
    your they them he she his her i""".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


class Embedder(ABC):
    """One question or chunk in, one unit-length vector out."""

    name: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (len(texts), dim), rows unit-normalised."""

    @property
    def identity(self) -> str:
        """Stored alongside the vectors; a change here invalidates the index."""
        return f"{self.name}:{self.dim}"

    def embed_one(self, text: str) -> list[float]:
        return [float(x) for x in self.embed([text])[0]]


def _l2_normalise(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class LocalLSAEmbedder(Embedder):
    name = "local-lsa"

    def __init__(self, dim: int | None = None, artifact_path: Path | None = None):
        self.dim = dim or settings().embedding_dim
        self.artifact_path = artifact_path or (settings().artifact_dir / "lsa_model.npz")
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None
        self.components: np.ndarray | None = None  # (k, vocab)
        self.corpus_fingerprint: str = ""

    # -- fitting ---------------------------------------------------------

    def _tfidf_matrix(self, docs: list[list[str]]) -> np.ndarray:
        n = len(docs)
        v = len(self.vocab)
        m = np.zeros((n, v), dtype=np.float32)
        for i, toks in enumerate(docs):
            if not toks:
                continue
            for t in toks:
                j = self.vocab.get(t)
                if j is not None:
                    m[i, j] += 1.0
            row = m[i]
            mx = row.max()
            if mx > 0:
                # Sublinear scaling: a word repeated twelve times in a worked
                # solution is not twelve times as informative.
                np.log1p(row, out=row)
        assert self.idf is not None
        m *= self.idf
        return _l2_normalise(m)

    def fit(self, texts: list[str]) -> None:
        docs = [tokenize(t) for t in texts]
        df: dict[str, int] = {}
        for toks in docs:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1

        # Keep terms appearing in at least one document but not in almost all.
        n = len(docs)
        keep = [t for t, c in sorted(df.items()) if c <= max(2, int(0.85 * n))]
        self.vocab = {t: i for i, t in enumerate(keep)}
        self.idf = np.array(
            [np.log((1 + n) / (1 + df[t])) + 1.0 for t in keep], dtype=np.float32
        )

        m = self._tfidf_matrix(docs)
        k = min(self.dim, min(m.shape) - 1) if min(m.shape) > 1 else 1
        # Full SVD is fine at this corpus size and avoids a scikit-learn
        # dependency for one call.
        _, _, vt = np.linalg.svd(m, full_matrices=False)
        self.components = np.ascontiguousarray(vt[:k], dtype=np.float32)
        self.corpus_fingerprint = hashlib.sha256(
            json.dumps(sorted(keep)).encode()
        ).hexdigest()[:16]

    # -- persistence -----------------------------------------------------

    def save(self) -> Path:
        if self.components is None or self.idf is None:
            raise RuntimeError("embedder has not been fitted")
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            self.artifact_path,
            terms=np.array(list(self.vocab.keys()), dtype=object),
            idf=self.idf,
            components=self.components,
            fingerprint=np.array([self.corpus_fingerprint]),
            dim=np.array([self.dim]),
        )
        return self.artifact_path

    def load(self) -> bool:
        if not self.artifact_path.exists():
            return False
        data = np.load(self.artifact_path, allow_pickle=True)
        terms = [str(t) for t in data["terms"]]
        self.vocab = {t: i for i, t in enumerate(terms)}
        self.idf = data["idf"]
        self.components = data["components"]
        self.corpus_fingerprint = str(data["fingerprint"][0])
        self.dim = int(data["dim"][0])
        return True

    def load_or_raise(self) -> None:
        if not self.load():
            raise RuntimeError(
                f"no embedding model at {self.artifact_path}. Run `sabi ingest` "
                "or `sabi reindex` to build it."
            )

    # -- embedding -------------------------------------------------------

    def embed(self, texts: list[str]) -> np.ndarray:
        if self.components is None or self.idf is None:
            self.load_or_raise()
        assert self.components is not None and self.idf is not None

        v = len(self.vocab)
        raw = np.zeros((len(texts), v), dtype=np.float32)
        for i, text in enumerate(texts):
            for t in tokenize(text):
                j = self.vocab.get(t)
                if j is not None:
                    raw[i, j] += 1.0
            np.log1p(raw[i], out=raw[i])
        raw *= self.idf
        raw = _l2_normalise(raw)

        projected = raw @ self.components.T  # (n, k)
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        out[:, : projected.shape[1]] = projected
        return _l2_normalise(out)

    @property
    def identity(self) -> str:
        return f"{self.name}:{self.dim}:{self.corpus_fingerprint}"


class VoyageEmbedder(Embedder):
    """voyage-3.5-lite. 1024 dimensions by default; 256 is also supported and is
    what we use, because a smaller vector is a smaller index and the retrieval
    difference on a corpus this size is not measurable."""

    name = "voyage-3.5-lite"

    def __init__(self, dim: int | None = None, api_key: str | None = None):
        self.dim = dim or settings().embedding_dim
        self.api_key = api_key or settings().voyage_api_key
        if not self.api_key:
            raise RuntimeError(
                "SABI_VOYAGE_API_KEY is not set but SABI_EMBEDDING_PROVIDER=voyage"
            )

    def embed(self, texts: list[str]) -> np.ndarray:
        import httpx

        out: list[list[float]] = []
        # The API takes batches; 128 keeps a single request comfortably small.
        for i in range(0, len(texts), 128):
            batch = texts[i : i + 128]
            r = httpx.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "input": batch,
                    "model": "voyage-3.5-lite",
                    "output_dimension": self.dim,
                    "input_type": "document",
                },
                timeout=30.0,
            )
            r.raise_for_status()
            payload = r.json()
            out.extend(item["embedding"] for item in payload["data"])
        return _l2_normalise(np.array(out, dtype=np.float32))


_cached: Embedder | None = None


def get_embedder(refresh: bool = False) -> Embedder:
    global _cached
    if _cached is not None and not refresh:
        return _cached
    provider = settings().embedding_provider
    if provider == "local_lsa":
        e: Embedder = LocalLSAEmbedder()
    elif provider == "voyage":
        e = VoyageEmbedder()
    else:
        raise RuntimeError(f"unknown embedding provider {provider!r}")
    _cached = e
    return e


def reset_embedder() -> None:
    global _cached
    _cached = None
