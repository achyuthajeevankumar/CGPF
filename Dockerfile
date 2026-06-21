FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure storage directories exist
RUN mkdir -p static/uploads/churches static/uploads/media static/uploads/profiles

# Expose port
EXPOSE 8080

# Run seeder and launch FastAPI server, using $PORT injected by Render (defaulting to 8080)
CMD sh -c "python seed.py && python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"
