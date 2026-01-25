FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port (Zeabur expects this, though environment variable often overrides)
EXPOSE 8000

# Run the application using shell to expand the PORT environment variable
# If PORT is not set, default to 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
