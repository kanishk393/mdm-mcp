FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mdm_mcp ./mdm_mcp

RUN pip install --no-cache-dir .

ENV MDM_DATA_DIR=/data
VOLUME /data

ENTRYPOINT ["mdm-mcp"]
