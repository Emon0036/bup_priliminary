# GridWise Smart Campus Energy Optimization Dockerfile
# Production-ready, minimal Docker image for the GridWise service

# Use a lightweight Python base image
FROM python:3.12-slim

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

# Set working directory
WORKDIR /app

# Install only required system dependencies
# (build essentials for scipy, minimal packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY gridwise/gridwise/pyproject.toml gridwise/requirements.txt ./

# Install Python dependencies
# FastAPI, Pydantic, SciPy, and other required packages
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        fastapi>=0.115,<1 \
        pydantic>=2.8,<3 \
        scipy>=1.13,<2 \
        uvicorn>=0.30,<1 \
        httpx>=0.27,<1 \
        python-dotenv>=1.0,<2 \
        pydantic-extra-types>=0.3,<1

# Copy source code cleanly (no secrets, no .env)
COPY gridwise/gridwise/app ./app
COPY gridwise/gridwise/llm ./llm
COPY gridwise/gridwise/tests ./tests
COPY gridwise/gridwise/scripts ./scripts
COPY gridwise/gridwise/docs ./docs
COPY gridwise/gridwise/.env.example .env.example
COPY gridwise/gridwise/.gitignore .gitignore
COPY gridwise/gridwise/README.md README.md
COPY gridwise/gridwise/LICENSE LICENSE

# Expose the documented port
EXPOSE 8000

# Set user to non-root
USER appuser

# Deterministic startup: health available immediately, LLM optional
# Health check should respond immediately without LLM
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]