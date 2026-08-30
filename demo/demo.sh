#!/usr/bin/env bash
# 30-second demo of the MDM MCP server through a real MCP client session.
# Requires the image from 'bash setup.sh'. Runs entirely inside Docker.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=mdm-mcp:latest
VOLUME=mdm-data

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed. Run 'bash setup.sh' after installing it."
  exit 1
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image $IMAGE not found - run 'bash setup.sh' first."
  exit 1
fi

echo "Recruiter walkthrough: schema -> CSV import with validation -> fuzzy search"
echo "-> filtered shortlist -> bulk update with dry-run -> summary"
echo
docker run -i --rm \
  -v "$VOLUME":/data \
  -v "$(pwd)/demo":/demo:ro \
  --entrypoint python \
  "$IMAGE" \
  /demo/demo.py 2>/dev/null
