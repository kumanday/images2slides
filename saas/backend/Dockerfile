FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi[standard] \
    uvicorn \
    sqlalchemy[asyncio] \
    asyncpg \
    pydantic-settings \
    python-multipart \
    google-auth \
    cryptography \
    pillow \
    && pip install --no-cache-dir -e .

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "saas.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]