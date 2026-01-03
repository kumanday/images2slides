FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
COPY images2slides ./images2slides
COPY cli ./cli
COPY saas ./saas

RUN pip install --no-cache-dir -e ".[saas,vlm]"

EXPOSE 8000

CMD ["uvicorn", "saas.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
