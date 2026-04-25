#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# GenAudius MCP — Update Script (zero downtime)
# Uso: ./vps/scripts/update.sh
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

cd /opt/genaudius

info "Actualizando GenAudius MCP..."

# Pull cambios
git pull origin main
log "Código actualizado"

# Rebuild imagen
cd vps
docker-compose build --no-cache mcp_server
log "Imagen reconstruida"

# Rolling restart — zero downtime
docker-compose up -d --no-deps --force-recreate mcp_server
log "MCP Server reiniciado"

# Reload nginx (no restart — no downtime)
docker-compose exec nginx nginx -s reload
log "Nginx recargado"

# Health check
sleep 5
if curl -sf "https://genaudius.cloud/health" > /dev/null; then
    log "✅ genaudius.cloud respondiendo correctamente"
else
    echo "⚠️  Health check falló. Revisa: docker-compose logs mcp_server"
fi

log "Update completado"
