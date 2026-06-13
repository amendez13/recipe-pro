# Recipe Pro container image (automation issue #351).
#
# Built on the VPS by the automation `container_service` role (external-repo
# mode) and pushed to ECR. The three SQLite DBs live on a bind-mounted /data
# volume; auth secrets come from the environment and are substituted into the
# baked config (app/config.py resolves ${VAR}). Read via the app's -c flag.

FROM python:3.12-slim AS runtime
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8084
HEALTHCHECK --interval=30s --timeout=5s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8084/health')"]
CMD ["python", "-m", "app.main", "-c", "/app/config/config.container.yaml"]
