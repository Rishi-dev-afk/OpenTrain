# ─── OpenTrain Worker Node ────────────────────────────────────────────────────
# Bundles Python, sentence-transformers, and the worker client into a single
# image that volunteers can run with one `docker run` command.

FROM python:3.11-slim

# System deps (needed by torch/transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model at build time so workers start instantly
# (avoids ~90MB download on every new container start)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy worker source
COPY worker.py   .
COPY ml_tasks.py .

# Default entrypoint — volunteers override --server and --token at runtime
ENTRYPOINT ["python", "worker.py"]
CMD ["--help"]