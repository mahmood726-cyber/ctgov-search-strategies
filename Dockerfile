# CT.gov Trial Registry Integrity Suite
# Docker container for reproducible validation

FROM python:3.11-slim

LABEL maintainer="Mahmood Ahmad"
LABEL version="4.1"
LABEL description="CT.gov Trial Registry Integrity Suite with TruthCert TC-TRIALREG"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY output/ ./output/
COPY FINAL_STRATEGY_GUIDE.md .
COPY EDITORIAL_REVIEW.md .

# Create output directory
RUN mkdir -p /app/output /app/data/papers

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command - run validation
CMD ["python", "scripts/proper_validation.py", "data/gold_standard.json", "-o", "output", "-n", "50"]
