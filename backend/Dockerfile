FROM denoland/deno:bin AS deno
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=deno /deno /usr/local/bin/deno

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg nodejs ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -U -r requirements.txt
COPY main.py .

CMD sh -c "pip install --no-cache-dir -U yt-dlp && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"