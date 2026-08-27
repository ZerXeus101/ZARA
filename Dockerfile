# Use lightweight official Python runtime
FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered streaming
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create non-root user for security
RUN groupadd --gid 1000 zara && \
    useradd --uid 1000 --gid zara --shell /bin/false --create-home zara

# Set working directory
WORKDIR /app

# Install dependencies first (leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=zara:zara . .

# Switch to non-root user
USER zara

# Default command runs the 24/7 administration bot daemon
CMD ["python", "bot.py"]
