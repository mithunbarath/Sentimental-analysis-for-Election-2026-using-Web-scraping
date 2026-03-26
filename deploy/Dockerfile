# =============================================================================
# Dockerfile — Palladam Politics Scraper container
# Build:  docker build -t palladam-scraper .
# Run:    docker run --rm \
#           -e BRIGHT_DATA_API_TOKEN=xxx \
#           -e GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account.json \
#           -v $(pwd)/gcp-service-account.json:/app/gcp-service-account.json:ro \
#           -v $(pwd)/output:/app/output \
#           palladam-scraper --platforms all --broad-search
# =============================================================================
FROM python:3.11-slim

# System packages required by Playwright / Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 \
    libcairo2 libasound2 wget ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install chromium \
 && playwright install-deps chromium

# Copy application source
COPY . .

# Non-root user for security
RUN useradd --create-home --shell /bin/bash scraper \
 && chown -R scraper:scraper /app
USER scraper

ENTRYPOINT ["python", "main.py"]
CMD ["--platforms", "all", "--broad-search", "--timeout", "20"]
