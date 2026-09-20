"""Peak memory and wall time for the two local-embedder fit modes.

    ./.venv/Scripts/python.exe tools/embedder_bench.py
    ./.venv/Scripts/python.exe tools/embedder_bench.py --sizes 200,2000,8000,20000

Not part of the test suite: it is slow, it allocates on purpose, and at the
largest size the dense mode is expected to be the thing that hurts. It exists so
that "the dense path does not survive a bigger corpus" is a number rather than
an assertion.

The corpora are synthetic but shaped like the real one: a Zipfian term
distribution, a long tail of terms that appear in exactly one document, and
roughly the per-chunk length the chunker produces. Absolute timings are
machine-specific; the ratios are the point.

Peak memory is measured with `tracemalloc`, which does see numpy's allocations.
It does *not* see LAPACK's internal workspace, so the dense figures are floors,
not ceilings -- `np.linalg.svd` on an (n, v) matrix wants several more arrays of
its own on top of what is reported here.
"""

from __future__ import annotations

import argparse
import gc
import time
import tracemalloc
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(REPO_ROOT))

from sabi.retrieval.embeddings import (  # noqa: E402
    LocalLSAEmbedder,
    count_csr,
    tokenize,
)

DEFAULT_SIZES = (200, 2_000, 8_000)


def synthetic_corpus(n_docs: int, seed: int = 20260920) -> list[str]:
    """A corpus with a realistic vocabulary shape for `n_docs` chunks.

    Vocabulary grows sub-linearly with the corpus (Heaps' law), terms are drawn
    Zipfian so a few are near-universal and most are rare, and every document
    additionally gets a handful of unique tokens -- the typos, one-off numerals
    and question-specific names that `min_df` exists to remove.
    """
    rng = np.random.default_rng(seed)
    shared_terms = max(400, int(38 * n_docs**0.72))
    vocab = [f"t{i:06d}" for i in range(shared_terms)]
    weights = 1.0 / np.arange(1, shared_terms + 1) ** 1.05
    weights /= weights.sum()

    docs: list[str] = []
    for d in range(n_docs):
        length = int(rng.integers(90, 240))
        picks = rng.choice(shared_terms, size=length, p=weights)
        words = [vocab[int(i)] for i in picks]
        words += [f"u{d:06d}x{j}" for j in range(int(rng.integers(3, 9)))]
        rng.shuffle(words)
        docs.append(" ".join(words))
    return docs


def measure(fn):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = fn()
        error = ""
    except MemoryError as exc:  # the whole point of the exercise
        result, error = None, f"MemoryError: {exc}"
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()
    return result, elapsed, peak, error


def run(sizes: tuple[int, ...], dim: int, skip_dense_over: int) -> None:
    rows = []
    for n in sizes:
        texts = synthetic_corpus(n)

        results: dict[str, tuple[float, int, str, int, int]] = {}
        for mode in ("full_svd", "randomised"):
            if mode == "full_svd" and skip_dense_over and n > skip_dense_over:
                results[mode] = (float("nan"), 0, "skipped (--skip-dense-over)", 0, 0)
                continue
            emb = LocalLSAEmbedder(dim=dim, fit_mode=mode)
            _, elapsed, peak, error = measure(lambda e=emb: e.fit(texts))
            vocab = len(emb.vocab)
            results[mode] = (elapsed, peak, error, vocab, emb.rank)
            del emb

        # What the old path would have had to hold, ignoring LAPACK workspace:
        # the dense TF-IDF matrix plus the copy `_l2_normalise` returns.
        full_vocab = results["full_svd"][3] or results["randomised"][3]
        dense_bytes = 4 * n * full_vocab
        rows.append((n, full_vocab, dense_bytes, results))

    print()
    print(f"dim={dim}   peak memory is tracemalloc, LAPACK workspace not included")
    print()
    head = (
        f"{'chunks':>8} {'vocab':>8} {'mode':>11} {'rank':>6} "
        f"{'wall s':>9} {'peak MB':>10} {'dense MB*':>11}  notes"
    )
    print(head)
    print("-" * len(head))
    for n, full_vocab, dense_bytes, results in rows:
        for mode in ("full_svd", "randomised"):
            elapsed, peak, error, vocab, rank = results[mode]
            wall = "     --  " if error else f"{elapsed:9.2f}"
            mem = "       -- " if error else f"{peak / 1e6:10.1f}"
            note = error or ""
            if mode == "randomised" and not error:
                note = f"vocab {vocab} after min_df/max_features"
            print(
                f"{n:>8} {full_vocab:>8} {mode:>11} {rank if rank else '--':>6} "
                f"{wall} {mem} {2 * dense_bytes / 1e6:>11.1f}  {note}"
            )
        print()
    print(
        "* dense MB is the two (n, vocab) float32 arrays the old path allocated "
        "back to back\n"
        "  (the TF-IDF matrix and the copy _l2_normalise returns), before the "
        "SVD is even called."
    )


def embed_bench(n: int, dim: int) -> None:
    """The other half: `embed()` over a whole corpus, which ingest does once."""
    texts = synthetic_corpus(n)
    emb = LocalLSAEmbedder(dim=dim, fit_mode="randomised")
    emb.fit(texts)
    _, elapsed, peak, error = measure(lambda: emb.embed(texts))
    vocab = len(emb.vocab)
    print()
    print(
        f"embed({n} texts) with vocab {vocab}: {elapsed:.2f}s, peak "
        f"{peak / 1e6:.1f} MB{'  ' + error if error else ''}"
    )
    print(
        f"  the old embed() allocated a single dense ({n}, {vocab}) array = "
        f"{4 * n * vocab / 1e6:.1f} MB, plus the normalised copy"
    )
    csr = count_csr([tokenize(t) for t in texts], emb.vocab)
    print(
        f"  the CSR form of the same matrix is {csr.nbytes / 1e6:.1f} MB "
        f"({csr.nnz} non-zeros, {100 * csr.nnz / (n * vocab):.2f}% dense)"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    p.add_argument("--dim", type=int, default=256)
    p.add_argument(
        "--skip-dense-over",
        type=int,
        default=0,
        help="do not run full_svd above this many chunks (it may not fit)",
    )
    args = p.parse_args()
    sizes = tuple(int(s) for s in args.sizes.split(",") if s.strip())
    run(sizes, args.dim, args.skip_dense_over)
    embed_bench(max(sizes), args.dim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
