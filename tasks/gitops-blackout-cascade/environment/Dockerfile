FROM us-central1-docker.pkg.dev/bespokelabs/nebula-devops-registry/nebula-devops:1.0.0

WORKDIR /app

ENV DISPLAY_NUM=1
ENV COMPUTER_HEIGHT_PX=768
ENV COMPUTER_WIDTH_PX=1024
ENV SKIP_BLEATER_BOOT=1
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
    && rm -rf /test /tests \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && chmod +x /app/bin/bootstrap_data.py /app/bin/run_server.py /app/bin/simulate_rollout.py /app/bin/task_entrypoint.sh

ENTRYPOINT ["/app/bin/task_entrypoint.sh"]
