FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY heartbeat_producer.py .

CMD ["python", "heartbeat_producer.py"]
