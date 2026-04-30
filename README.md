# GenAudius v1 — monorepo (MCP + Modal + ChatGAU)

Repositorio de trabajo para **GenAudius / GAU**: el **servidor MCP** vive aquí y está pensado para ejecutarse en un **VPS Hostinger**. El **backend y frontend** de producto van en **AWS**; los **datasets y artefactos de entrenamiento** en **Cloudflare R2**; la **GPU y orquestación** en **Modal**.

## Arquitectura objetivo

```
  Usuarios (Claude / Agents / SaaS)
           │
           ▼
  ┌──────────────────────┐
  │  VPS Hostinger       │  proceso `genaudius-mcp` (stdio o HTTP bridge si lo añades)
  │  (este repo + vps/)  │
  └──────────┬───────────┘
             │ HTTPS
             ▼
  ┌──────────────────────┐     ┌─────────────────┐
  │  AWS                 │     │  Modal          │
  │  API Gateway / ALB   │────▶│  api.py, image,│
  │  + FastAPI + Front   │     │  video, composer│
  └──────────────────────┘     │  ChatGAU, etc.  │
             │                  └────────┬────────┘
             │                           │
             ▼                           ▼
  ┌──────────────────────────────────────────────┐
  │  Cloudflare R2 (datasets, outputs, stems)    │
  └──────────────────────────────────────────────┘
```

- **MCP (`mcp/`)**: herramientas para generación, stems, MIDI, Composer Lyric y **ChatGAU** (soporte general).
- **Engine v1.0**: Soporte nativo para **RunPod** y ejecución local; compatible con la API de Kie/Suno.
- **VPS (`vps/`)**: instrucciones para systemd, variables de entorno y despliegue en Hostinger.

## Variables de Entorno (IMPORTANTE)
Para que el MCP funcione con el nuevo motor:
- `GENAUDIUS_API_BASE_URL`: URL de tu API (ej: `https://api.genaudius.studio`).
- `GAU_API_KEY`: Tu llave maestra de seguridad (definida en el motor).
- `GENAUDIUS_API_KEY`: Llave para autenticar el acceso al MCP.

## Instalación del MCP (en el VPS)

```bash
cd /ruta/al/repo/mcp
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
```

Comando de entrada: **`genaudius-mcp`**. Variables: copia `claude_desktop_config.template.json` y adapta las URLs (pueden ser dominios AWS que proxeen a Modal).

## Desarrollo local (Windows)

Ruta típica del repo: `E:\genaudius-backend-v7\genaudiusv1-mcp`.

## Tests (paquete MCP)

```bash
cd mcp
pip install pytest pytest-asyncio
pytest tests/ -q
```

## Licencia

MIT (ajusta según tu política).
