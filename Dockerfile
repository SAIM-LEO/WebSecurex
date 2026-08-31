FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY python-backend/requirements.txt python-backend/
COPY engines/xss_engine/requirements.txt engines/xss_engine/
COPY engines/sqli_engine/requirements.txt engines/sqli_engine/
COPY engines/nosql_engine/requirements.txt engines/nosql_engine/

# Install all python packages
RUN pip install --no-cache-dir -r python-backend/requirements.txt \
    && pip install --no-cache-dir -r engines/xss_engine/requirements.txt \
    && pip install --no-cache-dir -r engines/sqli_engine/requirements.txt \
    && pip install --no-cache-dir -r engines/nosql_engine/requirements.txt

# Copy application files
COPY . .

# Make reports directory
RUN mkdir -p /app/python-backend/reports /app/reports

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --app-dir python-backend --host 0.0.0.0 --port ${PORT:-8000}"]
