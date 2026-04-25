# MCP en VPS Hostinger

El proceso **`genaudius-mcp`** suele ejecutarse como **stdio** para Claude Desktop o un bridge SSE. En servidor Linux (Hostinger VPS) lo habitual es:

1. Clonar este repo en el VPS (`git clone …`).
2. Crear venv e instalar el paquete: `cd …/mcp && python3 -m venv .venv && . .venv/bin/activate && pip install -e .`
3. Definir variables de entorno (ver `genaudius-mcp.env.example`).

## Variables importantes

| Variable | Uso |
|----------|-----|
| `GENAUDIUS_API_KEY` | Clave interna (no la subas a git) |
| `MODAL_AUDIO_URL` | Base URL de la API de audio (Modal o AWS→Modal) |
| `MODAL_WEBHOOK_TOKEN` | Mismo Bearer que `gen-audius-secrets` en Modal |
| `MODAL_CHATGAU_URL` | API ChatGAU (soporte) |
| `MODAL_*_URL` | Opcionales según módulos que despliegues |

Las URLs pueden apuntar a **API Gateway en AWS** que reenvíe a las apps Modal; el MCP solo hace HTTP.

## systemd (ejemplo)

Archivo de servicio: `genaudius-mcp.service` (ajusta `User`, `WorkingDirectory` y rutas):

```ini
[Unit]
Description=GenAudius MCP (stdio bridge / worker)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/genaudiusv1-mcp/mcp
EnvironmentFile=/etc/genaudius/mcp.env
ExecStart=/opt/genaudiusv1-mcp/mcp/.venv/bin/genaudius-mcp
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Si expones el MCP vía **HTTP** (otro binario o proxy), cambia `ExecStart` y usa `nginx`/`Caddy` con TLS.

## Seguridad

- No commitear `.env` ni claves.
- Restringir acceso SSH al VPS; actualizar el sistema.
- Rotar `GENAUDIUS_API_KEY` y tokens Modal si se filtran logs.
