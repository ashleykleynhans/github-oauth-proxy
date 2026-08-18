FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies first so the layer can be cached
# between application changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY webhook.py github_auth.py ./

# Run as a non-root user.
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --create-home app
USER app

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/', timeout=3)"]

CMD ["python3", "webhook.py"]
