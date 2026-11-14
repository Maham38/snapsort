FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    AI_MODEL_ROOT=/home/snapsort/.insightface

WORKDIR /app

# System libraries required by InsightFace and ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy package metadata and application source
COPY pyproject.toml ./
COPY app ./app

# Install FastAPI and AI dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install ".[ai]"

# Copy migrations and remaining backend files
COPY . .

# Create a non-root runtime user and model-cache directory
RUN useradd --create-home --shell /usr/sbin/nologin snapsort \
    && mkdir -p /home/snapsort/.insightface \
    && chown -R snapsort:snapsort /app /home/snapsort

USER snapsort

EXPOSE 8000

# Default service: FastAPI
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
