#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# GenAudius MCP — Deploy Script VPS Hostinger
# Dominio: genaudius.cloud
#
# Uso (desde tu máquina local):
#   chmod +x vps/scripts/deploy.sh
#   VPS_IP=123.456.789.0 ./vps/scripts/deploy.sh
#
# O directamente en el VPS:
#   bash <(curl -sL https://raw.githubusercontent.com/tu-repo/main/vps/scripts/deploy.sh)
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colores ───────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║        GenAudius MCP — VPS Deploy               ║"
echo "║        genaudius.cloud — Hostinger                ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Verificar OS ───────────────────────────────────────────────
info "Verificando sistema..."
if [ ! -f /etc/debian_version ] && [ ! -f /etc/ubuntu_version ]; then
    warn "Este script está optimizado para Ubuntu/Debian."
fi

OS=$(lsb_release -si 2>/dev/null || echo "Unknown")
log "Sistema: $OS $(lsb_release -sr 2>/dev/null || echo '')"

# ── 2. Actualizar sistema ─────────────────────────────────────────
info "Actualizando paquetes..."
apt-get update -qq
apt-get upgrade -y -qq
log "Sistema actualizado"

# ── 3. Instalar Docker ────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    info "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log "Docker instalado: $(docker --version)"
else
    log "Docker ya instalado: $(docker --version)"
fi

# ── 4. Instalar Docker Compose ────────────────────────────────────
if ! command -v docker-compose &>/dev/null; then
    info "Instalando Docker Compose..."
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log "Docker Compose: $(docker-compose --version)"
else
    log "Docker Compose ya instalado"
fi

# ── 5. Configurar firewall ────────────────────────────────────────
info "Configurando firewall UFW..."
apt-get install -y -qq ufw
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    comment "SSH"
ufw allow 80/tcp    comment "HTTP"
ufw allow 443/tcp   comment "HTTPS"
ufw --force enable
log "Firewall configurado (22, 80, 443)"

# ── 6. Crear directorio del proyecto ─────────────────────────────
DEPLOY_DIR="/opt/genaudius"
info "Configurando directorio: $DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# ── 7. Clonar o actualizar repo ───────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/tu-usuario/genaudius-backend.git}"

if [ -d "$DEPLOY_DIR/.git" ]; then
    info "Actualizando repositorio..."
    git pull origin main
    log "Repositorio actualizado"
else
    info "Clonando repositorio..."
    git clone "$REPO_URL" .
    log "Repositorio clonado"
fi

# ── 8. Configurar .env ────────────────────────────────────────────
if [ ! -f "$DEPLOY_DIR/vps/.env" ]; then
    info "Configurando variables de entorno..."

    cp vps/.env.example vps/.env

    echo ""
    warn "⚠️  IMPORTANTE: Edita el archivo de configuración:"
    echo "    nano $DEPLOY_DIR/vps/.env"
    echo ""
    echo "    Debes configurar:"
    echo "    • GENAUDIUS_API_KEY   — clave privada del MCP"
    echo "    • MODAL_*_URL         — URLs de genaudius.studio"
    echo "    • MODAL_WEBHOOK_TOKEN — token de Modal"
    echo "    • SSL_EMAIL           — tu email para Let's Encrypt"
    echo ""
    read -p "Presiona ENTER cuando hayas editado el .env..."

    # Verificar que se configuró
    if grep -q "CAMBIAR_POR" "$DEPLOY_DIR/vps/.env"; then
        err "El .env aún tiene valores por defecto. Edítalo primero."
    fi
else
    log ".env ya existe"
fi

# ── 9. Obtener certificado SSL ────────────────────────────────────
info "Configurando SSL para genaudius.cloud..."

cd "$DEPLOY_DIR/vps"

# Primero levantar nginx en modo HTTP para el challenge
docker-compose up -d nginx 2>/dev/null || true
sleep 5

# Obtener certificado
docker-compose --profile ssl run --rm certbot || {
    warn "SSL no pudo configurarse automáticamente."
    warn "Ejecuta manualmente después de que el DNS de genaudius.cloud apunte a este VPS:"
    warn "  cd $DEPLOY_DIR/vps && docker-compose --profile ssl run --rm certbot"
}

log "SSL configurado"

# ── 10. Build y levantar servicios ────────────────────────────────
info "Construyendo imagen del MCP..."
docker-compose build --no-cache mcp_server
log "Imagen construida"

info "Iniciando servicios..."
docker-compose up -d
log "Servicios iniciados"

# ── 11. Verificar que todo está corriendo ─────────────────────────
info "Verificando servicios..."
sleep 10

if docker-compose ps | grep -q "Up"; then
    log "Servicios corriendo:"
    docker-compose ps
else
    err "Algunos servicios fallaron. Revisa: docker-compose logs"
fi

# ── 12. Test de salud ─────────────────────────────────────────────
info "Verificando health endpoint..."
sleep 5

if curl -sf "http://localhost/health" > /dev/null 2>&1; then
    log "Health check OK"
elif curl -sf "https://genaudius.cloud/health" > /dev/null 2>&1; then
    log "Health check HTTPS OK"
else
    warn "Health check no responde aún. Espera 30s y prueba manualmente:"
    warn "  curl https://genaudius.cloud/health"
fi

# ── 13. Configurar renovación automática SSL ──────────────────────
info "Configurando renovación automática de SSL..."
cp "$DEPLOY_DIR/vps/scripts/renew_ssl.sh" /etc/cron.daily/genaudius-ssl-renew
chmod +x /etc/cron.daily/genaudius-ssl-renew
log "Renovación automática configurada (diaria)"

# ── 14. Configurar auto-restart ───────────────────────────────────
info "Configurando systemd service..."
cat > /etc/systemd/system/genaudius-mcp.service << 'SYSTEMD'
[Unit]
Description=GenAudius MCP Server (genaudius.cloud)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/genaudius/vps
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable genaudius-mcp
log "Systemd service configurado"

# ── Resumen final ─────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          ✅ Deploy completado                   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
log "MCP Server:  https://genaudius.cloud"
log "API Gateway: https://api.genaudius.cloud/v1/"
log "Health:      https://genaudius.cloud/health"
log "Docs:        https://genaudius.cloud/docs"
echo ""
info "Logs en tiempo real:    docker-compose -f $DEPLOY_DIR/vps/docker-compose.yml logs -f"
info "Reiniciar MCP:          systemctl restart genaudius-mcp"
info "Ver estado:             docker-compose -f $DEPLOY_DIR/vps/docker-compose.yml ps"
echo ""
warn "Configura en el SaaS (genaudius.com):"
warn "  MCP_BASE_URL = https://api.genaudius.cloud"
warn "  X-GenAudius-Key = (el valor de GENAUDIUS_API_KEY en el .env)"
