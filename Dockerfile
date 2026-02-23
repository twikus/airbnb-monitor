# Image officielle Playwright Python — Chromium déjà installé
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps

COPY . .

RUN mkdir -p data/screenshots

EXPOSE 8080

CMD ["python", "app.py"]
