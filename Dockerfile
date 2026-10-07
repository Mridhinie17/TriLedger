# ==============================================================================
# Multi-Stage Dockerfile for TriLedger Reconciliation Platform
# Stage 1: Build Google Stitch Vite/React SPA
# Stage 2: Python runtime with poppler, tesseract OCR, FastAPI, & static SPA
# ==============================================================================

# --- Stage 1: Frontend Build ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python Runtime ---
FROM python:3.11-slim AS runtime

# Install system dependencies for PDF rendering and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY config/ ./config/
COPY db/ ./db/
COPY fx/ ./fx/
COPY extraction/ ./extraction/
COPY matching/ ./matching/
COPY agent/ ./agent/
COPY marts/ ./marts/
COPY api/ ./api/
COPY ui/ ./ui/
COPY data_gen/ ./data_gen/
COPY eval/ ./eval/
COPY tests/ ./tests/
COPY run_seed.py ./
COPY pyproject.toml ./

# Copy built frontend assets from Stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Initialize directory structure
RUN mkdir -p data/invoices_pdf data/marts data/fx

# Run database initialization and synthetic population
RUN python run_seed.py && python marts/exporter.py

# Expose ports: 8000 (FastAPI + Google Stitch UI), 8501 (Streamlit workbench)
EXPOSE 8000 8501

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Start FastAPI backend (which statically serves the React SPA)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
