FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Ensure directories exist (used when GCS_BUCKET not set)
RUN mkdir -p static/uploads local_exams

EXPOSE 8080

# Cloud Run injects PORT env var; default to 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
