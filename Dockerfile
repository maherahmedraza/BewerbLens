FROM python:3.12-slim

WORKDIR /app

# Install system deps for thefuzz[speedup] (python-Levenshtein needs gcc)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (cached layer — only re-runs when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY apps/tracker/ /app/apps/tracker/
COPY apps/orchestrator/ /app/apps/orchestrator/

# Set PYTHONPATH so all imports resolve correctly
ENV PYTHONPATH=/app/apps/tracker:/app/apps/orchestrator

# Health check — orchestrator exposes /health
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000

CMD ["python", "apps/orchestrator/main.py"]
