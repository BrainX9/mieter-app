# Image für den Betrieb (amd64 und arm64). Bauen: docker build -t mieter-app .
# Rollen: "web" (Standard) oder "worker", siehe docker/start.sh.

FROM ghcr.io/astral-sh/uv:0.13.2 AS uv

FROM python:3.13-slim-trixie AS bauen
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# Erst nur die Abhängigkeiten: Diese Schicht bleibt im Cache, solange uv.lock gleich bleibt.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY manage.py ./
COPY mieter ./mieter
COPY docker ./docker
# collectstatic braucht nur Platzhalter, keine echte Datenbank und keine Secrets.
RUN SECRET_KEY=nur-zum-bauen DATABASE_URL=postgres://bauen@localhost/bauen \
    /app/.venv/bin/python manage.py collectstatic --noinput


FROM python:3.13-slim-trixie
LABEL org.opencontainers.image.source="https://github.com/BrainX9/mieter-app" \
      org.opencontainers.image.description="Betriebskostenabrechnungen für Mieter" \
      org.opencontainers.image.licenses="MIT"

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Berlin

RUN groupadd --system --gid 1000 mieter \
    && useradd --system --uid 1000 --gid mieter --home-dir /app --no-create-home mieter

WORKDIR /app
COPY --from=bauen --chown=root:root /app /app

USER mieter
EXPOSE 8000
ENTRYPOINT ["/app/docker/start.sh"]
CMD ["web"]
