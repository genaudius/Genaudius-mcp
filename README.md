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
- **ChatGAU (`chatgau/`)**: dataset y scripts del asistente de soporte; expuesto vía `modal/chatgau_api.py` (URL `MODAL_CHATGAU_URL`).
- **Modal (`modal/`)**: apps de inferencia y entrenamiento; despliegue con `modal deploy`.
- **VPS (`vps/`)**: instrucciones para systemd, variables de entorno y despliegue en Hostinger.

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
