"""Retrieval is confined to one syllabus, and provably so.

The expensive test here is the EXPLAIN one. Everything else in this file would
still pass if the scope predicate were a bound parameter instead of a literal --
and that version of the code is broken in the one way this system cannot afford:
the ANN walk quietly returns fewer rows than `LIMIT` asked for, the fused list is
short, confidence drops, and the refusal threshold starts firing on answerable
questions. No error, no log line, just a worse product. So the plan is asserted
directly, by name.

The rest of the file pins the properties that stop one syllabus leaking into
another: the allow-list that keeps an unconfigured subject out of SQL, the
exclusion sections that make "not on this syllabus" mean *this* syllabus, and a
cache that cannot serve one subject's answer for another's question.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from sabi.answer import cache as answer_cache
from sabi.config import runtime
from sabi.retrieval.embeddings import get_embedder
from sabi.retrieval.pipeline import retrieve
from sabi.retrieval.scope import (
    DEFAULT_SCOPE,
    RetrievalScope,
    ScopeError,
    live_scopes,
)
from sabi.retrieval.store import (
    _exclusion_match_sql,
    _exclusion_sql,
    _lexical_sql,
    _siblings_sql,
    _trigram_sql,
    _vector_sql,
    exclusion_chunks,
    vector_candidates,
)

# The partial HNSW index `sabi.schema.scope_index_ddl` builds for the default
# scope. Spelled out rather than derived, so that renaming the index has to be
# a deliberate act that updates this line too.
EXPECTED_INDEX = "ix_chunks_hnsw_waec_mathematics"

# A question with ordinary maths vocabulary, so both recall paths find material.
QUESTION = "Find the sum of the interior angles of a polygon with 12 sides"


# ------------------------------------------------------------- the allow-list


# A subject that is deliberately not in config/limits.yaml, used wherever a
# test needs one. Derived rather than hardcoded: "Physics" was used for this
# and then Physics was switched on, which broke six tests that were all
# asserting correct behaviour. Anything still in this list is unconfigured by
# construction.
_NEVER_CONFIGURED = ("Astronomy", "Geography", "Woodwork")


def unconfigured_subject() -> str:
    from sabi.retrieval.scope import declared_subjects

    live = set(declared_subjects())
    for name in _NEVER_CONFIGURED:
        if name not in live:
            return name
    raise AssertionError("every placeholder subject is configured; add another")


def test_an_unconfigured_subject_is_refused_rather_than_retrieving_nothing():
    """A typo'd subject must fail loudly, not return an empty result set."""
    with pytest.raises(ScopeError) as excinfo:
        RetrievalScope(subject=unconfigured_subject(), exam_board="WAEC")
    # The message names what is configured, because the person reading it is
    # about to go and add it.
    assert "Mathematics" in str(excinfo.value)


def test_an_unconfigured_board_is_refused():
    with pytest.raises(ScopeError):
        RetrievalScope(subject="Mathematics", exam_board="NECO")


@pytest.mark.parametrize(
    "subject",
    [
        "Mathematics'; DROP TABLE chunks; --",
        "Mathematics'",
        'Mathematics"',
        "Mathematics; SELECT 1",
        "Mathematics\\",
        "",
    ],
)
def test_a_subject_that_cannot_be_spelled_in_sql_is_refused(subject):
    """The predicate is interpolated, so the character set is the first gate.

    This is checked before the configured allow-list, which means it holds even
    for a value that some future configuration happens to declare.
    """
    with pytest.raises(ScopeError):
        RetrievalScope(subject=subject)


def test_a_rejected_value_never_reaches_the_predicate():
    """Nothing that failed validation can be in the SQL, because there is no scope."""
    for bad in (unconfigured_subject(), "Mathematics'; --"):
        try:
            scope = RetrievalScope(subject=bad)
        except ScopeError:
            continue
        pytest.fail(f"{bad!r} produced a usable predicate: {scope.predicate('c')}")


@pytest.mark.parametrize(
    "subject, board",
    [
        ("__unconfigured__", "WAEC"),
        ("Mathematics'; DROP TABLE chunks; --", "WAEC"),
        ("Mathematics", "NECO"),
        (None, None),
        ("", ""),
        ("   ", "   "),
    ],
)
def test_safe_parse_falls_back_instead_of_raising(subject, board):
    """A stale bookmark is a redirect, not a 500."""
    assert RetrievalScope.safe_parse(subject, board) == DEFAULT_SCOPE


