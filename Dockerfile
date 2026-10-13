FROM python:3.11-slim

# ffmpeg：bailian 引擎需要 wav→mp3；qwen_audio 引擎用它测时长
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY web/ web/
COPY scripts/ scripts/
COPY content/content.json content/
COPY content/quiz/ content/quiz/
COPY content/media/ content/media/
COPY content/media_config.py content/
COPY content/figures_textbook.json content/

ENV KY_CONTENT_DIR=/app/content \
    KY_DB_PATH=/app/data/kaoyan.db \
    KY_DATA_DIR=/app/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
