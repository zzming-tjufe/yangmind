# YangMind Lab API — Hugging Face Spaces / 容器部署
# 监听 7860（HF Spaces 默认端口）

FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

COPY --chown=user backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user backend/app ./app

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
