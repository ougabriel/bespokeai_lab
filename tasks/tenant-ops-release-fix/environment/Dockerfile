FROM python:3.12.8-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app/app
COPY bin /app/bin
COPY config /app/config
COPY data /app/data

RUN mkdir -p /app/state \
    && chmod +x /app/bin/bootstrap_data.py /app/bin/run_server.py