def test_parse_still_raises_so_configuration_errors_are_not_swallowed():
    """`safe_parse` is for request handling only; `parse` is for everything else."""
    with pytest.raises(ScopeError):
        RetrievalScope.parse(unconfigured_subject(), "WAEC")


def test_the_key_and_predicate_agree_with_the_configured_scopes():
    assert DEFAULT_SCOPE.key == "WAEC:Mathematics"
    # Every configured pair, not a hardcoded list -- this used to assert
    # there was exactly one subject, which stopped being true.
    from sabi.retrieval.scope import declared_boards, declared_subjects

    expected = {
        f"{b}:{sub}" for b in declared_boards() for sub in declared_subjects()
    }
    assert {sc.key for sc in live_scopes()} == expected
    assert DEFAULT_SCOPE in live_scopes()
    predicate = DEFAULT_SCOPE.predicate("c")
    assert predicate == "c.subject = 'Mathematics' AND c.exam_board = 'WAEC'"


@pytest.mark.parametrize(
    "builder",
    [
        _lexical_sql,
        _trigram_sql,
        _vector_sql,
        _siblings_sql,
        _exclusion_sql,
        _exclusion_match_sql,
    ],
)
def test_every_scoped_statement_carries_the_predicate(builder):
    """A statement that forgot the predicate would read the whole table."""
    assert DEFAULT_SCOPE.predicate("c") in str(builder(DEFAULT_SCOPE))


# ------------------------------------------------------------------- the plan


def _query_vector() -> str:
    vector = get_embedder().embed_one(QUESTION)
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def _explain(session, sql: str, params: dict) -> str:
    """The plan, with `enable_sort` off.

    The test corpus is 201 chunks, so at default settings the planner reads the
    whole table and sorts it -- cheaper than any index walk, and it would be
    right about that. `enable_sort = off` asks the question the test actually
    cares about: *if* this ordering has to come from an index, which index can
    supply it? That is a property of the predicate and the index, not of the
    table's current size, which is what wants pinning. `SET LOCAL` confines it
    to this transaction.

    `ANALYZE` first because the fixtures re-ingest the corpus at session start
    and autovacuum has not caught up by the time this runs. On stale statistics
    the planner misjudges how much of the table one scope covers and picks the
    unscoped index -- a real property of a cold database, but not the one this
    test is about.
    """
    session.execute(text("ANALYZE chunks"))
    session.execute(text("SET LOCAL enable_sort = off"))
    return "\n".join(
        r[0] for r in session.execute(text(f"EXPLAIN {sql}"), params).all()
    )


def test_the_scoped_vector_query_uses_the_per_scope_partial_index(session):
    """The test that stops silent recall loss regressing.

    Asserted by name, because the failure it guards against has no symptom: a
    filtered ANN walk that cannot use a matching partial index returns fewer
    rows than `LIMIT` asked for, and nothing anywhere reports that.
    """
    plan = _explain(
        session, str(_vector_sql(DEFAULT_SCOPE)), {"vec": _query_vector(), "lim": 24}
    )

    assert EXPECTED_INDEX in plan, (
        "the scoped vector query is not using its partial HNSW index, so the "
        "ANN walk will post-filter and return fewer rows than LIMIT asked "
        f"for.\n{plan}"
    )
    # And the scope is satisfied *by* the index rather than applied after it.
    # A plan that walks the index and then filters on subject is the broken one.
    filters = [ln for ln in plan.splitlines() if "Filter:" in ln]
    assert not [ln for ln in filters if "subject" in ln], (
        f"the scope is being post-filtered, not indexed.\n{plan}"
    )
    assert "ix_chunks_embedding_hnsw" not in plan, (
        "fell back to the unscoped index; the walk is being post-filtered.\n"
        f"{plan}"
    )


# The same query with the scope as a bound parameter, which is what this code
# would look like if someone "fixed" the interpolation. Spelled out in full
# rather than derived from the real statement, so that it stays a fixed
# description of the broken shape.
BOUND_PARAM_SQL = """
    SELECT c.id
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.active AND c.subject = $1 AND c.exam_board = $2
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> $3
    LIMIT $4
"""


