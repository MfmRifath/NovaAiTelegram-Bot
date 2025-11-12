FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Expose port for Cloud Run health checks
EXPOSE 8080

# Use wrapper script for Cloud Run compatibility
CMD ["python", "run_bot.py"]