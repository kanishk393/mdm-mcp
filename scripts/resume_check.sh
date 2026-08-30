#!/usr/bin/env bash
# Prove persistence: write data in one session, read it from a brand-new one.
# Runs entirely inside Docker; requires the image from 'bash setup.sh'.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=mdm-mcp:latest
VOLUME=mdm-data

docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "Image not found - run 'bash setup.sh' first."; exit 1; }

docker run -i --rm \
  -v "$VOLUME":/data \
  -v "$(pwd)/scripts":/scripts:ro \
  --entrypoint python \
  "$IMAGE" \
  /scripts/resume_check.py 2>/dev/null
