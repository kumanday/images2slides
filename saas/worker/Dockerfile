FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi \
    sqlalchemy[asyncio] \
    asyncpg \
    pydantic-settings \
    google-auth \
    google-api-python-client \
    cryptography \
    pillow \
    && pip install --no-cache-dir -e .

# Copy application code
COPY . .

CMD ["python", "-m", "saas.worker.main"]