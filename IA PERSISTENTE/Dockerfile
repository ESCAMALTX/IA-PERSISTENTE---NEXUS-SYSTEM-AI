# NEXUS SYSTEM AI — imagen autocontenida.
#
# Lleva Python y todas las dependencias dentro: en el otro equipo solo hace
# falta Docker. No hay que instalar Python, ni pip, ni nada más.
#
#   docker compose up -d --build          (recomendado)
#   docker build -t nexus-ai .            (manual)
#   docker run -d -p 8000:8000 -v nexus-data:/app/data \
#       -e DEEPSEEK_API_KEY=sk-... nexus-ai

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NEXUS_HOST=0.0.0.0 \
    NEXUS_PORT=8000 \
    NEXUS_DATA_DIR=/app/data

WORKDIR /app

# Las dependencias primero: el rebuild es rápido si solo cambia el código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py deepseek_client.py diagnosis.py events.py \
     logger.py main.py monitor.py run.py ./
COPY static ./static

RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "run.py"]
