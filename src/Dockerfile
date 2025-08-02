# Security: Using Python 3.13 slim with latest security updates
# TODO: Monitor for updated base images to address CVE-2025-6020 (HIGH)
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
