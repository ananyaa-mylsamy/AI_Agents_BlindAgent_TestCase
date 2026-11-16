# FlyFinder mock site. State is in memory only: a fresh container is a fresh site.
FROM python:3.12-slim
WORKDIR /site
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py flights.json ./
COPY templates/ templates/
ENV SITE_LOG=/output/site_log.jsonl PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["python", "app.py"]
