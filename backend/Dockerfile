FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    git \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir "torch>=2.0.0" --index-url https://download.pytorch.org/whl/cpu
#
RUN pip install --no-cache-dir \
    "fr-core-news-lg @ https://github.com/explosion/spacy-models/releases/download/fr_core_news_lg-3.7.0/fr_core_news_lg-3.7.0-py3-none-any.whl"
# 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app
COPY ./scripts ./scripts

# Feature/embedding#131
ARG BAKE_EMBEDDING_MODELS="sentence-transformers/all-MiniLM-L6-v2 jinaai/jina-embeddings-v2-base-code"
ENV HF_HOME=/opt/hf \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN mkdir -p /opt/hf /opt/tiktoken \
    && BAKE_EMBEDDING_MODELS="$BAKE_EMBEDDING_MODELS" python scripts/bake_embedding_models.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /opt/hf /opt/tiktoken
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]