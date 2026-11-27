# syntax=docker/dockerfile:1
#
# Two images from one file:
#   dev   what `make up` runs: test dependencies, auto-reload, the source
#         bind-mounted over /app.
#   prod  what is deployed: runtime dependencies only, an unprivileged user,
#         only the code the app needs. It is the last stage, so a plain
#         `docker build` produces it.

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NLTK_DATA=/usr/local/share/nltk_data
WORKDIR /app

# Dependencies first, so the layer is reused until the requirements change.
COPY requirements.txt .
RUN pip install -r requirements.txt

# The sentiment lexicon, fetched at build time so a container never downloads
# anything when it starts. In a system path, readable by any user.
RUN python -m nltk.downloader -d "$NLTK_DATA" vader_lexicon


FROM base AS dev
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM base AS prod
RUN useradd --create-home --uid 10001 app
# Only what runs: the app, and the migrations it applies at start-up.
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
USER app

# Reported by /healthz, so a deploy can be seen to have taken effect.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

EXPOSE 8000
# One process. Analyses run in the worker (`python -m app.worker`, same
# image), so there is nothing here for more processes to do, and the cache,
# the alert sweep and the start-up migration each exist exactly once.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
