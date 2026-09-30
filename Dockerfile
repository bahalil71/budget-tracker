# Multi-stage build for minimal image size
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies in a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final runtime image
FROM python:3.12-slim

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy app code
COPY main.py .
COPY static ./static

# Expose app port
EXPOSE 8088

# Optimize python runtime
ENV PYTHONOPTIMIZE=2 \
    PYTHONUNBUFFERED=1

# Run single-process hybrid FastAPI + aiogram bot
CMD ["python", "main.py"]
