FROM python:3.11-slim

WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.4

# Copy only dependency files first for better caching
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry to not use a virtual environment and install runtime deps only
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy rest of the source code
COPY . /app/

# Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Default command (will be overridden by Docker Compose)
CMD ["python", "src/main.py"]
