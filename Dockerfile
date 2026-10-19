# Production Dockerfile for Grand Horizon Hotel Front Office PMS
FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable real-time logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install minimal system tools (curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project source files
COPY . /app/

# Create directories for persistent SQLite volume & staticfiles
RUN mkdir -p /app/data /app/staticfiles

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

# Collect static files with WhiteNoise during build
RUN SECRET_KEY="build-key-for-static-collection" python manage.py collectstatic --noinput

# Expose Gunicorn port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/login/ || exit 1

# Run entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