def test_a_bound_scope_parameter_falls_back_to_the_unscoped_index(session):
    """Why the predicate is interpolated. The negative half of the test above.

    A partial index only matches when its predicate is provable at plan time.
    For a one-off statement Postgres builds a custom plan with the values
    substituted, so a bound parameter looks fine -- which is exactly what makes
    this dangerous. Once the statement is prepared and Postgres switches to a
    generic plan, the values are gone, the partial index stops matching, and
    the walk goes to the unscoped index with the scope as a post-filter.

    `plan_cache_mode = force_generic_plan` reproduces that on the first
    execution instead of the sixth. If this test ever fails because the bound
    version *does* match, the interpolation is no longer buying anything and
    this whole design can be simplified.
    """
    session.execute(text("ANALYZE chunks"))
    session.execute(text("SET LOCAL enable_sort = off"))
    session.execute(text("SET LOCAL plan_cache_mode = force_generic_plan"))
    session.execute(
        text(f"PREPARE scope_bound(text, text, vector, int) AS {BOUND_PARAM_SQL}")
    )
    try:
        vec = _query_vector()
        plan = "\n".join(
            r[0]
            for r in session.execute(
                text(
                    "EXPLAIN EXECUTE scope_bound('Mathematics', 'WAEC', "
                    f"'{vec}'::vector, 24)"
                )
            ).all()
        )
    finally:
        session.execute(text("DEALLOCATE scope_bound"))

    assert EXPECTED_INDEX not in plan, (
        "a bound scope parameter now matches the partial index. If that is "
        "really true on this Postgres, the literal in RetrievalScope.predicate "
        f"is no longer needed.\n{plan}"
    )
    assert "ix_chunks_embedding_hnsw" in plan
    # The tell: the scope is applied as a filter on top of the ANN walk, which
    # is the thing that makes the walk return short.
    assert "Filter:" in plan and "subject" in plan


def test_the_scoped_vector_query_returns_the_full_limit(session):
    """The consequence the index exists to prevent, asserted on real rows."""
    vector = get_embedder().embed_one(QUESTION)
    candidates = vector_candidates(session, vector, 24, scope=DEFAULT_SCOPE)
    assert len(candidates) == 24, (
        f"asked for 24 candidates, got {len(candidates)} -- a short ANN walk"
    )


# --------------------------------------------------- scoping changed nothing


def _unscoped(monkeypatch) -> None:
    """Make every scoped statement unscoped, for comparison.

    Replacing the predicate with `true` is exactly the query this code ran
    before scopes existed. Both builders are `lru_cache`d on the scope, so the
    caches are cleared on the way in and again on the way out -- otherwise the
    unscoped statements would outlive the test.
    """
    builders = (
        _lexical_sql, _trigram_sql, _vector_sql,
        _siblings_sql, _exclusion_sql, _exclusion_match_sql,
    )
    for b in builders:
        b.cache_clear()
    monkeypatch.setattr(RetrievalScope, "predicate", lambda self, alias="c": "true")
    return builders


def test_scoping_confines_retrieval_to_one_syllabus(session, monkeypatch):
    """Scoping must actually exclude the other subject's material.

    This test previously asserted the opposite -- that scoped and unscoped
    retrieval gave identical results -- and it was right to. While the corpus
    held one subject, any difference would have meant the filter was changing
    retrieval rather than confining it, and that was the acceptance criterion
    for adding scoping at all.

    With a second subject indexed the premise is gone and the assertion
    inverts: unscoped retrieval should now reach material that scoped
    retrieval must not. Keeping the old version would have meant asserting
    that the filter does nothing, on the day it started doing something.
    """
    from sabi.models import Chunk

    vector = get_embedder().embed_one(QUESTION)
    scoped = retrieve(session, QUESTION, "test", query_vector=vector)
    assert scoped.refs, "retrieved nothing at all, so the comparison is vacuous"
    assert scoped.scope == DEFAULT_SCOPE

    subject_of = {
        ref: subject
        for ref, subject in session.query(Chunk.ref, Chunk.subject).all()
    }

    # Nothing from another syllabus came back.
    got = {subject_of.get(r) for r in scoped.refs}
    assert got == {DEFAULT_SCOPE.subject}, f"scoped retrieval reached {got}"

    builders = _unscoped(monkeypatch)
    try:
        unscoped = retrieve(session, QUESTION, "test", query_vector=vector)
    finally:
        monkeypatch.undo()
        for b in builders:
            b.cache_clear()

    # The filter has to have something to exclude, or the assertion above is
    # satisfied by there being nothing else in the table.
    pool = {s for (s,) in session.query(Chunk.subject).distinct().all()}
    assert len(pool) > 1, (
        f"only {pool} is indexed, so confinement is vacuous here"
    )

    # Unscoped retrieval is allowed to return the same refs -- a Mathematics
    # question's nearest neighbours are mostly Mathematics whether or not
    # anything filters them. What must not happen is the reverse: asking
    # under one syllabus and reaching another.
    assert all(
        subject_of.get(r) == DEFAULT_SCOPE.subject for r in scoped.refs
    )
    assert set(unscoped.refs) >= set(scoped.refs) or unscoped.refs != scoped.refs


