FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY revalli/__init__.py revalli/__init__.py
RUN pip install .  && pip uninstall -y revalli

COPY . .
RUN pip install --no-deps . \
    && useradd --system --uid 10001 --home /app revalli \
    && mkdir -p /data && chown revalli /data

USER revalli
EXPOSE 8000

# Por padrão sobe a API. O worker usa a mesma imagem com outro comando.
CMD ["sh", "/app/docker-entrypoint.sh"]
