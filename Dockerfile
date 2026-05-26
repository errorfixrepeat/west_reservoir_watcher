FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY bot.py .
CMD ["gunicorn", "--workers=1", "--threads=4", "--bind=0.0.0.0:8080", "bot:app"]