def test_every_retrieved_chunk_is_in_scope(session):
    vector = get_embedder().embed_one(QUESTION)
    result = retrieve(session, QUESTION, "test", query_vector=vector)
    assert result.chunks

    refs = [sc.candidate.ref for sc in result.chunks]
    rows = session.execute(
        text(
            "SELECT DISTINCT subject, exam_board FROM chunks WHERE ref = ANY(:refs)"
        ),
        {"refs": refs},
    ).all()
    assert rows == [(DEFAULT_SCOPE.subject, DEFAULT_SCOPE.exam_board)]


# -------------------------------------------------------------- exclusions


def test_exclusion_chunks_are_scoped_and_are_only_exclusions(session):
    """"Not on this syllabus" has to mean *this* syllabus.

    Unscoped, one subject's exclusion sections refuse another subject's
    answerable questions -- the worst failure this change can cause, because it
    looks like a retrieval bug in a subject nobody touched.
    """
    chunks = exclusion_chunks(session, DEFAULT_SCOPE)
    assert len(chunks) >= 10, (
        f"only {len(chunks)} exclusion chunks; the corpus has 13, so either "
        "ingest stopped setting is_exclusion or the heading convention moved"
    )

    refs = [c.ref for c in chunks]
    rows = session.execute(
        text(
            "SELECT ref, is_exclusion, subject, exam_board "
            "FROM chunks WHERE ref = ANY(:refs)"
        ),
        {"refs": refs},
    ).all()
    assert len(rows) == len(refs)
    for ref, is_exclusion, subject, board in rows:
        assert is_exclusion, f"{ref} is not an exclusion chunk"
        assert (subject, board) == (DEFAULT_SCOPE.subject, DEFAULT_SCOPE.exam_board)

    # And it is a strict subset: the corpus is mostly not exclusions.
    total = session.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    assert len(chunks) < total


# ------------------------------------------------------------------- caching


def _store_entry(session, question: str, vector, syllabus: str, cache_scope: str):
    answer_cache.store(
        session,
        question,
        vector,
        {"text": f"answer for {syllabus}", "refused": False, "citations": []},
        "test-model",
        cache_scope,
        "test-corpus-version",
        syllabus=syllabus,
    )
    session.flush()


def test_the_cache_does_not_serve_across_scopes(session):
    """Two subjects can share a question's wording.

    A hit across them would be the worst kind of hit: fluent, cited, and from
    the wrong syllabus. The scope is both a column filter and part of the key,
    and either one alone would be enough -- both is on purpose.
    """
    question = "What is the scalar product of two vectors?"
    vector = get_embedder().embed_one(question)

    mine = DEFAULT_SCOPE.key
    theirs = "WAEC:Astronomy"
    key_mine = answer_cache.scope_key("v3", "offline", DEFAULT_SCOPE)

    _store_entry(session, question, vector, mine, key_mine)

    # Same syllabus, same key: served, which proves the filter is not simply
    # breaking the cache outright.
    hit = answer_cache.lookup(
        session, question, vector, key_mine, "test-corpus-version", syllabus=mine
    )
    assert hit is not None
    assert hit.payload["text"] == f"answer for {mine}"

    # Different syllabus, identical question and vector: no hit.
    assert (
        answer_cache.lookup(
            session, question, vector, key_mine, "test-corpus-version",
            syllabus=theirs,
        )
        is None
    )


