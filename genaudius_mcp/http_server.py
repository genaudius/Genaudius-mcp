"""
GenAudius MCP — HTTP Server Wrapper
=====================================
Expone el MCP server como una API HTTP/REST para el VPS.
El SaaS (genaudius.com) y Claude Desktop llaman a estos endpoints.

Arquitectura en el VPS:
  Nginx (genaudius.app) → uvicorn → este archivo → tools del MCP

Endpoints:
  GET  /health              → estado del servidor
  GET  /tools               → lista las 26 tools disponibles
  POST /tool/{tool_name}    → ejecuta una tool específica
  POST /batch               → ejecuta múltiples tools en secuencia
  GET  /versions            → versiones del motor GenAudius
  WS   /ws                  → WebSocket para streaming (ChatGAU)
"""

import os
import json
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Importar todos los handlers del MCP
from genaudius_mcp.server import (
    list_tools,
    _gen_audio, _gen_lyrics, _gen_image, _gen_cover,
    _gen_video, _full_production,
    _compose_lyrics, _cl_analyze, _cl_refine,
    _cl_add_to_dataset, _cl_trigger_training,
    _chatgau_chat, _chatgau_quick,
    _chatgau_add_knowledge, _chatgau_status,
    _chatgau_trigger_training,
    _separate_stems, _export_midi, _build_prompt,
    _analytics_summary, _gateway_health,
    _system_status, _list_versions,
    _upload_audio, _trigger_training,
    _store_user_memory, _get_user_memories,
    ACTIVE_VERSION, TIMEOUT, _headers,
    AUDIO_URL, IMAGE_URL, VIDEO_URL, COMPOSER_URL,
    CHATGAU_URL, STEMS_URL, MIDI_URL, BUILDER_URL,
    ANALYTICS_URL, GATEWAY_URL,
)

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genaudius.http")

# ── Auth ──────────────────────────────────────────────────────────
MCP_API_KEY = os.environ.get("GENAUDIUS_API_KEY", "")

def verify_key(x_genaudius_key: str = Header(..., alias="X-GenAudius-Key")):
    if not MCP_API_KEY:
        raise HTTPException(500, "GENAUDIUS_API_KEY no configurada en el servidor")
    if x_genaudius_key != MCP_API_KEY:
        raise HTTPException(401, "API key inválida")
    return x_genaudius_key


def verify_key_optional(
    tool_name: str,
    x_genaudius_key: str | None = Header(None, alias="X-GenAudius-Key"),
):
    """`user_login` no exige X-GenAudius-Key; el resto sí."""
    if tool_name == "user_login":
        return x_genaudius_key
    if not x_genaudius_key:
        raise HTTPException(401, "Header X-GenAudius-Key requerida")
    return verify_key(x_genaudius_key)


# ── FastAPI app ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🎵 GenAudius MCP HTTP Server iniciando...")
    
    # Iniciar motor de memoria MongoDB
    try:
        from genaudius_mcp.memory import memory_engine
        await memory_engine.connect()
    except Exception as e:
        logger.error(f"⚠️ No se pudo iniciar el motor de memoria: {e}")

    logger.info(f"   Dominio: genaudius.app")
    logger.info(f"   Versión: {ACTIVE_VERSION}")
    logger.info(f"   Audio:   {AUDIO_URL[:40]}..." if AUDIO_URL else "   Audio:   ⚠️ no configurado")
    logger.info(f"   Gateway: {GATEWAY_URL[:40]}..." if GATEWAY_URL else "   Gateway: ⚠️ no configurado")
    yield
    logger.info("GenAudius MCP HTTP Server detenido.")

app = FastAPI(
    title="GenAudius MCP API",
    description="Motor de creación musical IA — genaudius.app",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://genaudius.com",
        "https://www.genaudius.com",
        "https://genaudius.studio",
        "https://genaudius.app",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-GenAudius-Key"],
)


