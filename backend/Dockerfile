FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY tests ./tests
COPY fixtures ./fixtures

RUN pip install --no-cache-dir -e ".[dev]"

RUN mkdir -p /app/data /app/storage

ENV DATABASE_URL=sqlite:///./data/artistassist.db \
    MEDIA_ROOT=./storage \
    PLATFORM_LIVE=0

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