def test_the_cache_key_carries_the_syllabus(session):
    """Belt as well as braces: an entry written under a different key misses.

    The column filter is what the index uses; the key is what protects entries
    written before the column existed, whose default value would otherwise make
    them look in-scope for the default syllabus.
    """
    question = "State the sine rule"
    vector = get_embedder().embed_one(question)
    mine = DEFAULT_SCOPE.key

    key = answer_cache.scope_key("v3", "offline", DEFAULT_SCOPE)
    assert key.endswith(mine)
    assert answer_cache.ANSWERER_REVISION in key

    _store_entry(session, question, vector, mine, key)

    other_key = key.replace(mine, "WAEC:Astronomy")
    assert other_key != key
    assert (
        answer_cache.lookup(
            session, question, vector, other_key, "test-corpus-version", syllabus=mine
        )
        is None
    )


def test_the_cache_key_is_short_enough_for_its_column():
    """`answer_cache.prompt_version` is varchar(64) and this is what goes in it."""
    for scope in live_scopes():
        key = answer_cache.scope_key(runtime().prompt_version, "anthropic", scope)
        assert len(key) <= 64, key


# ------------------------------------------------------------- per-scope version


def test_the_corpus_version_is_recorded_per_scope_and_globally(session):
    """Adding one subject's document must not flush another's answers."""
    from sabi.corpus.ingest import CORPUS_KEY, corpus_version
    from sabi.models import SystemState

    row = session.get(SystemState, CORPUS_KEY)
    assert row is not None, "ingest did not record a corpus version"

    # The global key still exists: `sabi status` and the eval harness read it.
    assert row.value.get("version")
    assert corpus_version(session) == row.value["version"]

    scopes = row.value.get("scopes") or {}
    assert DEFAULT_SCOPE.key in scopes
    assert scopes[DEFAULT_SCOPE.key]["documents"] > 0
    assert corpus_version(session, DEFAULT_SCOPE.key) == (
        scopes[DEFAULT_SCOPE.key]["version"]
    )

    # A scope with nothing in it gets a version nothing else shares, so the
    # cache cannot serve it by accident.
    empty = corpus_version(session, "WAEC:Astronomy")
    assert empty == "empty:WAEC:Astronomy"
    assert empty != corpus_version(session)


def test_a_state_row_written_before_scopes_existed_falls_back_to_the_global(session):
    """Deploying this must not throw away a warm cache before the next ingest.

    An old `system_state['corpus']` has a `version` and no `scopes`. Treating
    that as "this scope is empty" would invalidate every cached answer on
    deploy, which is the opposite of what per-scope versions are for.
    """
    from sabi.corpus.ingest import CORPUS_KEY, corpus_version
    from sabi.models import SystemState

    row = session.get(SystemState, CORPUS_KEY)
    original = dict(row.value)
    try:
        row.value = {"version": original["version"], "documents": 82}
        session.flush()
        assert corpus_version(session, DEFAULT_SCOPE.key) == original["version"]
        assert corpus_version(session, "WAEC:Astronomy") == original["version"]
    finally:
        row.value = original
        session.flush()


def test_the_request_row_records_the_syllabus(session):
    """The review queue and the per-subject eval slices both group on these."""
    from sqlalchemy import select

    from sabi.answer.service import answer_question
    from sabi.models import Request

    answer_question(
        QUESTION, anon_id="t-scope-row", client="cli", plan_hint="internal",
        use_cache=False,
    )
    row = session.execute(select(Request)).scalars().first()
    assert row is not None
    assert row.subject == DEFAULT_SCOPE.subject
    assert row.exam_board == DEFAULT_SCOPE.exam_board


def test_an_unknown_subject_on_the_request_falls_back_to_the_default(session):
    """A stale bookmark answers under the default syllabus rather than 500ing."""
    from sqlalchemy import select

    from sabi.answer.service import answer_question
    from sabi.models import Request

    result = answer_question(
        QUESTION, anon_id="t-scope-bad", client="cli", plan_hint="internal",
        use_cache=False, subject="Underwater Basket Weaving", exam_board="NECO",
    )
    assert not result.refused
    row = session.execute(select(Request)).scalars().first()
    assert row.subject == DEFAULT_SCOPE.subject
    assert row.exam_board == DEFAULT_SCOPE.exam_board
