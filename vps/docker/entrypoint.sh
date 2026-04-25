#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# GenAudius MCP — Entrypoint VPS
# Expone el MCP server como HTTP FastAPI
# para que Nginx pueda hacer proxy y el SaaS pueda llamarlo via REST
# ═══════════════════════════════════════════════════════════════════

set -e

echo "🎵 GenAudius MCP Server — genaudius.app"
echo "   Version: ${GENAUDIUS_VERSION:-GenAudius_V1}"
echo "   Starting HTTP wrapper..."

exec uvicorn genaudius_mcp.http_server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info \
    --access-log \
    --log-config /app/genaudius_mcp/logging.json
