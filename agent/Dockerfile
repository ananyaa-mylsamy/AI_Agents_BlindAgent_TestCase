# The agent: browser-use with headless Chromium, plus the scripts that run the
# case and score it. browser-use drives Playwright's Chromium.
FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY requirements.txt .
# libatomic1 is needed by the Node runtime bundled with Playwright on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
 && pip install -r requirements.txt \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*
COPY *.py *.md ./
ENTRYPOINT ["python"]
CMD ["run_case.py", "--help"]
