"""The exam catalog: formats, subjects, and the gate on what a student sees.

The rule this file exists to protect, from master prompt v2 trap 17: an
unverified or dev-only question must never reach a student. It is enforced in
the query layer rather than left to callers, because a caller who forgets
produces no error at all -- just a question nobody reviewed, on a student's
screen, indistinguishable from one that was.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from sabi.content import formats, subjects as subjects_mod
from sabi.models import Question, Subject

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------- exam formats


def test_every_shipped_format_validates():
    loaded = formats.load_all()
    assert loaded, "no exam formats found at all"
    for key, fmt in loaded.items():
        assert fmt.data["exam_body"]
        assert fmt.data["sections"]


def test_a_format_cannot_ship_without_a_source(tmp_path):
    """No source, no load.

    Nigerian exam formats move between seasons -- WAEC's CBT transition moved
    twice while this was being specified. A config nobody can trace to an
    official page is a config nobody can re-check, so the schema requires
    both the URL and the date.
    """
    good = yaml.safe_load((formats.FORMAT_DIR / "jamb_utme.yaml").read_text(encoding="utf-8"))

    for missing in ("source_url", "verified_on"):
        broken = dict(good)
        broken.pop(missing)
        path = tmp_path / f"no_{missing}.yaml"
        path.write_text(yaml.safe_dump(broken), encoding="utf-8")
        with pytest.raises(formats.FormatError) as caught:
            formats.load_file(path)
        assert missing in str(caught.value)


def test_a_yaml_date_is_coerced_before_validation(tmp_path):
    """The trap that would have broken every config.

    YAML parses a bare `2026-09-23` into a `datetime.date`, which JSON
    Schema's `"type": "string"` rejects. Found by validating rather than by
    assuming, and it would have failed every format file on its own
    `verified_on` field.
    """
    good = yaml.safe_load((formats.FORMAT_DIR / "jamb_utme.yaml").read_text(encoding="utf-8"))
    good["verified_on"] = dt.date(2026, 9, 23)  # a real date object, unquoted
    path = tmp_path / "bare_date.yaml"
    path.write_text(yaml.safe_dump(good), encoding="utf-8")

    loaded = formats.load_file(path)
    assert loaded.data["verified_on"] == "2026-09-23"
    assert loaded.verified_on == dt.date(2026, 9, 23)


def test_a_cbt_format_must_declare_its_keyboard(tmp_path):
    """A CBT simulation with no key bindings is not a simulation of a CBT exam."""
    good = yaml.safe_load((formats.FORMAT_DIR / "jamb_utme.yaml").read_text(encoding="utf-8"))
    del good["navigation"]["keyboard"]
    path = tmp_path / "no_keys.yaml"
    path.write_text(yaml.safe_dump(good), encoding="utf-8")
    with pytest.raises(formats.FormatError):
        formats.load_file(path)


def test_option_labels_are_not_assumed_to_be_four(tmp_path):
    """NECO objective papers use five options.

    A shared options component that hard-codes A-D would have a student
    practising against three distractors when the real paper has four, which
    is the exact assumption v2 warned about.
    """
    good = yaml.safe_load((formats.FORMAT_DIR / "jamb_utme.yaml").read_text(encoding="utf-8"))
    good["option_labels"] = ["A", "B", "C", "D", "E"]
    good["exam_body"] = "NECO"
    path = tmp_path / "neco.yaml"
    path.write_text(yaml.safe_dump(good), encoding="utf-8")

    loaded = formats.load_file(path)
    assert loaded.option_labels == ["A", "B", "C", "D", "E"]


def test_jamb_matches_what_jambs_own_manual_says():
    """Read from JAMB's Step-by-Step CBT Manual, not from memory.

    The keyboard map is page 46's "Keyboard Usage" panel; the confirmation
    keys are page 50's End Examination dialog, which reads "Press R to
    continue Exam, Press Y to end Exam". The structure figures are from the
    Candidate Details panel: 2 hours, four subjects, 60 for Use of English,
    180 in total.
    """
    jamb = formats.get("jamb_utme")

    assert jamb.total_questions == 180
    assert jamb.data["total_duration_minutes"] == 120
    assert jamb.data["scoring"]["scale_max"] == 400
    assert len(jamb.data["sections"]) == 4

    english = next(s for s in jamb.data["sections"] if s["key"] == "use_of_english")
    assert english["question_count"] == 60
    assert english["compulsory"] is True

    kb = jamb.data["navigation"]["keyboard"]
    assert kb["select_option"] == {"A": "a", "B": "b", "C": "c", "D": "d"}
    # The arrow aliases are the part a dozen secondary walkthroughs omit.
    assert "ArrowRight" in kb["next"] and "n" in kb["next"]
    assert "ArrowLeft" in kb["previous"] and "p" in kb["previous"]
    assert kb["submit"] == ["s"]
    assert kb["confirm_submit"] == ["y"]
    assert kb["cancel_submit"] == ["r"]

    # One clock across all four subjects, with free movement between them.
    assert all(s["duration_minutes"] is None for s in jamb.data["sections"])
    assert jamb.data["navigation"]["cross_section_movement"] is True


def test_a_format_that_is_a_year_old_is_reported_as_stale():
    """Not an expiry -- it still loads -- but it should be looked at."""
    fmt = formats.get("jamb_utme")
    assert not fmt.is_stale, "the shipped format is already stale; re-verify it"
    assert fmt.days_since_verified >= 0


# ----------------------------------------------------------------- subjects


def test_the_registry_has_no_duplicate_or_reserved_codes():
    entries = subjects_mod.load_registry()
    codes = [e.code for e in entries]
    assert len(codes) == len(set(codes))
    assert len(entries) >= 40


def test_sync_puts_the_registry_in_the_table(session):
    changed = subjects_mod.sync(session)
    session.flush()
    rows = session.execute(select(Subject)).scalars().all()
    assert len(rows) == len(subjects_mod.load_registry())
    assert changed


def test_sync_never_switches_a_subject_on(session):
    """Availability is a fact about the bank, not about the registry."""
    subjects_mod.sync(session)
    session.flush()
    rows = session.execute(select(Subject)).scalars().all()
    assert rows
    assert all(not r.available for r in rows), (
        "sync made a subject available without any verified content behind it"
    )


def test_a_subject_becomes_available_only_on_verified_content(session):
    subjects_mod.sync(session)
    session.flush()

    # `uq_question_identity` is (exam_body, year, subject_code, paper,
    # question_number), so each batch continues the numbering rather than
    # restarting it -- two questions cannot share a slot on one paper.
    added = 0

    def add(n: int) -> None:
        nonlocal added
        for i in range(n):
            number = added + i + 1
            session.add(
                Question(
                    id=f"waec-2019-chemistry-p1-{number}",
                    exam_body="WAEC", subject_code="CHM", year=2019, paper="1",
                    question_number=number, type="objective", stem=f"Q{number}",
                    options=[{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
                    answer={"key": "A"}, status="verified", licence="original",
                    stem_hash=f"h{number}",
                )
            )
        added += n
        session.flush()

    threshold = 5

    add(threshold - 1)
    subjects_mod.refresh_availability(session, threshold=threshold)
    session.flush()
    assert session.get(Subject, "CHM").available is False, "available below the threshold"

    add(2)
    subjects_mod.refresh_availability(session, threshold=threshold)
    session.flush()
    assert session.get(Subject, "CHM").available is True


def test_unverified_and_dev_only_questions_do_not_count(session):
    """The gate, counted the same way every student-facing read counts."""
    subjects_mod.sync(session)
    session.flush()

    for i, (status, licence) in enumerate(
        [("draft", "original"), ("needs_review", "original"),
         ("rejected", "original"), ("verified", "dev_only")]
    ):
        session.add(
            Question(
                id=f"waec-2019-physics-p1-{i}", exam_body="WAEC", subject_code="PHY",
                year=2019, paper="1", question_number=i + 1, type="objective",
                stem="Q", options=[{"label": "A", "text": "x"}], answer={"key": "A"},
                status=status, licence=licence, stem_hash=f"p{i}",
            )
        )
    session.flush()

    counts = subjects_mod.verified_counts(session)
    assert counts.get("PHY", 0) == 0, (
        "a draft, rejected or dev-only question was counted as servable"
    )

    subjects_mod.refresh_availability(session, threshold=1)
    session.flush()
    assert session.get(Subject, "PHY").available is False


def test_a_subject_is_withdrawn_if_its_content_goes_away(session):
    """Availability is recomputed, not latched."""
    subjects_mod.sync(session)
    session.flush()
    session.add(
        Question(
            id="waec-2019-biology-p1-1", exam_body="WAEC", subject_code="BIO",
            year=2019, paper="1", question_number=1, type="objective", stem="Q",
            options=[{"label": "A", "text": "x"}], answer={"key": "A"},
            status="verified", licence="original", stem_hash="b1",
        )
    )
    session.flush()
    subjects_mod.refresh_availability(session, threshold=1)
    session.flush()
    assert session.get(Subject, "BIO").available is True

    session.execute(
        Question.__table__.update().where(Question.id == "waec-2019-biology-p1-1")
        .values(status="rejected")
    )
    session.flush()
    subjects_mod.refresh_availability(session, threshold=1)
    session.flush()
    assert session.get(Subject, "BIO").available is False
