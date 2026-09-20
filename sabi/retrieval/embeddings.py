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

Fitting has two modes, chosen by `SABI_EMBEDDING_FIT`:

* `full_svd` (the default) -- the historic path. Materialises a dense
  `(n_chunks, vocab)` TF-IDF matrix and calls `np.linalg.svd` on it. Correct,
  but the dense array is O(n*v) and the full SVD is O(n*v*min(n,v)): at ~8,000
  chunks and ~40,000 terms that is a 1.28 GB array and ~10^12 flops, which will
  MemoryError on a small cloud machine. It stays the default because
  `config/limits.yaml`'s refusal/exclusion/cache thresholds and the committed
  eval baseline were tuned against the vectors it produces, and swapping the
  embedder changes every one of them. That switch happens deliberately, with a
  threshold re-sweep, not as a side effect of this module changing.
* `randomised` -- sparse CSR TF-IDF plus a seeded randomised (Halko) SVD. Peak
  memory is O(nnz), the flop count is O(nnz*k), and because the random
  projection is seeded from the corpus fingerprint the fit is reproducible from
  a clean clone on any machine rather than depending on whichever LAPACK the
  host happens to ship.

The sparse matrix type is hand-rolled rather than scipy's. This project has a
deliberate minimal-dependency habit and one matrix format does not justify
pulling in scipy, its BLAS stack and its wheel-size, for a container that
otherwise needs numpy alone.
"""

from __future__ import annotations

import hashlib
import json
import re
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
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

FIT_MODES = ("full_svd", "randomised")

# `embed()` builds its TF-IDF rows a block at a time so that a caller handing
# over the whole corpus at once -- which `sabi.corpus.ingest` does -- never
# holds more than one block's worth of intermediates. 512 rows of CSR is tens
# of kilobytes at any realistic vocabulary size.
EMBED_BLOCK = 512

# Above this, the dense `full_svd` path is about to ask the allocator for an
# amount of memory that a 1 vCPU / 2 GB box does not have. Warn rather than
# fail: the mode is the default for a reason, and the operator deserves to be
# told which knob fixes it before the MemoryError arrives.
DENSE_WARN_BYTES = 512 * 1024 * 1024


def tokenize(text: str) -> list[str]:
    """Content terms.

    Single characters are kept. In ordinary prose they are noise, but this
    corpus is mathematics: `x`, `y`, `n`, `r` and `d` are the subject matter.
    Dropping them made "reflect in the line y = x" and "reflect in the line
    y = -x" identical to the retriever, which is how a golden item asking for
    one got an answer about the other.
    """
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


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


# ---------------------------------------------------------------------------
# A minimal CSR matrix
# ---------------------------------------------------------------------------


class CSR:
    """Compressed sparse row, the three-array form, numpy only.

    `indptr[i]:indptr[i + 1]` slices `indices` and `data` for row `i`. Column
    indices within a row are ascending and unique, which is what makes the
    scatter in `rdot` safe without `np.add.at`.

    Storage is 8 bytes per non-zero (int32 column + float32 value) against
    4 * n * vocab for the dense form. On the corpus this module is being sized
    for -- ~8,000 chunks, ~20,000 terms after the vocabulary cap, ~90 distinct
    terms per chunk -- that is about 6 MB instead of 640 MB.
    """

    __slots__ = ("indptr", "indices", "data", "shape")

    def __init__(
        self,
        indptr: np.ndarray,
        indices: np.ndarray,
        data: np.ndarray,
        shape: tuple[int, int],
    ) -> None:
        self.indptr = indptr
        self.indices = indices
        self.data = data
        self.shape = shape

    @property
    def nnz(self) -> int:
        return int(self.data.size)

    @property
    def nbytes(self) -> int:
        return int(self.indptr.nbytes + self.indices.nbytes + self.data.nbytes)

    def to_dense(self) -> np.ndarray:
        """The dense equivalent. Only the legacy `full_svd` path calls this."""
        n, v = self.shape
        out = np.zeros((n, v), dtype=np.float32)
        for i in range(n):
            s, e = int(self.indptr[i]), int(self.indptr[i + 1])
            if e > s:
                out[i, self.indices[s:e]] = self.data[s:e]
        return out

    def normalise_rows(self) -> None:
        """L2-normalise each row in place. A zero row is left alone."""
        for i in range(self.shape[0]):
            s, e = int(self.indptr[i]), int(self.indptr[i + 1])
            if e <= s:
                continue
            seg = self.data[s:e]
            norm = float(np.linalg.norm(seg))
            if norm > 0.0:
                seg /= np.float32(norm)

    def dot(self, b: np.ndarray) -> np.ndarray:
        """M @ b for a dense `b` of shape (vocab, c). Returns (n, c)."""
        n = self.shape[0]
        out = np.zeros((n, b.shape[1]), dtype=np.float32)
        for i in range(n):
            s, e = int(self.indptr[i]), int(self.indptr[i + 1])
            if e > s:
                out[i] = self.data[s:e] @ b[self.indices[s:e]]
        return out

    def rdot(self, a: np.ndarray) -> np.ndarray:
        """M.T @ a for a dense `a` of shape (n, c). Returns (vocab, c)."""
        out = np.zeros((self.shape[1], a.shape[1]), dtype=np.float32)
        for i in range(self.shape[0]):
            s, e = int(self.indptr[i]), int(self.indptr[i + 1])
            if e > s:
                out[self.indices[s:e]] += self.data[s:e, None] * a[i]
        return out

    def project(self, components: np.ndarray) -> np.ndarray:
        """M @ components.T for `components` of shape (k, vocab). Returns (n, k).

        Kept separate from `dot` so that the (k, vocab) orientation the model is
        stored in never has to be transposed into a second (vocab, k) array --
        at 40,000 terms and 256 components that copy alone would be 41 MB, on
        every call.
        """
        n = self.shape[0]
        out = np.zeros((n, components.shape[0]), dtype=np.float32)
        for i in range(n):
            s, e = int(self.indptr[i]), int(self.indptr[i + 1])
            if e > s:
                out[i] = components[:, self.indices[s:e]] @ self.data[s:e]
        return out


def count_csr(doc_tokens: list[list[str]], vocab: dict[str, int]) -> CSR:
    """Term counts for each document, as CSR.

    Counting in a dict and writing once means the value written for a term is
    the exact integer count, which is representable in float32 for any count
    this side of 2^24 -- so this produces bit-for-bit what the old
    `m[i, j] += 1.0` loop produced, without the `(n, vocab)` array.
    """
    v = len(vocab)
    indptr = np.zeros(len(doc_tokens) + 1, dtype=np.int64)
    indices: list[np.ndarray] = []
    data: list[np.ndarray] = []
    total = 0
    for i, toks in enumerate(doc_tokens):
        counts: dict[int, int] = {}
        for t in toks:
            j = vocab.get(t)
            if j is not None:
                counts[j] = counts.get(j, 0) + 1
        if counts:
            cols = np.fromiter(sorted(counts), dtype=np.int32, count=len(counts))
            vals = np.fromiter(
                (counts[int(c)] for c in cols), dtype=np.float32, count=len(counts)
            )
            indices.append(cols)
            data.append(vals)
            total += len(counts)
        indptr[i + 1] = total
    return CSR(
        indptr,
        np.concatenate(indices) if indices else np.zeros(0, dtype=np.int32),
        np.concatenate(data) if data else np.zeros(0, dtype=np.float32),
        (len(doc_tokens), v),
    )


def sparse_tfidf(counts: CSR, idf: np.ndarray) -> CSR:
    """Sublinear TF times IDF, row-normalised, in place on the CSR values."""
    # Sublinear scaling: a word repeated twelve times in a worked solution is
    # not twelve times as informative. log1p(0) is 0, so the zeros the dense
    # path used to run this over contributed nothing and can be skipped.
    np.log1p(counts.data, out=counts.data)
    counts.data *= idf[counts.indices]
    counts.normalise_rows()
    return counts


def dense_tfidf(counts: CSR, idf: np.ndarray) -> np.ndarray:
    """The legacy dense TF-IDF matrix, value-for-value as it always was.

    Kept because `full_svd` is the tuned default and `np.linalg.svd` wants a
    dense array anyway; there is nothing to gain from being clever here, and a
    last-bit difference would move the committed eval baseline.
    """
    n, v = counts.shape
    want = 4 * n * v
    if want > DENSE_WARN_BYTES:
        warnings.warn(
            f"the full_svd fit is about to allocate a dense {n} x {v} TF-IDF "
            f"matrix ({want / 1e9:.2f} GB), and the SVD over it needs several "
            "times that again in LAPACK workspace. Set "
            "SABI_EMBEDDING_FIT=randomised for the sparse, seeded path -- but "
            "note that it changes every vector, so re-sweep the retrieval "
            "thresholds and rebuild the eval baseline at the same time.",
            RuntimeWarning,
            stacklevel=2,
        )
    m = counts.to_dense()
    np.log1p(m, out=m)
    m *= idf
    return _l2_normalise(m)


# ---------------------------------------------------------------------------
# Randomised SVD
# ---------------------------------------------------------------------------


def _deterministic_signs(vt: np.ndarray) -> np.ndarray:
    """Fix the sign of every right singular vector.

    An SVD is only defined up to a per-component sign, and which sign LAPACK
    returns is an implementation detail that differs between builds. Pinning it
    to "the largest-magnitude entry is positive" makes the fitted model the same
    object everywhere, which is the point of the whole randomised path.
    """
    if vt.size == 0:
        return vt
    pivots = np.argmax(np.abs(vt), axis=1)
    signs = np.sign(vt[np.arange(vt.shape[0]), pivots])
    signs[signs == 0] = 1.0
    return vt * signs[:, None].astype(vt.dtype)


def randomised_svd(
    m: CSR,
    k: int,
    seed: int,
    oversample: int = 10,
    power_iterations: int = 2,
) -> np.ndarray:
    """Halko-Martinsson-Tropp. Returns the top-`k` right singular vectors.

    Sketch the row space with a seeded Gaussian, orthonormalise, project, and
    take a dense SVD of the small `(k + p, vocab)` result. The only full-width
    array that ever exists is that projection, which is 21 MB at 20,000 terms
    and 256 components -- against 1.28 GB for the dense TF-IDF matrix the exact
    SVD would need, plus its workspace.

    `power_iterations` sharpens the separation between the kept components and
    the tail; TF-IDF spectra decay slowly, so 0 is visibly worse and 2 is where
    the accuracy stops improving for the cost.
    """
    n, v = m.shape
    ell = int(min(k + oversample, n, v))
    rng = np.random.default_rng(seed)
    omega = rng.standard_normal((v, ell), dtype=np.float32)

    q, _ = np.linalg.qr(m.dot(omega))
    for _ in range(power_iterations):
        # Re-orthonormalising between each half-step is what keeps the sketch
        # from collapsing onto the leading singular vector in float32.
        z, _ = np.linalg.qr(m.rdot(q))
        q, _ = np.linalg.qr(m.dot(z))

    b = m.rdot(q).T  # (ell, vocab)
    _, _, vt = np.linalg.svd(b, full_matrices=False)
    return _deterministic_signs(np.ascontiguousarray(vt[:k], dtype=np.float32))


# ---------------------------------------------------------------------------
# Vocabulary policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FitPolicy:
    """How a fit selects its vocabulary and computes its components."""

    mode: str
    min_df: int
    max_features: int  # 0 means uncapped
    max_df_ratio: float
    oversample: int
    power_iterations: int


# The vocabulary rules are per-mode, not global, and that is deliberate.
#
# `full_svd` keeps min_df=1 and no feature cap because those are the rules the
# committed eval baseline and the thresholds in config/limits.yaml were
# produced under. Tightening them would change every vector, which is exactly
# the change this module is not allowed to make by default.
#
# `randomised` applies the rules that a corpus several times this size actually
# needs:
#   * min_df=2 drops every term that occurs in exactly one document. In a
#     hand-authored maths corpus those are overwhelmingly typos, one-off
#     numerals and question-specific names. They can never link two documents
#     -- a term in one document contributes one rank-1 direction that no query
#     but that document's own text will match -- so they cost vocabulary width
#     and SVD work and return nothing. On this corpus they are already ~55% of
#     the terms, and that fraction grows with corpus size, not shrinks.
#   * max_features=20,000 by descending document frequency bounds the one
#     dimension that is otherwise unbounded. 20,000 terms is comfortably more
#     than the distinct vocabulary of a WAEC Mathematics syllabus plus forty
#     years of past papers; the cap exists so that an accidental ingest of
#     something enormous degrades instead of exhausting the machine.
MODE_DEFAULTS = {
    "full_svd": FitPolicy("full_svd", 1, 0, 0.85, 10, 2),
    "randomised": FitPolicy("randomised", 2, 20_000, 0.85, 10, 2),
}


def fit_policy(mode: str | None = None) -> FitPolicy:
    """Resolve the fit policy: mode defaults, overridden by explicit settings."""
    cfg = settings()
    chosen = mode or cfg.embedding_fit
    if chosen not in MODE_DEFAULTS:
        raise RuntimeError(
            f"unknown embedding fit {chosen!r}; expected one of {', '.join(FIT_MODES)}"
        )
    base = MODE_DEFAULTS[chosen]
    return FitPolicy(
        mode=chosen,
        min_df=base.min_df if cfg.embedding_min_df is None else cfg.embedding_min_df,
        max_features=(
            base.max_features
            if cfg.embedding_max_features is None
            else cfg.embedding_max_features
        ),
        max_df_ratio=base.max_df_ratio,
        oversample=base.oversample,
        power_iterations=base.power_iterations,
    )


def select_vocabulary(df: dict[str, int], n_docs: int, policy: FitPolicy) -> list[str]:
    """The kept terms, in a deterministic order.

    Ordering is by term, and the feature cap ranks by document frequency with
    the term as the tie-break, so two machines that see the same corpus build
    the same vocabulary with the same column indices.
    """
    # Terms in almost every document separate nothing.
    max_df = max(2, int(policy.max_df_ratio * n_docs))
    kept = [t for t, c in df.items() if policy.min_df <= c <= max_df]
    if policy.max_features and len(kept) > policy.max_features:
        kept.sort(key=lambda t: (-df[t], t))
        kept = kept[: policy.max_features]
    kept.sort()
    return kept


class LocalLSAEmbedder(Embedder):
    name = "local-lsa"

    def __init__(
        self,
        dim: int | None = None,
        artifact_path: Path | None = None,
        fit_mode: str | None = None,
    ):
        self.dim = dim or settings().embedding_dim
        self.artifact_path = artifact_path or (settings().artifact_dir / "lsa_model.npz")
        self.policy = fit_policy(fit_mode)
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None
        self.components: np.ndarray | None = None  # (dim, vocab)
        self.corpus_fingerprint: str = ""
        # How many of the `dim` components carry signal. The corpus bounds this:
        # a rank-200 matrix cannot supply 256 directions. The rest are exact
        # zeros, so the vector width is always `dim` and never moves under you.
        self.rank: int = 0

    # -- fitting ---------------------------------------------------------

    def _pad(self, components: np.ndarray) -> np.ndarray:
        """Widen to exactly `dim` rows.

        The old code carried `k = min(dim, min(m.shape) - 1)` components and
        zero-filled the tail of every *vector* instead. That made the effective
        dimensionality a silent function of corpus size: cross 257 chunks and k
        goes from 200 to 256, every vector changes meaning, and nothing says so.
        Padding the model rather than the output moves the width into the
        artifact, where `load()` can check it.
        """
        out = np.zeros((self.dim, components.shape[1]), dtype=np.float32)
        out[: components.shape[0]] = components
        return out

    def fit(self, texts: list[str]) -> None:
        policy = self.policy
        docs = [tokenize(t) for t in texts]
        df: dict[str, int] = {}
        for toks in docs:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1

        n = len(docs)
        keep = select_vocabulary(df, n, policy)
        self.vocab = {t: i for i, t in enumerate(keep)}
        self.idf = np.array(
            [np.log((1 + n) / (1 + df[t])) + 1.0 for t in keep], dtype=np.float32
        )

        # A hash of the vocabulary, which is a pure function of the corpus and
        # the vocabulary rules. It is both the index-invalidation token and the
        # seed for the randomised sketch -- so a clean clone on another machine
        # draws the same Gaussian and fits the same model.
        vocab_digest = hashlib.sha256(json.dumps(sorted(keep)).encode()).hexdigest()

        counts = count_csr(docs, self.vocab)

        if policy.mode == "full_svd":
            m = dense_tfidf(counts, self.idf)
            k = min(self.dim, min(m.shape) - 1) if min(m.shape) > 1 else 1
            _, _, vt = np.linalg.svd(m, full_matrices=False)
            comps = np.ascontiguousarray(vt[:k], dtype=np.float32)
            # Unchanged from before this module grew a second mode, so an
            # existing index is not invalidated by the refactor alone.
            self.corpus_fingerprint = vocab_digest[:16]
        else:
            sparse_tfidf(counts, self.idf)
            k = min(self.dim, min(counts.shape) - 1) if min(counts.shape) > 1 else 1
            comps = randomised_svd(
                counts,
                k,
                seed=int(vocab_digest[:16], 16),
                oversample=policy.oversample,
                power_iterations=policy.power_iterations,
            )
            # The two modes produce incomparable vectors from identical input,
            # so the fingerprint has to separate them. Without this, switching
            # the flag would leave `identity` unchanged and ingest would happily
            # mix old and new vectors in one index.
            self.corpus_fingerprint = hashlib.sha256(
                json.dumps(
                    [
                        vocab_digest,
                        policy.mode,
                        policy.min_df,
                        policy.max_features,
                        policy.oversample,
                        policy.power_iterations,
                        self.dim,
                    ]
                ).encode()
            ).hexdigest()[:16]

        self.rank = int(comps.shape[0])
        self.components = self._pad(comps)

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
            # The component count actually stored. Checked on load: an artifact
            # of the wrong width produces vectors the database column cannot
            # hold and scores that are not comparable with anything.
            k=np.array([self.components.shape[0]]),
            rank=np.array([self.rank]),
            fit_mode=np.array([self.policy.mode]),
        )
        return self.artifact_path

    def load(self) -> bool:
        if not self.artifact_path.exists():
            return False
        data = np.load(self.artifact_path, allow_pickle=True)
        components = data["components"]
        stored_dim = int(data["dim"][0])
        # Artifacts written before `k` existed carry their width in the array.
        k = int(data["k"][0]) if "k" in data.files else int(components.shape[0])

        if k != self.dim or stored_dim != self.dim:
            raise RuntimeError(
                f"embedding model at {self.artifact_path} has {k} components "
                f"(fitted for dim {stored_dim}) but the configured "
                f"SABI_EMBEDDING_DIM is {self.dim}. Vectors of different widths "
                "cannot be compared and will not fit the `vector` column. Run "
                "`sabi reindex` to refit the model and rebuild every vector, or "
                "set SABI_EMBEDDING_DIM back to what the artifact was built for."
            )

        terms = [str(t) for t in data["terms"]]
        self.vocab = {t: i for i, t in enumerate(terms)}
        self.idf = data["idf"]
        self.components = components
        self.corpus_fingerprint = str(data["fingerprint"][0])
        self.rank = int(data["rank"][0]) if "rank" in data.files else k
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

        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        # Block, rather than one `(len(texts), vocab)` array. `sabi ingest`
        # calls this once with every chunk in the corpus, so the un-blocked
        # version scaled its peak memory with the corpus.
        for start in range(0, len(texts), EMBED_BLOCK):
            block = texts[start : start + EMBED_BLOCK]
            rows = sparse_tfidf(
                count_csr([tokenize(t) for t in block], self.vocab), self.idf
            )
            out[start : start + len(block)] = rows.project(self.components)
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


# ---------------------------------------------------------------------------
# Startup guard
# ---------------------------------------------------------------------------

_dim_checked = False


def check_embedding_dim() -> int | None:
    """Fail loudly if SABI_EMBEDDING_DIM disagrees with the live vector column.

    `sabi.models.EMBEDDING_DIM` is read at import time and baked into
    `Vector(N)`. Change the setting against an existing database and nothing
    complains until a query returns "expected 256 dimensions, not 512" from
    somewhere three layers below the thing the operator actually did -- or, for
    a *smaller* configured dim, until retrieval quietly compares vectors that
    were never comparable.

    One catalogue lookup, once per process. Returns the column width, or None
    if there is no database to ask -- absence is not a disagreement, and this
    must not turn a missing Postgres into an embedding error.
    """
    global _dim_checked
    if _dim_checked:
        return None
    _dim_checked = True

    try:
        from sqlalchemy import text

        from sabi.db import engine

        with engine().connect() as c:
            found = c.execute(
                text(
                    """
                    SELECT c.relname, a.atttypmod
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind = 'r'
                      AND c.relname IN ('chunks', 'answer_cache')
                      AND a.attname = 'embedding'
                      AND NOT a.attisdropped
                    """
                )
            ).all()
    except Exception:
        # No database, no schema yet, no permission: none of those are this
        # function's business. The check exists to catch a *mismatch*.
        return None

    configured = settings().embedding_dim
    wrong = [(t, int(mod)) for t, mod in found if int(mod) > 0 and int(mod) != configured]
    if wrong:
        detail = ", ".join(f"{t}.embedding is vector({mod})" for t, mod in wrong)
        raise RuntimeError(
            f"SABI_EMBEDDING_DIM is {configured} but the database says {detail}. "
            "The column width is fixed when the table is created, so the two can "
            "only be reconciled by rebuilding: drop and recreate the vector "
            "columns (`sabi init` on an empty database) and run `sabi reindex`, "
            f"or set SABI_EMBEDDING_DIM back to {wrong[0][1]}."
        )
    return int(found[0][1]) if found else None


def reset_dim_check() -> None:
    """Test hook -- let the guard run again in this process."""
    global _dim_checked
    _dim_checked = False


_cached: Embedder | None = None


def get_embedder(refresh: bool = False) -> Embedder:
    global _cached
    if _cached is not None and not refresh:
        return _cached
    # Cheap, and this is the one place every vector-producing path passes
    # through exactly once per process. The right home is the app's startup
    # hook; this is the right home for the CLI, the eval harness and the tests
    # as well, which is why it lives here.
    check_embedding_dim()
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
