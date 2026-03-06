FROM python:3.11-slim

# Install system dependencies for OpenCV (libGL) and others
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
# Install uv for fast dependency management
ENV UV_HTTP_TIMEOUT=600
RUN pip install uv

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml .
# COPY requirements.txt . # Optional if you want to use it as fallback

# Install dependencies using uv
# using --system to install into the container's python environment
RUN UV_HTTP_TIMEOUT=600 uv pip install --system --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu126 .

# Copy the application code
# Copy the application code (including preload script)
COPY . .

# Run the model preload script during build
# RUN python preload_models.py

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose the API port
EXPOSE 5000

# Run the application
CMD ["python", "run.py"]
