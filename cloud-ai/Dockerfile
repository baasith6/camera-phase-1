FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --default-timeout=200 -r requirements.txt \
    && pip install --no-cache-dir --default-timeout=200 "git+https://github.com/ultralytics/CLIP.git"
COPY . ./

ENTRYPOINT ["python", "-m", "app.main"]
