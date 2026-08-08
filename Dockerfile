# Deploys Aegis anywhere that runs a container: Hugging Face Spaces, Render,
# Railway, Fly, Cloud Run. Works with no API key — the app falls back to
# deterministic mode — so a demo link needs no secrets.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate the synthetic data and warm the vector index at build time, so the
# first request a visitor makes isn't the one that pays for indexing.
RUN python data/generate_data.py \
 && python data/generate_corpus.py \
 && EMBEDDING_MODE=hash python -c "from rag.store import get_store; s=get_store(); print('indexed', s.count(), 'chunks')"

# The offline embedder keeps the image self-contained and startup instant.
# Set EMBEDDING_MODE=auto to let ChromaDB download its MiniLM model instead.
ENV EMBEDDING_MODE=hash \
    LLM_PROVIDER=mock \
    PORT=8000

EXPOSE 8000

# Hosts inject $PORT; the default covers plain `docker run`.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
