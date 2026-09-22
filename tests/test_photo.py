"""Photo input, and the rules that keep it an input method.

The feature is small. The things that make it safe are not, and they are what
this file is about:

* **The image bytes are never stored.** Checked against the table's columns,
  not against a comment, so adding a `data` column breaks a test.
* **Nothing is asked automatically.** A transcription lands in a textarea and
  the student presses Ask. A misread digit that gets answered without anyone
  looking is the failure this product exists to prevent.
* **The format is decided by the bytes.** A file claiming `image/png` and
  holding something else is rejected on its magic bytes.
* **It is metered.** An unmetered path is what `sabi/limits/limiter.py`'s own
  docstring forbids, and OCR is metered on its own cap rather than spending a
  question the student has not asked.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import inspect, select

from sabi import vision
from sabi.llm.base import ImagePart, LLMUnavailable, NoVisionClient
from sabi.models import OcrUpload, UsageEvent
from sabi.vision.fixtures import FixtureVisionClient

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ocr"
POLYGON = FIXTURES / "polygon.png"
INDICES = FIXTURES / "indices.jpg"
UNREADABLE = FIXTURES / "unreadable.png"


def csrf(client, path="/app"):
    return re.search(
        r'name="csrf_token" value="([^"]+)"', client.get(path).text
    ).group(1)


def upload(client, path: Path, name: str | None = None, content_type="image/png"):
    return client.post(
        "/photo",
        data={"csrf_token": csrf(client, "/photo")},
        files={"photo": (name or path.name, path.read_bytes(), content_type)},
    )


@pytest.fixture
def reader(monkeypatch):
    """Swap the unavailable client for the fixture-backed one."""
    monkeypatch.setattr(vision, "get_vision", lambda: FixtureVisionClient())
    import sabi.api.app as app_module

    monkeypatch.setattr(app_module.vision, "get_vision", lambda: FixtureVisionClient())
    return FixtureVisionClient()


# ------------------------------------------------------------ the image itself


def test_the_image_is_never_stored(session):
    """Not a comment, a column list.

    A photograph of an exercise book carries a name, handwriting and often a
    school stamp, and this audience is majority under 18. If a `data` column
    is ever added, this fails.
    """
    columns = {c.name for c in inspect(OcrUpload).columns}
    for forbidden in ("data", "image", "bytes", "blob", "content", "payload", "path"):
        assert forbidden not in columns, (
            f"ocr_uploads.{forbidden} would persist the picture itself"
        )
    assert "sha256" in columns and "transcription" in columns


def test_the_format_comes_from_the_bytes_not_the_upload(client, reader, session):
    """A file can claim any content type. Only the magic bytes decide."""
    assert vision.sniff(POLYGON.read_bytes()) == "image/png"
    assert vision.sniff(INDICES.read_bytes()) == "image/jpeg"

    with pytest.raises(vision.ImageRejected):
        vision.sniff(b"%PDF-1.7\nnot an image at all")

    # Declared image/png, actually a PDF: refused, and refused politely.
    r = client.post(
        "/photo",
        data={"csrf_token": csrf(client, "/photo")},
        files={"photo": ("sneaky.png", b"%PDF-1.7\n" + b"x" * 200, "image/png")},
    )
    assert r.status_code == 200
    assert "not a photo Sabi can read" in r.text
    assert session.execute(select(OcrUpload)).scalars().all() == []


def test_an_oversized_photo_is_refused_with_the_size_in_the_message(client, reader):
    too_big = b"\xff\xd8\xff" + b"\x00" * (vision.MAX_BYTES + 10)
    with pytest.raises(vision.ImageRejected) as caught:
        vision.validate(too_big)
    assert "MB" in str(caught.value)


def test_an_empty_upload_is_refused(client, reader):
    with pytest.raises(vision.ImageRejected):
        vision.validate(b"")


# ---------------------------------------------------------------- the reading


def test_a_photo_is_transcribed_and_never_answered(client, reader, session):
    """The whole safety property of this feature, in one test."""
    r = upload(client, POLYGON)
    assert r.status_code == 200

    # The text Sabi read is offered for editing...
    assert "Find the sum of the interior angles" in r.text
    assert 'name="question"' in r.text
    assert "What Sabi read" in r.text

    # ...and nothing was asked. No answer, no citation, no request row.
    assert '<details class="source"' not in r.text
    from sabi.models import Request as RequestRow

    assert session.execute(select(RequestRow)).scalars().all() == [], (
        "the photo route asked a question by itself"
    )


def test_the_transcription_goes_into_a_form_the_student_submits(client, reader):
    r = upload(client, POLYGON)
    # The form posts to /ask, carries a CSRF token, and holds the text in a
    # textarea rather than a hidden field -- it has to be editable.
    assert 'action="/ask"' in r.text
    assert re.search(r'<textarea[^>]*name="question"[^>]*>', r.text)
    assert 'name="csrf_token"' in r.text


def test_an_unreadable_photo_says_so_rather_than_inventing_text(client, reader, session):
    r = upload(client, UNREADABLE)
    assert r.status_code == 200
    assert "could not be read" in r.text
    assert "What Sabi read" not in r.text
    assert session.execute(select(OcrUpload)).scalars().all() == []


def test_the_same_photo_twice_is_read_once(client, reader, session):
    upload(client, POLYGON)
    first = session.execute(select(OcrUpload)).scalars().one()
    assert first.hits == 0

    upload(client, POLYGON)
    session.expire_all()
    rows = session.execute(select(OcrUpload)).scalars().all()
    assert len(rows) == 1, "the same image was read twice"
    assert rows[0].hits == 1

    events = session.execute(
        select(UsageEvent).where(UsageEvent.event_type == vision.OCR_EVENT)
    ).scalars().all()
    assert len(events) == 1, "a cached read was metered again"


# ------------------------------------------------------------------ metering


def test_reading_a_photo_does_not_spend_a_question(client, reader, session):
    """It is a model call, but the student has not asked anything yet."""
    from sabi.limits import limiter

    assert vision.OCR_EVENT not in limiter.COUNTED_EVENTS, (
        "OCR events counted against the question cap would charge a student "
        "for a photo they may well discard"
    )

    before = client.get("/app").text
    upload(client, POLYGON)
    after = client.get("/app").text

    left = lambda page: re.search(r"<strong>(\d+)</strong> left", page)
    if left(before):
        assert left(before).group(1) == left(after).group(1)


def test_photos_are_capped_on_their_own_allowance(client, reader, session, monkeypatch):
    """Unmetered is not the same as unbounded."""
    monkeypatch.setattr(vision, "ocr_cap", lambda s, user: 1)
    import sabi.api.app as app_module

    monkeypatch.setattr(app_module.vision, "ocr_cap", lambda s, user: 1)

    upload(client, POLYGON)
    r = upload(client, INDICES, content_type="image/jpeg")
    assert "all your photo questions for today" in r.text

    session.expire_all()
    rows = session.execute(select(OcrUpload)).scalars().all()
    assert len(rows) == 1, "the cap did not stop the second read"


def test_every_read_writes_a_usage_event(client, reader, session):
    upload(client, POLYGON)
    events = session.execute(
        select(UsageEvent).where(UsageEvent.event_type == vision.OCR_EVENT)
    ).scalars().all()
    assert len(events) == 1
    assert events[0].billable is True


# ----------------------------------------------- the state without a key


def test_without_a_vision_model_the_page_says_so_and_offers_the_composer(client):
    """The real production behaviour here, and it must not look like a fault."""
    assert isinstance(vision.get_vision(), NoVisionClient)
    assert vision.get_vision().available() is False

    page = client.get("/photo").text
    assert "cannot read photos here" in page
    assert 'type="file"' not in page, "an upload box that cannot work"
    assert "/app" in page


def test_the_unavailable_client_raises_rather_than_returning_empty_text():
    """Empty text would render as a transcription with nothing to correct."""
    with pytest.raises(LLMUnavailable):
        NoVisionClient().transcribe(
            ImagePart(data=b"\xff\xd8\xff", media_type="image/jpeg"),
            model="whatever",
        )


def test_the_fixture_client_refuses_an_image_it_has_no_transcription_for():
    """A test that wants a transcription has to commit one."""
    with pytest.raises(LLMUnavailable):
        FixtureVisionClient().transcribe(
            ImagePart(data=UNREADABLE.read_bytes(), media_type="image/png"),
            model="whatever",
        )


def test_the_committed_fixtures_match_their_images():
    """The index is keyed by hash, so a re-saved image silently stops matching."""
    index = json.loads((FIXTURES / "transcriptions.json").read_text(encoding="utf-8"))
    on_disk = {
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in FIXTURES.iterdir()
        if p.suffix in {".png", ".jpg"}
    }
    missing = set(index) - on_disk
    assert not missing, f"transcriptions with no image: {sorted(missing)}"
    assert len(index) >= 3
