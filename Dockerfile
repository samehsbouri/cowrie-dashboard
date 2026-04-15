FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
    -days 365 -nodes -subj "/CN=cowrie-dashboard"

COPY app.py .
COPY templates/ ./templates/

ENV LOGS_DIR=/cowrie/logs
ENV STATE_DIR=/cowrie/var/lib/cowrie

EXPOSE 8443

CMD ["python", "app.py"]