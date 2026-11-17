FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for DuckDB / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose FastAPI (8000) and Streamlit (8501)
EXPOSE 8000
EXPOSE 8501

# Default command (overridden in docker-compose)
CMD ["python", "scripts/api.py"]