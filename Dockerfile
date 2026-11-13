# Use official slim Python runtime
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set default timezone to UTC
ENV TZ=UTC

# Set working directory inside container
WORKDIR /app

# Copy and install python dependencies first (Docker layer caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and files
COPY core/ /app/core/
COPY templates/ /app/templates/
COPY ui/ /app/ui/
COPY config.yaml /app/
COPY dashboard.py /app/
COPY cron_worker.py /app/
COPY run.py /app/

# Create persistent storage directories
RUN mkdir -p /app/uploads /app/data

# Expose Streamlit default port
EXPOSE 8501

# Default command runs the Streamlit UI dashboard
CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]

