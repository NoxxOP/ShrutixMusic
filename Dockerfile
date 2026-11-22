FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["bash", "start"]
