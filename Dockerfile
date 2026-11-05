FROM python:3.13-slim
LABEL org.opencontainers.image.source="https://github.com/timzilla/pixel-pantry" \
      org.opencontainers.image.description="Pixel Pantry: a cozy self-hosted recipe shelf" \
      org.opencontainers.image.licenses="MIT"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ /app/
ENV RECIPES_DATA=/data PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
