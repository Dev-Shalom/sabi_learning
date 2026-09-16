"""Sabi command line.

    sabi init                 create the schema and seed plans
    sabi status               what is indexed, which embedder, budget state
    sabi ingest [paths]       ingest documents (default: the whole corpus)
    sabi ingest --dry-run     show exactly how documents will be chunked
    sabi reindex              refit the embedder and rebuild every vector
    sabi search "question"    run retrieval and print what came back
    sabi ask "question"       run the full answer path, metered like a user
    sabi plans sync           push limits.yaml into the plans table
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fmt_words(n: int) -> str:
    return f"{n} word{'s' if n != 1 else ''}"


def cmd_init(args: argparse.Namespace) -> int:
    from sabi.schema import bootstrap, describe

    bootstrap()
    info = describe()
    print(f"schema ready on {info['database']}")
    print(f"  tables:     {len(info['tables'])} ({', '.join(info['tables'][:6])}...)")
    print(f"  extensions: {', '.join(info['extensions'])}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from sqlalchemy import func, select

    from sabi.db import session_scope
    from sabi.models import Chunk, Document, GoldenItem, Request, SystemState

    with session_scope() as s:
        docs = s.execute(select(func.count()).select_from(Document)).scalar_one()
        chunks = s.execute(select(func.count()).select_from(Chunk)).scalar_one()
        golden = s.execute(select(func.count()).select_from(GoldenItem)).scalar_one()
        reqs = s.execute(select(func.count()).select_from(Request)).scalar_one()
        emb = s.get(SystemState, "embedder")
        corpus = s.get(SystemState, "corpus")

    print(f"documents      {docs}")
    print(f"chunks         {chunks}")
    print(f"golden items   {golden}")
    print(f"requests       {reqs}")
    print(f"embedder       {emb.value.get('identity') if emb else 'none'}")
    print(f"corpus version {corpus.value.get('version') if corpus else 'unindexed'}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from sabi.corpus.ingest import apply_ingest, plan_ingest

    paths = [Path(p) for p in args.paths] if args.paths else None

    if args.dry_run:
        plan = plan_ingest(paths, prune=args.prune)
        for dp in plan.documents:
            if args.changed_only and dp.action == "unchanged":
                continue
            print(f"\n{'=' * 72}")
            print(f"{dp.doc.doc_id}  [{dp.action}]  {dp.doc.locator}")
            print(f"{dp.doc.title}")
            print(f"source: {dp.doc.source}  attribution: {dp.doc.attribution}")
            print(f"{len(dp.chunks)} chunks, words: {dp.word_counts}")
            for c in dp.chunks:
                flag = " ATOMIC" if c.atomic else ""
                merged = f" merged<-{c.merged_from}" if c.merged_from > 1 else ""
                print(f"\n  --- chunk {c.index} ({_fmt_words(c.word_count)}){flag}{merged}")
                print(f"  heading: {c.heading}")
                body = c.rendered(dp.doc) if args.rendered else c.body
                for line in body.split("\n"):
                    print(f"  | {line}")
            for w in dp.warnings:
                print(f"  WARNING: {w}")

        print(f"\n{'=' * 72}")
        print(
            f"{len(plan.documents)} documents -> {plan.total_chunks} chunks; "
            f"{len(plan.warnings)} warnings; {len(plan.removed_doc_ids)} would be removed"
        )
        for w in plan.warnings:
            print(f"  WARNING: {w}")
        print("\nDry run. Nothing was written.")
        return 0

    result = apply_ingest(paths, prune=args.prune, refit=args.refit or not paths)
    print(json.dumps(result, indent=2))
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    from sabi.corpus.ingest import reindex

    print(json.dumps(reindex(), indent=2))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from sabi.corpus.ingest import corpus_version
    from sabi.db import session_scope
    from sabi.retrieval.pipeline import retrieve

    with session_scope() as s:
        result = retrieve(s, args.query, corpus_version())

    print(f"query       {result.query}")
    print(f"confidence  {result.confidence}  {result.confidence_parts}")
    print(f"latency     {result.retrieval_ms} ms   candidates {result.counts}")
    print()
    for i, sc in enumerate(result.chunks, 1):
        c = sc.candidate
        print(f"{i}. [{c.locator}] {c.heading}  score={sc.score:.4f}  {sc.features}")
        print(f"   ref={c.ref}  {c.provenance.get('attribution')}")
        snippet = " ".join(c.text.split())[:220]
        print(f"   {snippet}...")
        print()
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from sabi.answer.service import answer_question

    result = answer_question(
        question=args.query,
        anon_id=args.user,
        ip="127.0.0.1",
        client="cli",
        plan_hint="internal",
    )
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    from sqlalchemy import func, select

    from sabi.answer.cache import invalidate_all
    from sabi.db import session_scope
    from sabi.models import AnswerCache

    with session_scope() as s:
        if args.action == "clear":
            print(f"cleared {invalidate_all(s)} cache entries")
            return 0
        rows = s.execute(
            select(
                func.count(),
                func.coalesce(func.sum(AnswerCache.hits), 0),
            )
        ).one()
        print(f"entries {rows[0]}   hits served {rows[1]}")
    return 0


def cmd_plans(args: argparse.Namespace) -> int:
    from sabi.schema import sync_plans

    changes = sync_plans()
    print("\n".join(changes) if changes else "plans already in sync")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from sabi.obs.report import render_report

    print(render_report(days=args.days))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from evalharness.runner import main as eval_main

    return eval_main(args)


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("sabi.api.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sabi", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create schema, seed plans").set_defaults(func=cmd_init)
    sub.add_parser("status", help="what is indexed").set_defaults(func=cmd_status)

    ing = sub.add_parser("ingest", help="ingest corpus documents")
    ing.add_argument("paths", nargs="*", help="files or directories (default: corpus/)")
    ing.add_argument("--dry-run", action="store_true", help="show chunking, write nothing")
    ing.add_argument("--rendered", action="store_true", help="show the text as indexed")
    ing.add_argument("--changed-only", action="store_true", help="dry run: skip unchanged")
    ing.add_argument("--prune", action="store_true", help="delete documents no longer on disk")
    ing.add_argument("--refit", action="store_true", help="refit the local embedder")
    ing.set_defaults(func=cmd_ingest)

    sub.add_parser("reindex", help="refit embedder, rebuild all vectors").set_defaults(
        func=cmd_reindex
    )

    se = sub.add_parser("search", help="run retrieval only")
    se.add_argument("query")
    se.set_defaults(func=cmd_search)

    ask = sub.add_parser("ask", help="run the full answer path (metered)")
    ask.add_argument("query")
    ask.add_argument("--user", default="cli-local", help="anonymous id to meter against")
    ask.set_defaults(func=cmd_ask)

    ca = sub.add_parser("cache", help="semantic cache")
    ca.add_argument("action", choices=["stats", "clear"], nargs="?", default="stats")
    ca.set_defaults(func=cmd_cache)

    pl = sub.add_parser("plans", help="plan limits")
    pl.add_argument("action", choices=["sync"])
    pl.set_defaults(func=cmd_plans)

    rep = sub.add_parser("report", help="cost and latency report")
    rep.add_argument("--days", type=int, default=7)
    rep.set_defaults(func=cmd_report)

    ev = sub.add_parser("eval", help="run the evaluation harness")
    ev.add_argument("--suite", default="all")
    ev.add_argument("--limit", type=int, default=0)
    ev.add_argument("--baseline", default="", help="compare against a saved run")
    ev.add_argument("--save", default="", help="write results to this path")
    ev.add_argument("--fail-under", default="", help="gate: metric=value,metric=value")
    ev.add_argument("--json", action="store_true")
    ev.add_argument("--heuristic-judge", action="store_true",
                    help="force the deterministic judge even if a key is set")
    ev.set_defaults(func=cmd_eval)

    sv = sub.add_parser("serve", help="run the web app")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")
    sv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
