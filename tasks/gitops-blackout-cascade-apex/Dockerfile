FROM us-central1-docker.pkg.dev/bespokelabs/nebula-devops-registry/nebula-devops:1.0.0

ENV DISPLAY_NUM=1
ENV COMPUTER_HEIGHT_PX=768
ENV COMPUTER_WIDTH_PX=1024
ENV SKIP_BLEATER_BOOT=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /task

COPY data/runtime/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && ln -sf /usr/bin/python3 /usr/local/bin/python

COPY data /task/data
COPY tests /task/tests
COPY task.yaml /task/task.yaml
COPY grader.py /task/grader.py
COPY setup.sh /task/setup.sh
COPY solution.sh /task/solution.sh

RUN mkdir -p /mcp_server/tasks \
    && ln -s /task /mcp_server/tasks/gitops-blackout-cascade-apex \
    && chmod +x /task/setup.sh /task/solution.sh /task/data/runtime/bin/bootstrap_data.py /task/data/runtime/bin/run_server.py /task/data/runtime/bin/simulate_rollout.py /task/data/runtime/bin/task_entrypoint.sh

ENTRYPOINT ["/task/data/runtime/bin/task_entrypoint.sh"]
