FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Maak werkdirectory
WORKDIR /app

# Copy requirements + install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy alle code (consumers + scripts)
COPY . .

# Standaard commando – kan worden overschreven in docker-compose
CMD ["python", "consumer.py"]
