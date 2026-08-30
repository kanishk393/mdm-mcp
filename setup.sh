#!/usr/bin/env bash
# One-command setup for the MDM MCP server.
# Builds the Docker image, smoke-tests the MCP handshake, and generates
# opencode.json + .mcp.json so OpenCode / Claude Code attach out of the box.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=mdm-mcp:latest
VOLUME=mdm-data

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed."
  echo "  macOS/Windows: install Docker Desktop -> https://www.docker.com/products/docker-desktop"
  echo "  Linux:         curl -fsSL https://get.docker.com | sh"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is installed but not running. Start Docker Desktop and re-run."
  exit 1
fi

echo "==> Building $IMAGE (first build downloads the Python image, ~1-2 min)"
docker build -t "$IMAGE" .

echo "==> Smoke test: MCP handshake over stdio (exactly what clients do)"
HANDSHAKE='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"setup","version":"0"}}}'
RESPONSE=$(printf '%s\n' "$HANDSHAKE" | docker run -i --rm -v "$VOLUME":/data "$IMAGE" 2>/dev/null || true)
if echo "$RESPONSE" | grep -q '"serverInfo"'; then
  SERVER_NAME=$(echo "$RESPONSE" | sed -n 's/.*"serverInfo":{"name":"\([^"]*\)".*/\1/p')
  echo "    handshake OK (server: $SERVER_NAME)"
else
  echo "ERROR: smoke test failed. Raw response:"
  echo "$RESPONSE"
  exit 1
fi

echo "==> Generating opencode.json and .mcp.json"
cat > opencode.json <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "mcp": {
    "master-data": {
      "type": "local",
      "command": ["docker", "run", "-i", "--rm", "-v", "$VOLUME:/data", "$IMAGE"],
      "enabled": true
    }
  }
}
EOF
cat > .mcp.json <<EOF
{
  "mcpServers": {
    "master-data": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "$VOLUME:/data", "$IMAGE"]
    }
  }
}
EOF

cat <<'NOTE'

Setup complete. Attach your MCP client:

  OpenCode:     start "opencode" in this folder - the config is already in place.
  Claude Code:  run "claude" in this folder and approve the "master-data" project
                server when prompted. (Or run:
                  claude mcp add master-data -- docker run -i --rm -v mdm-data:/data mdm-mcp:latest
                )

Notes:
  - All data is stored in the Docker volume "mdm-data" and survives restarts.
  - Start fresh anytime with:  docker volume rm mdm-data
  - Re-run this script anytime - it is safe and fast after the first build.
NOTE
