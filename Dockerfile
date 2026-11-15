FROM python:3.11-slim

# pango/harfbuzz for WeasyPrint, libgomp for LightGBM
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LLL_DATA_DIR=/app/data \
    LLL_MODEL_DIR=/app/models \
    LLL_TEMPLATE_DIR=/app/templates

WORKDIR /app

# COPY pyproject.toml README.md ./
# COPY src ./src
# RUN pip install .

ENV POETRY_VERSION=2.5.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN pip install "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock README.md ./
COPY src ./src
RUN poetry install --only main --no-ansi \
    && rm -rf $POETRY_CACHE_DIR

COPY data ./data
COPY api ./api
COPY app ./app
COPY templates ./templates
COPY docs ./docs
COPY models ./models
COPY .streamlit ./.streamlit

EXPOSE 8000

# Access log is off because /lookup query strings contain residents' addresses.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