# ── /health ───────────────────────────────────────────────────────
class LoginBody(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str


@app.post("/auth/login")
async def auth_login(body: LoginBody):
    """
    Login de usuario sin API key del MCP: reenvía a GENAUDIUS_AUTH_URL (backend AWS u otro).
    El cuerpo debe incluir password y email o username.
    """
    if not body.password.strip():
        raise HTTPException(400, "password requerido")
    if not (body.email or body.username):
        raise HTTPException(400, "email o username requerido")
    args: dict[str, Any] = {"password": body.password.strip()}
    if body.email:
        args["email"] = body.email.strip()
    if body.username:
        args["username"] = body.username.strip()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            results = await _user_login(client, args)
        text = results[0].text if results else ""
        ok = not text.startswith("❌")
        return {"ok": ok, "message": text}
    except Exception as e:
        logger.error("auth_login: %s", e, exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/health")
async def health():
    return {
        "status":  "ok",
        "service": "GenAudius MCP",
        "domain":  "genaudius.app",
        "version": ACTIVE_VERSION,
        "time":    time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ── /tools ────────────────────────────────────────────────────────
@app.get("/tools")
async def get_tools(x_genaudius_key: str = Header(..., alias="X-GenAudius-Key")):
    verify_key(x_genaudius_key)
    tools = await list_tools()
    return {
        "total": len(tools),
        "tools": [
            {
                "name":        t.name,
                "description": t.description[:100] + "...",
                "schema":      t.inputSchema,
            }
            for t in tools
        ],
    }


# ── /tool/{tool_name} ─────────────────────────────────────────────
class ToolRequest(BaseModel):
    arguments: dict[str, Any] = {}

TOOL_DISPATCH = {
    # Audio
    "generate_song":            lambda c, a: _gen_audio(c, a, "song"),
    "generate_bgm":             lambda c, a: _gen_audio(c, a, "bgm"),
    "generate_lyrics":          lambda c, a: asyncio.coroutine(lambda: _gen_lyrics(a))(),
    # Imagen
    "generate_image":           lambda c, a: _gen_image(c, a),
    "generate_cover_art":       lambda c, a: _gen_cover(c, a),
    # Video
    "generate_video":           lambda c, a: _gen_video(c, a),
    "create_full_production":   lambda c, a: _full_production(c, a),
    # Composer Lyric
    "compose_lyrics":           lambda c, a: _compose_lyrics(c, a),
    "analyze_prompt":           lambda c, a: _cl_analyze(c, a),
    "refine_lyrics":            lambda c, a: _cl_refine(c, a),
    "add_lyric_to_dataset":     lambda c, a: _cl_add_to_dataset(a),
    "trigger_composer_training":lambda c, a: _cl_trigger_training(c, a),
    # ChatGAU
    "chatgau_support":          lambda c, a: _chatgau_chat(c, a),
    "chatgau_quick":            lambda c, a: _chatgau_quick(c, a),
    "chatgau_add_knowledge":    lambda c, a: _chatgau_add_knowledge(c, a),
    "chatgau_status":           lambda c, a: _chatgau_status(c),
    "trigger_chatgau_training": lambda c, a: _chatgau_trigger_training(a),
    # Enterprise
    "separate_stems":           lambda c, a: _separate_stems(c, a),
    "export_midi":              lambda c, a: _export_midi(c, a),
    "build_prompt":             lambda c, a: _build_prompt(c, a),
    "analytics_summary":        lambda c, a: _analytics_summary(c, a),
    "gateway_health":           lambda c, a: _gateway_health(c),
    # Sistema
    "get_system_status":        lambda c, a: _system_status(c),
    "list_versions":            lambda c, a: _list_versions(c),
    "upload_audio_to_r2":       lambda c, a: asyncio.coroutine(lambda: _upload_audio(a))(),
    "trigger_training":         lambda c, a: _trigger_training(c, a),
    "user_login":               lambda c, a: _user_login(c, a),
    # Memoria GAU
    "store_user_memory":        lambda c, a: _store_user_memory(a),
    "get_user_memories":         lambda c, a: _get_user_memories(a),
}

@app.post("/tool/{tool_name}")
async def execute_tool(
    tool_name: str,
    request: ToolRequest,
    x_genaudius_key: str | None = Header(None, alias="X-GenAudius-Key"),
):
    verify_key_optional(tool_name, x_genaudius_key)

    if tool_name not in TOOL_DISPATCH:
        raise HTTPException(404, f"Tool '{tool_name}' no existe. GET /tools para ver la lista.")

    handler = TOOL_DISPATCH[tool_name]
    t0 = time.time()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            results = await handler(client, request.arguments)

        duration_ms = int((time.time() - t0) * 1000)
        logger.info(f"✅ {tool_name} — {duration_ms}ms")

        # Memorizar interacción automáticamente en MongoDB
        try:
            from genaudius_mcp.memory import memory_engine
            if memory_engine.enabled:
                asyncio.create_task(memory_engine.log_interaction(
                    user_id=request.arguments.get("user_id", "global_user"),
                    tool_name=tool_name,
                    arguments=request.arguments,
                    result=results[0].text if results else ""
                ))
        except Exception:
            pass

        return {
            "status":      "ok",
            "tool":        tool_name,
            "duration_ms": duration_ms,
            "result":      results[0].text if results else "",
        }

    except httpx.TimeoutException:
        raise HTTPException(504, f"Timeout ejecutando '{tool_name}' (>{TIMEOUT}s)")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Error del motor: {e.response.text[:300]}")
    except Exception as e:
        logger.error(f"❌ {tool_name}: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ── /batch ────────────────────────────────────────────────────────
class BatchStep(BaseModel):
    tool:      str
    arguments: dict[str, Any] = {}
    pass_result_as: str = ""   # si no vacío, pasa result del paso anterior como este argumento

class BatchRequest(BaseModel):
    steps: list[BatchStep]
    stop_on_error: bool = True

@app.post("/batch")
async def batch_execute(
    request: BatchRequest,
    x_genaudius_key: str = Header(..., alias="X-GenAudius-Key"),
):
    """
    Ejecuta múltiples tools en secuencia.
    Útil para flujos como: analyze_prompt → compose_lyrics → generate_song → generate_video
    """
    verify_key(x_genaudius_key)

    results = []
    last_result = ""

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for i, step in enumerate(request.steps):
            if step.tool not in TOOL_DISPATCH:
                error = {"step": i, "tool": step.tool, "error": "Tool no encontrada"}
                if request.stop_on_error:
                    raise HTTPException(404, error)
                results.append(error)
                continue

            # Inyectar resultado anterior si se especificó
            args = dict(step.arguments)
            if step.pass_result_as and last_result:
                args[step.pass_result_as] = last_result

            try:
                t0 = time.time()
                handler = TOOL_DISPATCH[step.tool]
                tool_results = await handler(client, args)
                last_result = tool_results[0].text if tool_results else ""
                results.append({
                    "step":        i,
                    "tool":        step.tool,
                    "status":      "ok",
                    "duration_ms": int((time.time() - t0) * 1000),
                    "result":      last_result[:500],   # truncar para el response
                })
            except Exception as e:
                error = {"step": i, "tool": step.tool, "error": str(e)}
                if request.stop_on_error:
                    raise HTTPException(500, {"completed": results, "failed": error})
                results.append(error)

    return {
        "status":     "ok",
        "steps_total": len(request.steps),
        "steps_ok":   sum(1 for r in results if r.get("status") == "ok"),
        "results":    results,
    }


# ── WebSocket /ws (ChatGAU streaming) ────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para streaming de ChatGAU.
    El frontend genaudius.com conecta aquí para chat en tiempo real.

    Protocolo:
      Cliente envía: {"tool": "chatgau_support", "arguments": {...}, "key": "..."}
      Servidor responde: chunks de texto hasta {"done": true}
    """
    await websocket.accept()
    logger.info("WebSocket conectado")

    try:
        while True:
            data = await websocket.receive_json()

            # Auth
            if data.get("key") != MCP_API_KEY:
                await websocket.send_json({"error": "API key inválida", "done": True})
                continue

            tool = data.get("tool", "chatgau_support")
            args = data.get("arguments", {})

            if tool not in ("chatgau_support", "chatgau_quick"):
                await websocket.send_json({"error": f"Solo chatgau tools via WS", "done": True})
                continue

            # Llamar al endpoint de streaming de ChatGAU
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    async with client.stream(
                        "POST",
                        f"{CHATGAU_URL}/chat/stream",
                        json=args,
                        headers=_headers(),
                        timeout=TIMEOUT,
                    ) as response:
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                chunk_data = line[6:]
                                if chunk_data == "[DONE]":
                                    await websocket.send_json({"done": True})
                                    break
                                try:
                                    chunk = json.loads(chunk_data)
                                    await websocket.send_json(chunk)
                                except json.JSONDecodeError:
                                    pass

            except Exception as e:
                await websocket.send_json({"error": str(e), "done": True})

    except WebSocketDisconnect:
        logger.info("WebSocket desconectado")


# ── /versions ─────────────────────────────────────────────────────
@app.get("/versions")
async def get_versions(x_genaudius_key: str = Header(..., alias="X-GenAudius-Key")):
    verify_key(x_genaudius_key)
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{AUDIO_URL}/versions", headers=_headers())
            return resp.json()
        except Exception:
            return {
                "active": ACTIVE_VERSION,
                "available": ["GenAudius_V1", "GenAudius_V2", "GenAudius_V3"],
            }
