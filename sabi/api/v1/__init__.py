"""The JSON API, mounted at /api.

Assembled here so that `sabi/api/app.py` mounts one router rather than
importing eight. Every route in it answers JSON, including its errors: the
Jinja surface redirects an unauthenticated visitor to the login page, which is
right for a browser following a 303 and wrong for a `fetch`.

The Jinja routes stay alongside these for the whole migration (see
`docs/REDIRECTION.md`). A surface moves when its Next.js route and its
Playwright test land in the same commit that deletes its template -- never
before, so there is no window in which something is unreachable.
"""

from __future__ import annotations

from fastapi import APIRouter

from sabi.api.v1 import auth, catalog, exam, study, tutor

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(study.router)
api_router.include_router(exam.router)
api_router.include_router(tutor.router)

__all__ = ["api_router"]
