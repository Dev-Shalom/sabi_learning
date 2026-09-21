# Single-stage: the app is Python and a directory of markdown. A multi-stage
# build would save little and hide the corpus, which is the thing most likely to
# need inspecting on a running instance.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY sabi ./sabi
COPY evalharness ./evalharness
COPY corpus ./corpus
COPY config ./config
COPY eval ./eval
COPY tools ./tools

RUN pip install --upgrade pip && pip install -e .

# The local embedder is fitted on the corpus and its artifact is rebuilt by
# ingest, so it is not baked into the image.
RUN mkdir -p /app/var

# Run as a non-root user. Nothing here needs root, and the admin surface is
# reachable over the network.
RUN useradd --create-home --uid 10001 sabi && chown -R sabi:sabi /app
USER sabi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"

# `--forwarded-allow-ips` decides whose X-Forwarded-For uvicorn will believe.
# It defaults to '*' because on Fly nothing reaches this container except Fly's
# own proxy, and pinning the range would break the moment they renumber it.
#
# That default is only safe because of how the header is read: `client_ip`
# takes the *rightmost* entry, which only a proxy can have appended, rather
# than the leftmost one the caller controls. Set FORWARDED_ALLOW_IPS to the
# proxy's address on a host that does not isolate the container this way.
#
# One worker by default. The corpus is small and the work is IO-bound against
# Postgres; a second worker doubles the memory for the embedding model without
# doubling throughput. Raise it with WEB_CONCURRENCY when there is traffic that
# justifies it.
CMD ["sh", "-c", "python -m sabi.cli init && python -m sabi.cli ingest && exec uvicorn sabi.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-*}\""]
