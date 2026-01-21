FROM python:3.9-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for some python packages)
# RUN apt-get update && apt-get install -y gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port 80 for Lightsail Container Service
EXPOSE 80

# Environment variable for N8N URL (can be overridden in deployment)
# ENV N8N_WEBHOOK_URL="https://gscode.app.n8n.cloud/webhook/ask"

CMD ["fastapi", "run", "main.py", "--port", "80"]
