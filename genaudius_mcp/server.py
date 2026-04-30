"""
GenAudius MCP Server — v7 (GAU + multimedia + Composer + ChatGAU + enterprise)
===============================================================================
Diseñado para correr en **VPS (p. ej. Hostinger)** y llamar a APIs en **AWS** (proxy a Modal)
o directamente a **Modal**. Datasets / outputs en **R2**; cómputo en **Modal**.

Incluye **ChatGAU** (`MODAL_CHATGAU_URL`): soporte general para el departamento de soporte.

Solo son obligatorias `GENAUDIUS_API_KEY` + `MODAL_AUDIO_URL` + `MODAL_WEBHOOK_TOKEN`.
El resto de `MODAL_*_URL` se valida al usar la herramienta correspondiente.

GAU training: `trigger_training` → POST `{MODAL_AUDIO_URL}/training/trigger`.

Variables típicas:
  GENAUDIUS_API_KEY, MODAL_WEBHOOK_TOKEN, MODAL_AUDIO_URL (mínimo)
  MODAL_IMAGE_URL, MODAL_VIDEO_URL, MODAL_COMPOSER_URL
  MODAL_CHATGAU_URL (ChatGAU)
  MODAL_STEMS_URL, MODAL_MIDI_URL, MODAL_BUILDER_URL, MODAL_ANALYTICS_URL, MODAL_GATEWAY_URL
  GENAUDIUS_VERSION, TIME_OUT_SECONDS
  GENAUDIUS_AUTH_URL (opcional) — URL del login en tu API (AWS); tool `user_login` y POST /auth/login
"""

import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Any

import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genaudius-mcp")

# GenAudius Engine v1.0 (RunPod / Local / VPS)
API_BASE_URL   = os.environ.get("GENAUDIUS_API_BASE_URL", "https://api.genaudius.studio")
MCP_API_KEY    = os.environ.get("GENAUDIUS_API_KEY", "") # Key used to call the MCP
GAU_API_KEY    = os.environ.get("GAU_API_KEY", "gau_master_secure_2026") # Key used to call the Engine
TIMEOUT        = int(os.environ.get("TIME_OUT_SECONDS", "600"))
ACTIVE_VERSION = os.environ.get("GENAUDIUS_VERSION", "MusicGAU-V1")
AUTH_LOGIN_URL = os.environ.get("GENAUDIUS_AUTH_URL", "").strip()

# Legacy URLs (for backward compatibility if needed)
AUDIO_URL      = os.environ.get("MODAL_AUDIO_URL", f"{API_BASE_URL}/api/v1")
STEMS_URL      = os.environ.get("MODAL_STEMS_URL", f"{API_BASE_URL}/api/v1/vocal-removal")
MIDI_URL       = os.environ.get("MODAL_MIDI_URL", f"{API_BASE_URL}/api/v1")
IMAGE_URL      = os.environ.get("MODAL_IMAGE_URL", "")
VIDEO_URL      = os.environ.get("MODAL_VIDEO_URL", "")
CHATGAU_URL    = os.environ.get("MODAL_CHATGAU_URL", "")

GENRE_LIST = ["bachata", "rock", "pop", "salsa", "reggaeton", "jazz", "lofi", "electronic"]

def _headers():
    return {
        "x-api-key": GAU_API_KEY,
        "Content-Type": "application/json",
        "X-GenAudius-Source": "mcp-v7-engine-v1",
    }

app = Server("genaudius-mcp")


def _auth_error():
    """
    Solo exige lo mínimo para GAU (audio). El resto de MODAL_* son opcionales por tool;
    puedes apuntarlos a rutas en AWS (API Gateway) que reenvíen a Modal.
    """
    missing = [k for k, v in {
        "GENAUDIUS_API_KEY": MCP_API_KEY,
        "MODAL_AUDIO_URL": AUDIO_URL,
    }.items() if not v]
    if missing:
        return types.TextContent(
            type="text",
            text=f"❌ Variables mínimas faltantes: {', '.join(missing)}. Opcionales según tool: MODAL_IMAGE_URL, MODAL_VIDEO_URL, MODAL_COMPOSER_URL, MODAL_CHATGAU_URL, MODAL_GATEWAY_URL, …",
        )
    return None


def _need_url(url: str, name: str) -> types.TextContent | None:
    if not (url or "").strip():
        return types.TextContent(
            type="text",
            text=f"❌ Falta {name} en el entorno del MCP (VPS). Configúrala en systemd o en Claude Desktop.",
        )
    return None


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── AUDIO ─────────────────────────────────────────────────────────────
        types.Tool(
            name="generate_song",
            description=f"🎶 Genera canción WAV con modelo GAU. Versión activa: {ACTIVE_VERSION}.",
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt":        {"type": "string"},
                    "genre":         {"type": "string", "enum": GENRE_LIST},
                    "seconds_total": {"type": "number", "default": 30},
                    "steps":         {"type": "integer", "default": 100},
                    "cfg_scale":     {"type": "number", "default": 6.0},
                    "seed":          {"type": "integer", "default": -1},
                    "version":       {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),
        types.Tool(
            name="generate_bgm",
            description="🎼 Genera música de fondo instrumental (sin voces). Para videos, streams, podcasts.",
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt":        {"type": "string"},
                    "genre":         {"type": "string", "enum": GENRE_LIST},
                    "seconds_total": {"type": "number", "default": 60},
                    "steps":         {"type": "integer", "default": 80},
                    "seed":          {"type": "integer", "default": -1},
                    "version":       {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),
        types.Tool(
            name="generate_lyrics",
            description="✍️ Genera letra de canción en cualquier idioma y género. Sin GPU.",
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt":    {"type": "string"},
                    "genre":     {"type": "string", "enum": GENRE_LIST},
                    "language":  {"type": "string", "default": "Español"},
                    "structure": {"type": "string", "default": "Verso-Coro-Verso-Coro-Puente-Coro"},
                },
            },
        ),

        # ── IMAGEN ────────────────────────────────────────────────────────────
        types.Tool(
            name="generate_image",
            description="🖼️ Genera imagen con FLUX.1-schnell o SDXL. Estilos musicales predefinidos por género.",
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt":  {"type": "string"},
                    "style":   {"type": "string", "enum": GENRE_LIST + ["auto", "default"], "default": "auto"},
                    "model":   {"type": "string", "enum": ["flux", "sdxl"], "default": "flux"},
                    "width":   {"type": "integer", "default": 1024},
                    "height":  {"type": "integer", "default": 1024},
                    "steps":   {"type": "integer", "default": 4},
                    "seed":    {"type": "integer", "default": -1},
                    "version": {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),
        types.Tool(
            name="generate_cover_art",
            description="🎨 Genera cover art optimizado para álbum/single. Usa el mismo prompt de la canción.",
            inputSchema={
                "type": "object",
                "required": ["song_prompt"],
                "properties": {
                    "song_prompt":  {"type": "string"},
                    "genre":        {"type": "string", "enum": GENRE_LIST + ["default"], "default": "default"},
                    "style":        {"type": "string", "enum": ["album_cover", "single_art", "lyric_card"], "default": "album_cover"},
                    "artist_name":  {"type": "string", "default": "GenAudius"},
                    "version":      {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),

        # ── VIDEO ─────────────────────────────────────────────────────────────
        types.Tool(
            name="generate_video",
            description=(
                "🎬 Combina audio WAV + imagen PNG en video MP4. "
                "Agrega waveform visualizer y título. "
                "Formatos: 1080x1080 (Instagram), 1920x1080 (YouTube), 1080x1920 (TikTok)."
            ),
            inputSchema={
                "type": "object",
                "required": ["audio_r2_key", "image_r2_key"],
                "properties": {
                    "audio_r2_key": {"type": "string", "description": "r2_key del WAV generado"},
                    "image_r2_key": {"type": "string", "description": "r2_key del PNG generado"},
                    "title":        {"type": "string"},
                    "artist":       {"type": "string", "default": "GenAudius"},
                    "resolution":   {"type": "string", "enum": ["1080x1080", "1920x1080", "1080x1920"], "default": "1080x1080"},
                    "visualizer":   {"type": "boolean", "default": True},
                    "version":      {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),

        # ── MAESTRO ───────────────────────────────────────────────────────────
        types.Tool(
            name="create_full_production",
            description=(
                "🚀 PRODUCCIÓN COMPLETA en un comando. "
                "Genera automáticamente: canción WAV + cover art PNG + video MP4. "
                "Solo necesitas el prompt y género. Devuelve 3 URLs de descarga."
            ),
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt":        {"type": "string", "description": "Ej: 'bachata romántica sobre el atardecer en el mar'"},
                    "genre":         {"type": "string", "enum": GENRE_LIST, "default": "bachata"},
                    "title":         {"type": "string"},
                    "artist":        {"type": "string", "default": "GenAudius"},
                    "audio_seconds": {"type": "number", "default": 30},
                    "resolution":    {"type": "string", "enum": ["1080x1080", "1920x1080", "1080x1920"], "default": "1080x1080"},
                    "version":       {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),

        # ── SISTEMA / AUTH ─────────────────────────────────────────────────────
        types.Tool(
            name="user_login",
            description=(
                "🔐 Autenticación de usuario vía MCP. Envía email (o username) y password; "
                "el MCP reenvía a GENAUDIUS_AUTH_URL (tu API en AWS). "
                "Si el backend devuelve access_token/token/jwt, se muestra para usarlo en el SaaS o en headers."
            ),
            inputSchema={
                "type": "object",
                "required": ["password"],
                "properties": {
                    "email":    {"type": "string", "description": "Correo del usuario"},
                    "username": {"type": "string", "description": "Alternativa si tu API usa username en lugar de email"},
                    "password": {"type": "string", "description": "Contraseña"},
                },
            },
        ),
        types.Tool(
            name="get_system_status",
            description="📊 Estado completo: versiones, modelos disponibles, APIs activas.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_versions",
            description="🗂️ Lista versiones del motor (V1, V2, V3).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="upload_audio_to_r2",
            description="📤 Sube audio local al dataset de entrenamiento en R2.",
            inputSchema={
                "type": "object",
                "required": ["local_path", "genre"],
                "properties": {
                    "local_path":   {"type": "string"},
                    "genre":        {"type": "string", "enum": GENRE_LIST},
                    "dataset_type": {"type": "string", "enum": ["genres_15s", "genres_original"], "default": "genres_15s"},
                    "version":      {"type": "string", "default": ACTIVE_VERSION},
                },
            },
        ),
        types.Tool(
            name="trigger_training",
            description=(
                "🚀 Encola entrenamiento GAU vía POST /training/trigger en la API de audio "
                "(Modal train_gau / app genaudius-v1-gau-train)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "version":                {"type": "string", "default": ACTIVE_VERSION},
                    "genres":                 {"type": "array", "items": {"type": "string"}},
                    "resume_from_checkpoint": {"type": "boolean", "default": True},
                    "resume_ckpt_path":       {
                        "type": "string",
                        "default": "",
                        "description": "Ruta .ckpt en volumen Modal; vacío usa GEANAUDIUS_WEBHOOK_RESUME_CKPT en el servidor",
                    },
                },
            },
        ),

        # ── COMPOSER LYRIC ────────────────────────────────────────────────────
        types.Tool(
            name="compose_lyrics",
            description=(
                "🖊️ COMPOSER LYRIC — Genera letras profesionales con el modelo fine-tuneado "
                "en tu estilo musical. Más profundo e inteligente que generate_lyrics. "
                "Analiza el prompt, planifica la estructura y compone sección por sección."
            ),
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt":           {"type": "string", "description": "Describe la canción con detalle"},
                    "genre":            {"type": "string", "enum": GENRE_LIST, "default": "bachata"},
                    "mood":             {"type": "string", "description": "Estado emocional: melancólico, alegre, sensual..."},
                    "theme":            {"type": "string", "description": "Tema central de la letra"},
                    "bpm":              {"type": "integer", "default": 130},
                    "language":         {"type": "string", "default": "Español"},
                    "mode":             {"type": "string", "enum": ["professional", "creative", "experimental"],
                                         "default": "professional",
                                         "description": "professional=más controlado, creative=más libre, experimental=más arriesgado"},
                    "custom_structure": {"type": "array", "items": {"type": "string"},
                                         "description": "Estructura personalizada, ej: ['Verso 1','Coro','Verso 2','Coro','Puente','Coro']"},
                    "max_tokens":       {"type": "integer", "default": 1200},
                    "seed":             {"type": "integer", "default": -1},
                },
            },
        ),
        types.Tool(
            name="analyze_prompt",
            description=(
                "🔍 COMPOSER LYRIC — Analiza un prompt musical ANTES de componer. "
                "Devuelve: mood detectado, estructura recomendada, metáforas clave, "
                "clichés a evitar, y la primera línea propuesta. "
                "Úsalo para planificar antes de llamar a compose_lyrics."
            ),
            inputSchema={
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt": {"type": "string"},
                    "genre":  {"type": "string", "enum": GENRE_LIST, "default": "bachata"},
                },
            },
        ),
        types.Tool(
            name="refine_lyrics",
            description=(
                "✨ COMPOSER LYRIC — Mejora o reescribe una letra existente. "
                "Pasa la letra original y las instrucciones de mejora (ej: 'el coro necesita más impacto', "
                "'cambia las metáforas del verso 2', 'hazla más melancólica'). "
                "El modelo reescribe manteniendo el espíritu original."
            ),
            inputSchema={
                "type": "object",
                "required": ["original_lyrics", "instructions"],
                "properties": {
                    "original_lyrics": {"type": "string", "description": "La letra actual completa"},
                    "instructions":    {"type": "string", "description": "Qué mejorar o cambiar"},
                    "genre":           {"type": "string", "enum": GENRE_LIST, "default": "bachata"},
                    "max_tokens":      {"type": "integer", "default": 1200},
                },
            },
        ),
        types.Tool(
            name="add_lyric_to_dataset",
            description=(
                "📚 COMPOSER LYRIC — Agrega una letra nueva al dataset de entrenamiento. "
                "Cada letra que agregas mejora el modelo. Después de agregar, "
                "usa trigger_composer_training para re-entrenar."
            ),
            inputSchema={
                "type": "object",
                "required": ["lyrics_text", "genre"],
                "properties": {
                    "lyrics_text": {"type": "string", "description": "La letra completa con etiquetas [Verso 1], [Coro], etc."},
                    "genre":       {"type": "string", "enum": GENRE_LIST},
                    "mood":        {"type": "string", "default": "romántico"},
                    "theme":       {"type": "string", "default": "amor"},
                    "bpm":         {"type": "integer", "default": 130},
                    "prompt":      {"type": "string", "description": "Descripción de la canción (para el dataset)"},
                    "quality":     {"type": "integer", "default": 9, "description": "Calidad 1-10"},
                },
            },
        ),
        # ── ENTERPRISE ───────────────────────────────────────────────────────
        types.Tool(
            name="separate_stems",
            description="🎚️ Separa un audio WAV en stems individuales (vocals, drums, bass, other) usando Demucs. Devuelve URLs de descarga para cada stem desde R2. Ideal para productores que quieren editar en su DAW.",
            inputSchema={"type":"object","required":["audio_r2_key"],"properties":{
                "audio_r2_key":{"type":"string","description":"r2_key del WAV generado"},
                "model":{"type":"string","enum":["htdemucs_ft","htdemucs","mdx_extra"],"default":"htdemucs_ft"},
                "stems":{"type":"array","items":{"type":"string"},"default":["vocals","drums","bass","other"]},
                "version":{"type":"string","default":ACTIVE_VERSION},
            }},
        ),
        types.Tool(
            name="export_midi",
            description="🎹 Convierte un audio WAV generado a archivo MIDI + piano roll PNG usando basic-pitch (Spotify). Permite importar la melodía a cualquier DAW (Ableton, FL Studio, GarageBand).",
            inputSchema={"type":"object","required":["audio_r2_key"],"properties":{
                "audio_r2_key":{"type":"string"},
                "onset_threshold":{"type":"number","default":0.5,"description":"0.3=más notas, 0.7=solo notas fuertes"},
                "minimum_note_length":{"type":"number","default":0.05},
                "generate_piano_roll":{"type":"boolean","default":True},
                "version":{"type":"string","default":ACTIVE_VERSION},
            }},
        ),
        types.Tool(
            name="build_prompt",
            description="🏗️ Construye un prompt optimizado para generate_song/bgm desde parámetros simples. El usuario no necesita saber escribir prompts — elige género, mood, BPM e instrumentos y el sistema construye el prompt perfecto con los parámetros recomendados.",
            inputSchema={"type":"object","properties":{
                "genre":{"type":"string","enum":GENRE_LIST+["bgm"],"default":"bachata"},
                "mood":{"type":"string","description":"romántico, melancólico, sensual, alegre, nostálgico, energético, oscuro"},
                "bpm":{"type":"integer","description":"None=usa el default del género"},
                "instruments":{"type":"array","items":{"type":"string"},"description":"vacío=usa los del género"},
                "style_descriptors":{"type":"array","items":{"type":"string"}},
                "reference_artist":{"type":"string","description":"Ej: Romeo Santos, Bad Bunny"},
                "extra_description":{"type":"string"},
                "is_bgm":{"type":"boolean","default":False},
                "duration_seconds":{"type":"integer","default":30},
            }},
        ),
        types.Tool(
            name="analytics_summary",
            description="📊 Métricas de todas las generaciones del sistema: total, tasa de éxito, géneros más usados, ratings, tiempo promedio. Para el dashboard admin del SaaS.",
            inputSchema={"type":"object","properties":{
                "days":{"type":"integer","default":30,"description":"Últimos N días"},
            }},
        ),
        types.Tool(
            name="gateway_health",
            description="🌐 Estado completo de todos los módulos del API Gateway: audio, imagen, video, composer, chatgau, stems, midi, builder, analytics.",
            inputSchema={"type":"object","properties":{}},
        ),
        # ── CHATGAU ───────────────────────────────────────────────────────────
        types.Tool(
            name="chatgau_support",
            description=(
                "🤖 ChatGAU — Asistente de soporte musical de GenAudius. "
                "Responde preguntas sobre cómo hacer mejores prompts, qué parámetros usar, "
                "cómo solucionar problemas de calidad, flujo de trabajo, géneros y más. "
                "Soporta historial de conversación multi-turno."
            ),
            inputSchema={
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message":     {"type": "string", "description": "Tu pregunta o mensaje para ChatGAU"},
                    "history":     {"type": "array", "description": "Historial de la conversación",
                                    "items": {"type": "object", "properties": {
                                        "role":    {"type": "string", "enum": ["user", "assistant"]},
                                        "content": {"type": "string"}
                                    }}},
                    "use_rag":     {"type": "boolean", "default": True,
                                    "description": "Usar el Knowledge Base para enriquecer la respuesta"},
                    "temperature": {"type": "number", "default": 0.7,
                                    "description": "0.5=más preciso, 0.9=más creativo"},
                    "max_tokens":  {"type": "integer", "default": 800},
                    "session_id":  {"type": "string", "default": "",
                                    "description": "ID de sesión para tracking de conversaciones"},
                },
            },
        ),
        types.Tool(
            name="chatgau_quick",
            description=(
                "⚡ ChatGAU Quick — Respuesta instantánea desde el Knowledge Base (sin GPU). "
                "Para preguntas frecuentes sobre prompts, parámetros o flujo de trabajo. "
                "Más rápido que chatgau_support pero sin generación de modelo."
            ),
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query":  {"type": "string", "description": "Tu pregunta rápida"},
                    "top_k":  {"type": "integer", "default": 2},
                },
            },
        ),
        types.Tool(
            name="chatgau_add_knowledge",
            description=(
                "📚 ChatGAU — Agrega nuevo conocimiento de soporte musical al sistema. "
                "Úsalo para enseñar a ChatGAU sobre nuevas funciones, géneros o flujos de trabajo. "
                "Después usa trigger_chatgau_training para re-entrenar."
            ),
            inputSchema={
                "type": "object",
                "required": ["category", "subcategory", "question", "answer"],
                "properties": {
                    "category":    {"type": "string",
                                    "enum": ["prompts", "parametros", "troubleshooting",
                                             "workflow", "composer_lyric", "versiones",
                                             "generos", "chatgau", "otro"]},
                    "subcategory": {"type": "string"},
                    "question":    {"type": "string"},
                    "answer":      {"type": "string"},
                    "examples":    {"type": "array", "items": {"type": "string"}},
                    "parameters":  {"type": "object"},
                    "tips":        {"type": "string"},
                    "quality_score": {"type": "integer", "default": 9},
                },
            },
        ),
        types.Tool(
            name="chatgau_status",
            description="📊 ChatGAU — Estado del modelo y del Knowledge Base.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="trigger_chatgau_training",
            description=(
                "🚀 ChatGAU — Dispara re-entrenamiento del modelo con el Knowledge Base actualizado. "
                "Ejecutar después de agregar nuevas entradas con chatgau_add_knowledge."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "epochs": {"type": "integer", "default": 4},
                    "resume": {"type": "boolean", "default": True},
                },
            },
        ),
        types.Tool(
            name="trigger_composer_training",
            description=(
                "🚀 COMPOSER LYRIC — Dispara el re-entrenamiento del modelo Composer Lyric "
                "con las letras nuevas que hayas agregado al dataset. "
                "Ejecutar después de add_lyric_to_dataset."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "epochs":  {"type": "integer", "default": 3, "description": "Épocas de entrenamiento adicionales"},
                    "resume":  {"type": "boolean", "default": True, "description": "Reanudar desde el último checkpoint"},
                },
            },
        ),
        # ── MEMORIA GAU ────────────────────────────────────────────────────────
        types.Tool(
            name="store_user_memory",
            description="🧠 Guarda un dato importante sobre el usuario (preferencias, gustos, notas).",
            inputSchema={
                "type": "object",
                "required": ["content", "category"],
                "properties": {
                    "content":  {"type": "string", "description": "El dato a recordar"},
                    "category": {"type": "string", "enum": ["preference", "style", "history", "other"]},
                    "user_id":  {"type": "string", "default": "global_user"},
                    "metadata": {"type": "object"},
                },
            },
        ),
        types.Tool(
            name="get_user_memories",
            description="🔍 Recupera lo que el sistema recuerda sobre el usuario desde MongoDB.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "default": "global_user"},
                    "limit":   {"type": "integer", "default": 10},
                },
            },
        ),
    ]


_URL_FOR_TOOL: dict[str, tuple[str, str]] = {
    "generate_image": ("MODAL_IMAGE_URL", IMAGE_URL),
    "generate_cover_art": ("MODAL_IMAGE_URL", IMAGE_URL),
    "generate_video": ("MODAL_VIDEO_URL", VIDEO_URL),
    "create_full_production": ("MODAL_IMAGE_URL", IMAGE_URL),
    "compose_lyrics": ("MODAL_COMPOSER_URL", COMPOSER_URL),
    "analyze_prompt": ("MODAL_COMPOSER_URL", COMPOSER_URL),
    "refine_lyrics": ("MODAL_COMPOSER_URL", COMPOSER_URL),
    "add_lyric_to_dataset": ("MODAL_COMPOSER_URL", COMPOSER_URL),
    "trigger_composer_training": ("MODAL_COMPOSER_URL", COMPOSER_URL),
    "separate_stems": ("MODAL_STEMS_URL", STEMS_URL),
    "export_midi": ("MODAL_MIDI_URL", MIDI_URL),
    "build_prompt": ("MODAL_BUILDER_URL", BUILDER_URL),
    "analytics_summary": ("MODAL_ANALYTICS_URL", ANALYTICS_URL),
    "gateway_health": ("MODAL_GATEWAY_URL", GATEWAY_URL),
    "chatgau_support": ("MODAL_CHATGAU_URL", CHATGAU_URL),
    "chatgau_quick": ("MODAL_CHATGAU_URL", CHATGAU_URL),
    "chatgau_add_knowledge": ("MODAL_CHATGAU_URL", CHATGAU_URL),
    "chatgau_status": ("MODAL_CHATGAU_URL", CHATGAU_URL),
}


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name != "user_login":
        err = _auth_error()
        if err:
            return [err]

    req = _URL_FOR_TOOL.get(name)
    if req:
        miss = _need_url(req[1], req[0])
        if miss:
            return [miss]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            match name:
                case "user_login":             return await _user_login(client, arguments)
                case "generate_song":          return await _gen_audio(client, arguments, "song")
                case "generate_bgm":           return await _gen_audio(client, arguments, "bgm")
                case "generate_lyrics":        return _gen_lyrics(arguments)
                case "generate_image":         return await _gen_image(client, arguments)
                case "generate_cover_art":     return await _gen_cover(client, arguments)
                case "generate_video":         return await _gen_video(client, arguments)
                case "create_full_production": return await _full_production(client, arguments)
                case "get_system_status":      return await _system_status(client)
                case "list_versions":          return await _list_versions(client)
                case "upload_audio_to_r2":     return _upload_audio(arguments)
                case "trigger_training":       return await _trigger_training(client, arguments)
                # ── Composer Lyric ──────────────────────────────────────────
                # ── Enterprise ─────────────────────────────────────────
                case "separate_stems":   return await _separate_stems(client, arguments)
                case "export_midi":      return await _export_midi(client, arguments)
                case "build_prompt":     return await _build_prompt(client, arguments)
                case "analytics_summary":return await _analytics_summary(client, arguments)
                case "gateway_health":   return await _gateway_health(client)
                # ── ChatGAU ────────────────────────────────────────────
                case "chatgau_support":          return await _chatgau_chat(client, arguments)
                case "chatgau_quick":            return await _chatgau_quick(client, arguments)
                case "chatgau_add_knowledge":    return await _chatgau_add_knowledge(client, arguments)
                case "chatgau_status":           return await _chatgau_status(client)
                case "trigger_chatgau_training": return await _chatgau_trigger_training(arguments)
                # ── Composer Lyric ──────────────────────────────────────────
                case "compose_lyrics":            return await _compose_lyrics(client, arguments)
                case "analyze_prompt":            return await _cl_analyze(client, arguments)
                case "refine_lyrics":             return await _cl_refine(client, arguments)
                case "add_lyric_to_dataset":      return await _cl_add_to_dataset(arguments)
                case "trigger_composer_training": return await _cl_trigger_training(client, arguments)
                # ── Memoria GAU ───────────────────────────────────────────────
                case "store_user_memory":         return await _store_user_memory(arguments)
                case "get_user_memories":          return await _get_user_memories(arguments)
                case _:
                    return [types.TextContent(type="text", text=f"❌ Tool desconocida: {name}")]
        except TimeoutError as e:
            return [types.TextContent(type="text", text=f"⏱️ Timeout ({TIMEOUT}s): {e}")]
        except httpx.HTTPStatusError as e:
            return [types.TextContent(type="text", text=f"❌ API error {e.response.status_code}: {e.response.text[:300]}")]
        except Exception as e:
            logger.error("Error en %s: %s", name, e, exc_info=True)
            return [types.TextContent(type="text", text=f"❌ Error: {e}")]


# ── Handlers ──────────────────────────────────────────────────────────────────
async def _user_login(client: httpx.AsyncClient, args: dict[str, Any]) -> list[types.TextContent]:
    if not AUTH_LOGIN_URL:
        return [
            types.TextContent(
                type="text",
                text=(
                    "❌ **GENAUDIUS_AUTH_URL** no está configurada en el servidor MCP.\n\n"
                    "En el VPS (systemd o `.env` de Docker), define la URL completa del login de tu API, "
                    "por ejemplo: `https://api.tudominio.com/v1/auth/login`.\n\n"
                    "El MCP solo hace de proxy: no almacena contraseñas."
                ),
            )
        ]
    password = (args.get("password") or "").strip()
    email = (args.get("email") or "").strip()
    username = (args.get("username") or "").strip()
    if not password or (not email and not username):
        return [
            types.TextContent(
                type="text",
                text="❌ Indica **password** y **email** o **username**.",
            )
        ]
    if email:
        payload: dict[str, Any] = {"email": email, "password": password}
    else:
        payload = {"username": username, "password": password}

    try:
        resp = await client.post(AUTH_LOGIN_URL, json=payload, timeout=60)
    except httpx.RequestError as e:
        return [types.TextContent(type="text", text=f"❌ No se pudo contactar el servicio de login: {e}")]

    try:
        body = resp.json()
    except Exception:
        body = {"raw": (resp.text or "")[:800]}

    if resp.status_code >= 400:
        detail = body if isinstance(body, dict) else str(body)
        return [
            types.TextContent(
                type="text",
                text=f"❌ Login rechazado (**{resp.status_code}**)\n\n```json\n{json.dumps(detail, ensure_ascii=False, indent=2)[:1200]}\n```",
            )
        ]

    token = None
    if isinstance(body, dict):
        for key in ("access_token", "token", "jwt", "id_token", "accessToken"):
            if body.get(key):
                token = str(body[key])
                break

    t = "🔐 **Sesión obtenida**\n\n"
    if token:
        t += f"**Token** (`…{token[-8:]}`): `{token[:24]}…` (truncado en log; copia el valor completo del JSON abajo)\n\n"
    t += "```json\n"
    t += json.dumps(body, ensure_ascii=False, indent=2)[:4000]
    t += "\n```\n\n"
    t += (
        "Usa el token según tu backend (p. ej. `Authorization: Bearer …` en el SaaS). "
        "Para las rutas HTTP del MCP (`/tool/...`), sigue usando **X-GenAudius-Key** salvo que tu gateway traduzca JWT a esa clave."
    )
    return [types.TextContent(type="text", text=t)]

async def _gen_audio(client, args, mode):
    prompt = args["prompt"]
    if mode == "bgm" and "instrumental" not in prompt.lower():
        prompt += ", instrumental, no vocals"
    payload = {
        "prompt": prompt,
        "version": args.get("version", ACTIVE_VERSION),
        "make_instrumental": True if mode == "bgm" else False,
    }
    
    endpoint = f"{API_BASE_URL}/api/v1/generate"
    resp = await client.post(endpoint, json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    
    icon = "🎶" if mode == "song" else "🎼"
    t  = f"{icon} **GenAudius {mode.title()} — Tarea enviada**\n\n"
    if d.get("data") and d["data"].get("taskId"):
        t += f"**Task ID:** `{d['data']['taskId']}`\n"
        t += f"**Estado:** {d['data'].get('status', 'submitted')}\n\n"
        t += f"💡 Usa `get_record_info` para ver el progreso."
    else:
        t += f"Error: {d.get('msg', 'Respuesta inesperada')}"
    return [types.TextContent(type="text", text=t)]


def _gen_lyrics(args):
    prompt    = args["prompt"]
    genre     = args.get("genre", "")
    language  = args.get("language", "Español")
    structure = args.get("structure", "Verso 1 - Coro - Verso 2 - Coro - Puente - Coro")
    t  = f"✍️ **Letra — {genre.title() if genre else 'Canción'}**\n\n"
    t += f"Generando en {language} sobre: _{prompt}_\n"
    t += f"**Estructura:** {structure}\n\n---\n\n"
    t += "_(Claude completará la letra en el siguiente mensaje)_\n\n"
    t += f"**Siguiente paso:** Usa `generate_song` con el prompt:\n`\"{genre} con letra: [pegar letra aquí]\"`"
    return [types.TextContent(type="text", text=t)]


async def _gen_image(client, args):
    payload = {
        "prompt": args["prompt"],
        "style": args.get("style", "auto"),
        "model": args.get("model", "flux"),
        "width": args.get("width", 1024),
        "height": args.get("height", 1024),
        "steps": args.get("steps", 4),
        "seed": args.get("seed", -1),
        "version": args.get("version", ACTIVE_VERSION),
        "upload_to_r2": True,
    }
    resp = await client.post(f"{IMAGE_URL}/generate-image", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"🖼️ **Imagen generada — {d.get('model','flux').upper()}**\n\n"
    t += f"**Resolución:** {d.get('width')}×{d.get('height')} | **Seed:** {d.get('seed')}\n\n"
    if d.get("image_url"):
        t += f"🔗 **Ver imagen** (2h):\n{d['image_url']}\n\n"
    if d.get("r2_key"):
        t += f"📦 `image_r2_key: {d['r2_key']}`"
    return [types.TextContent(type="text", text=t)]


async def _gen_cover(client, args):
    payload = {
        "song_prompt": args["song_prompt"],
        "genre": args.get("genre", "default"),
        "style": args.get("style", "album_cover"),
        "artist_name": args.get("artist_name", "GenAudius"),
        "version": args.get("version", ACTIVE_VERSION),
    }
    resp = await client.post(f"{IMAGE_URL}/generate-cover", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"🎨 **Cover Art — {payload['genre']} / {payload['style']}**\n\n"
    if d.get("image_url"):
        t += f"🔗 **Ver cover** (2h):\n{d['image_url']}\n\n"
    if d.get("r2_key"):
        t += f"📦 `image_r2_key: {d['r2_key']}`\n"
        t += "\n💡 Combina con `generate_video` pasando este key + un audio_r2_key."
    return [types.TextContent(type="text", text=t)]


async def _gen_video(client, args):
    payload = {
        "audio_r2_key": args["audio_r2_key"],
        "image_r2_key": args["image_r2_key"],
        "title":        args.get("title", ""),
        "artist":       args.get("artist", "GenAudius"),
        "resolution":   args.get("resolution", "1080x1080"),
        "visualizer":   args.get("visualizer", True),
        "version":      args.get("version", ACTIVE_VERSION),
    }
    resp = await client.post(f"{VIDEO_URL}/generate-video", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    labels = {"1080x1080": "Instagram/cuadrado", "1920x1080": "YouTube", "1080x1920": "TikTok/Reels"}
    t  = f"🎬 **Video MP4 — {d.get('resolution')} ({labels.get(d.get('resolution',''), '')})**\n\n"
    t += f"**Tamaño:** {d.get('file_size_mb')} MB\n\n"
    if d.get("video_url"):
        t += f"🔗 **Descargar MP4** (2h):\n{d['video_url']}\n\n"
    if d.get("r2_key"):
        t += f"📦 `video_r2_key: {d['r2_key']}`"
    return [types.TextContent(type="text", text=t)]


async def _full_production(client, args):
    prompt  = args["prompt"]
    genre   = args.get("genre", "bachata")
    title   = args.get("title", prompt[:40])
    artist  = args.get("artist", "GenAudius")
    version = args.get("version", ACTIVE_VERSION)
    seconds = args.get("audio_seconds", 30)
    res     = args.get("resolution", "1080x1080")

    t = f"🚀 **Producción completa — {title}**\n\n"
    t += "Generando audio e imagen en paralelo...\n\n"

    # Audio + imagen en paralelo
    audio_task = client.post(f"{AUDIO_URL}/generate", headers=_headers(), json={
        "prompt": f"{genre}, {prompt}",
        "version": version,
        "seconds_total": seconds,
        "steps": 100,
        "upload_to_r2": True,
    })
    cover_task = client.post(f"{IMAGE_URL}/generate-cover", headers=_headers(), json={
        "song_prompt": prompt,
        "genre": genre,
        "style": "album_cover",
        "version": version,
    })

    audio_resp, cover_resp = await asyncio.gather(audio_task, cover_task)
    audio_resp.raise_for_status()
    cover_resp.raise_for_status()
    audio_d = audio_resp.json()
    cover_d = cover_resp.json()

    # Video
    t += "Combinando en video...\n\n"
    video_resp = await client.post(f"{VIDEO_URL}/generate-video", headers=_headers(), json={
        "audio_r2_key": audio_d["r2_key"],
        "image_r2_key": cover_d["r2_key"],
        "title": title,
        "artist": artist,
        "resolution": res,
        "visualizer": True,
        "version": version,
    })
    video_resp.raise_for_status()
    video_d = video_resp.json()

    t += "---\n\n✅ **¡Producción lista!**\n\n"
    t += f"🎶 **Audio WAV:**\n{audio_d.get('audio_url', '—')}\n\n"
    t += f"🖼️ **Cover Art:**\n{cover_d.get('image_url', '—')}\n\n"
    t += f"🎬 **Video MP4** ({video_d.get('resolution')}, {video_d.get('file_size_mb')} MB):\n{video_d.get('video_url', '—')}\n\n"
    t += f"📦 **R2 keys:**\n  Audio: `{audio_d.get('r2_key')}`\n  Imagen: `{cover_d.get('r2_key')}`\n  Video: `{video_d.get('r2_key')}`"
    return [types.TextContent(type="text", text=t)]


async def _system_status(client: httpx.AsyncClient) -> list[types.TextContent]:
    # Check Engine v1.0 credits/status
    try:
        resp = await client.get(f"{API_BASE_URL}/api/v1/chat/credit", headers=_headers())
        d = resp.json()
        status_txt = f"✅ **GenAudius Engine v1.0:** Online\n💰 **Créditos:** {d.get('data', 'N/A')}"
    except Exception:
        status_txt = "❌ **GenAudius Engine v1.0:** Offline"
        
    t  = f"📊 **GenAudius MCP — Estado del Sistema**\n\n"
    t += f"{status_txt}\n"
    t += f"🌍 **API Base:** {API_BASE_URL}\n"
    t += f"🏷️ **Versión Activa:** {ACTIVE_VERSION}\n"
    return [types.TextContent(type="text", text=t)]
async def _list_versions(client):
    resp = await client.get(f"{AUDIO_URL}/versions", headers=_headers(), timeout=30)
    resp.raise_for_status()
    d = resp.json()
    t = f"🗂️ **Versiones — Activa: `{d.get('active', ACTIVE_VERSION)}`**\n\n"
    for ver, cfg in d.get("config", {}).items():
        t += f"**{ver}** — {cfg.get('description', '')}\n  Géneros: {', '.join(cfg.get('genres', []))}\n\n"
    return [types.TextContent(type="text", text=t)]


def _upload_audio(args):
    import subprocess
    local_path   = args["local_path"]
    genre        = args["genre"]
    dataset_type = args.get("dataset_type", "genres_15s")
    version      = args.get("version", ACTIVE_VERSION)
    r2_key = f"{version}/dataset/audio/{dataset_type}/{genre}/{Path(local_path).name}"
    result = subprocess.run(
        ["modal", "run", "tools/dataset_pipeline/r2_sync_modal_mount.py",
         "--local-path", local_path,
         "--r2-prefix", f"{version}/dataset/audio/{dataset_type}/{genre}/"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        return [types.TextContent(type="text", text=f"❌ Error:\n```\n{result.stderr[-400:]}\n```")]
    t  = f"📤 **Subido a R2**\n\n`{Path(local_path).name}` → `{r2_key}`\n\n"
    t += "El Worker detectará el archivo y encolará el re-entrenamiento."
    return [types.TextContent(type="text", text=t)]


async def _trigger_training(client, args):
    version = args.get("version", ACTIVE_VERSION)
    genres = args.get("genres") or []
    resume_from = args.get("resume_from_checkpoint", True)
    resume_ckpt = (args.get("resume_ckpt_path") or "").strip()
    payload = {
        "version": version,
        "genres": genres,
        "resume_ckpt_path": resume_ckpt,
        "force_fresh": not bool(resume_from),
    }
    resp = await client.post(
        f"{AUDIO_URL}/training/trigger",
        json=payload,
        headers=_headers(),
        timeout=60,
    )
    resp.raise_for_status()
    d = resp.json()
    t = (
        f"🚀 **Training encolado — {version}**\n\n"
        f"**Estado:** {d.get('status', '?')}\n"
        f"**call_id:** `{d.get('call_id', '?')}`\n"
        f"**run name:** `{d.get('name', '?')}`\n"
        f"**R2 genres prefix:** `{d.get('r2_genres_15s_prefix', '?')}`\n"
        f"**Resume ckpt:** `{d.get('resume_ckpt_path') or '—'}`\n"
        f"**Géneros (log):** {', '.join(genres) if genres else '—'}\n\n"
        f"Logs: `modal app logs {d.get('train_app', 'genaudius-v1-gau-train')}`"
    )
    return [types.TextContent(type="text", text=t)]


async def main():
    logger.info(
        "GenAudius MCP — audio/imagen/video/composer + ChatGAU soporte; "
        "URLs pueden ser Modal directo o API Gateway en AWS"
    )
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())

def run():
    asyncio.run(main())

if __name__ == "__main__":
    run()

# ── Composer Lyric handlers ────────────────────────────────────────────────────

async def _compose_lyrics(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {
        "prompt": args["prompt"],
        "genre": args.get("genre", "bachata"),
        "mood": args.get("mood", ""),
        "theme": args.get("theme", ""),
        "bpm": args.get("bpm", 130),
        "language": args.get("language", "Español"),
        "mode": args.get("mode", "professional"),
        "custom_structure": args.get("custom_structure"),
        "max_tokens": args.get("max_tokens", 1200),
        "seed": args.get("seed", -1),
    }
    resp = await client.post(f"{COMPOSER_URL}/compose", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"🖊️ **Composer Lyric — {d.get('genre','').title()} / {d.get('mode','')}**\n\n"
    t += f"**Mood:** {d.get('mood') or 'según el tema'} | **Temperatura:** {d.get('temperature')} | **Palabras:** {d.get('word_count')}\n\n---\n\n"
    t += d.get("lyrics", "")
    t += "\n\n---\n\n💡 Refina con `refine_lyrics` o produce con `create_full_production`."
    return [types.TextContent(type="text", text=t)]


async def _cl_analyze(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {"prompt": args["prompt"], "genre": args.get("genre", "bachata")}
    resp = await client.post(f"{COMPOSER_URL}/analyze", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"🔍 **Análisis — {d.get('genre','').title()}**\n\n_{d.get('prompt', '')}_\n\n---\n\n"
    t += d.get("analysis", "")
    t += "\n\n---\n\n✅ Usa `compose_lyrics` con estos datos para la composición final."
    return [types.TextContent(type="text", text=t)]


async def _cl_refine(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {
        "original_lyrics": args["original_lyrics"],
        "instructions": args["instructions"],
        "genre": args.get("genre", "bachata"),
        "max_tokens": args.get("max_tokens", 1200),
    }
    resp = await client.post(f"{COMPOSER_URL}/refine", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"✨ **Letra refinada**\n\n**Instrucciones:** _{args['instructions']}_\n\n---\n\n"
    t += d.get("refined_lyrics", "")
    return [types.TextContent(type="text", text=t)]


async def _cl_add_to_dataset(args: dict) -> list[types.TextContent]:
    import json as json_mod
    lyrics_text = args["lyrics_text"]
    genre       = args["genre"]
    sections: dict = {}
    current_key = "verso1"
    current_lines: list = []
    label_map = {
        "verso 1": "verso1", "verso 2": "verso2", "pre-coro": "pre_coro",
        "pre coro": "pre_coro", "coro": "coro", "coro final": "coro_final",
        "puente": "puente", "bridge": "bridge", "intro": "intro",
        "outro": "outro", "breakdown": "breakdown",
    }
    for line in lyrics_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_lines:
                sections[current_key] = "\n".join(l for l in current_lines if l.strip())
            current_lines = []
            label = stripped[1:-1].lower()
            current_key = label_map.get(label, label.replace(" ", "_"))
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_key] = "\n".join(l for l in current_lines if l.strip())

    entry = {
        "id": f"cl_mcp_{int(time.time())}",
        "genre": genre,
        "subgenre": "original",
        "language": "es",
        "mood": args.get("mood", "romántico"),
        "theme": args.get("theme", "amor"),
        "bpm": args.get("bpm", 130),
        "structure": list(sections.keys()),
        "prompt": args.get("prompt", f"Letra de {genre}"),
        "lyrics": sections,
        "style_notes": "Letra agregada via MCP",
        "quality_score": args.get("quality", 9),
    }

    seed_path = Path("composer_lyric/dataset/seed_lyrics.json")
    existing = json_mod.loads(seed_path.read_text(encoding="utf-8")) if seed_path.exists() else []
    existing.append(entry)
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(json_mod.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    t  = f"📚 **Letra agregada — `{entry['id']}`**\n\n"
    t += f"**Género:** {genre} | **Secciones:** {len(sections)} | **Total dataset:** {len(existing)} letras\n\n"
    t += "Usa `trigger_composer_training` para re-entrenar el modelo."
    return [types.TextContent(type="text", text=t)]


async def _cl_trigger_training(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    import subprocess
    epochs = args.get("epochs", 3)
    resume = args.get("resume", True)
    subprocess.run(["python", "composer_lyric/scripts/build_dataset.py"], timeout=60)
    subprocess.Popen([
        "modal", "run", "modal/composer_lyric_train.py",
        f"--epochs={epochs}", f"--resume={'True' if resume else 'False'}",
    ])
    t  = f"🚀 **Composer Lyric — training lanzado**\n\n"
    t += f"**Épocas:** {epochs} | **Resume:** {'Sí' if resume else 'No'}\n\n"
    t += "Monitorea: `modal logs genaudius-composer-lyric-train`"
    return [types.TextContent(type="text", text=t)]

# ── ChatGAU handlers ──────────────────────────────────────────────────────────

async def _chatgau_chat(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {
        "message":    args["message"],
        "history":    args.get("history", []),
        "use_rag":    args.get("use_rag", True),
        "temperature": args.get("temperature", 0.7),
        "max_tokens": args.get("max_tokens", 800),
        "session_id": args.get("session_id", ""),
    }
    resp = await client.post(f"{CHATGAU_URL}/chat", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()

    t  = f"🤖 **ChatGAU**\n\n{d.get('response', '')}\n\n"
    if d.get("tool_suggestions"):
        t += "---\n\n🛠️ **Tools sugeridas:**\n"
        for ts in d["tool_suggestions"]:
            t += f"  • `{ts['tool']}` — parámetros: `{json.dumps(ts['params'])}`\n"
    if d.get("kb_used"):
        t += "\n_Respuesta enriquecida con el Knowledge Base de GenAudius._"
    return [types.TextContent(type="text", text=t)]


async def _chatgau_quick(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {"query": args["query"], "top_k": args.get("top_k", 2)}
    resp = await client.post(f"{CHATGAU_URL}/quick", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    if d.get("status") == "no_match":
        return [types.TextContent(type="text",
            text=f"🤖 **ChatGAU Quick**\n\n{d['response']}\n\nUsa `chatgau_support` para una respuesta completa.")]
    t  = f"🤖 **ChatGAU Quick — {d.get('category', '')}**\n\n{d.get('response', '')}"
    return [types.TextContent(type="text", text=t)]


async def _chatgau_add_knowledge(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {
        "category":    args["category"],
        "subcategory": args["subcategory"],
        "question":    args["question"],
        "answer":      args["answer"],
        "examples":    args.get("examples", []),
        "parameters":  args.get("parameters"),
        "tips":        args.get("tips", ""),
        "quality_score": args.get("quality_score", 9),
    }
    resp = await client.post(f"{CHATGAU_URL}/add-knowledge", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"📚 **Conocimiento agregado a ChatGAU**\n\n"
    t += f"**ID:** `{d['id']}`\n**Total KB:** {d['total']} entradas\n\n"
    t += "Usa `trigger_chatgau_training` para re-entrenar el modelo con este nuevo conocimiento."
    return [types.TextContent(type="text", text=t)]


async def _chatgau_status(client: httpx.AsyncClient) -> list[types.TextContent]:
    resp = await client.get(f"{CHATGAU_URL}/health", headers=_headers(), timeout=30)
    resp.raise_for_status()
    d = resp.json()
    status_icon = "✅" if d.get("model_ready") else "⚠️"
    t  = f"🤖 **ChatGAU — Estado**\n\n"
    t += f"{status_icon} Modelo: {'Listo' if d.get('model_ready') else 'No entrenado aún'}\n"
    t += f"📚 Knowledge Base: {d.get('kb_entries', 0)} entradas\n"
    t += f"🏷️ Categorías: {', '.join(d.get('kb_categories', []))}\n\n"
    if not d.get("model_ready"):
        t += "💡 Para entrenar:\n"
        t += "  1. `python chatgau/scripts/build_dataset.py`\n"
        t += "  2. `modal run modal/chatgau_train.py`"
    return [types.TextContent(type="text", text=t)]


async def _chatgau_trigger_training(args: dict) -> list[types.TextContent]:
    import subprocess
    epochs = args.get("epochs", 4)
    resume = args.get("resume", True)
    subprocess.run(["python", "chatgau/scripts/build_dataset.py"], timeout=60)
    subprocess.Popen([
        "modal", "run", "modal/chatgau_train.py",
        f"--epochs={epochs}", f"--resume={'True' if resume else 'False'}",
    ])
    t  = f"🚀 **ChatGAU training lanzado**\n\n"
    t += f"**Épocas:** {epochs} | **Resume:** {'Sí' if resume else 'No'}\n\n"
    t += "Monitorea: `modal logs genaudius-chatgau-train`"
    return [types.TextContent(type="text", text=t)]

# ── Enterprise handlers ───────────────────────────────────────────────────────


async def _separate_stems(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    # Support for both file uploads (multipart) and R2 keys (legacy)
    audio_url = args.get("audio_url")
    if not audio_url:
        return [types.TextContent(type="text", text="❌ Proporciona `audio_url` para la separación.")]

    payload = {
        "audio_url": audio_url,
        "model":     args.get("model", "htdemucs"),
        "version":   args.get("version", ACTIVE_VERSION),
    }
    
    # In the new Engine v1.0, we call /api/v1/vocal-removal/generate
    endpoint = f"{API_BASE_URL}/api/v1/vocal-removal/generate"
    resp = await client.post(endpoint, json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    
    t  = f"🎚️ **GenAudius Stems — Tarea enviada**\n\n"
    t += f"**Task ID:** `{d['data']['taskId']}`\n"
    t += f"**Estado:** {d['data']['status']}\n\n"
    t += "💡 Usa `get_record_info` con el taskId para obtener los enlaces de descarga cuando termine."
    return [types.TextContent(type="text", text=t)]


async def _export_midi(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    audio_url = args.get("audio_url")
    if not audio_url:
        return [types.TextContent(type="text", text="❌ Proporciona `audio_url` para la transcripción MIDI.")]

    payload = {
        "audio_url": audio_url,
        "version":   args.get("version", ACTIVE_VERSION),
    }
    
    # In the new Engine v1.0, we call /api/v1/midi
    endpoint = f"{API_BASE_URL}/api/v1/midi"
    resp = await client.post(endpoint, json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    
    t  = f"🎹 **GenAudius MIDI — Tarea enviada**\n\n"
    t += f"**Task ID:** `{d['data']['taskId']}`\n"
    t += f"**Estado:** {d['data']['status']}\n\n"
    t += "💡 El sistema extraerá la melodía y el bajo automáticamente."
    return [types.TextContent(type="text", text=t)]


async def _build_prompt(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    payload = {
        "genre":              args.get("genre", "bachata"),
        "mood":               args.get("mood", "romántico"),
        "bpm":                args.get("bpm"),
        "instruments":        args.get("instruments", []),
        "style_descriptors":  args.get("style_descriptors", []),
        "reference_artist":   args.get("reference_artist", ""),
        "extra_description":  args.get("extra_description", ""),
        "is_bgm":             args.get("is_bgm", False),
        "duration_seconds":   args.get("duration_seconds", 30),
    }
    resp = await client.post(f"{BUILDER_URL}/build", json=payload, headers=_headers())
    resp.raise_for_status()
    d = resp.json()
    t  = f"🏗️ **Prompt Builder — {args.get('genre','').title()}**\n\n"
    t += f"**Prompt optimizado:**\n```\n{d.get('prompt', '')}\n```\n\n"
    t += f"**Parámetros recomendados:**\n```json\n{json.dumps(d.get('recommended_params', {}), indent=2)}\n```\n\n"
    t += f"**BPM validado:** {d.get('bpm_validated')} (rango: {d.get('bpm_range')})\n"
    t += f"**Artistas de referencia:** {', '.join(d.get('reference_artists', []))}\n\n"
    t += f"💡 {d.get('tip', '')}\n\n"
    t += "Copia los parámetros recomendados directamente en `generate_song`."
    return [types.TextContent(type="text", text=t)]


async def _analytics_summary(client: httpx.AsyncClient, args: dict) -> list[types.TextContent]:
    days = args.get("days", 30)
    resp = await client.get(f"{ANALYTICS_URL}/summary?days={days}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    d = resp.json()
    t  = f"📊 **Analytics GenAudius — últimos {days} días**\n\n"
    t += f"**Total generaciones:** {d.get('total_events', 0)}\n"
    t += f"**Tasa de éxito:** {d.get('success_rate', 0)}%\n"
    t += f"**Tiempo promedio:** {d.get('avg_duration_ms', 0)}ms\n"
    t += f"**Rating promedio:** ⭐ {d.get('avg_rating', 0)}/5 ({d.get('total_ratings', 0)} votos)\n\n"
    t += "**Por tipo:**\n"
    for k, v in d.get("by_type", {}).items():
        t += f"  {k}: {v}\n"
    t += "\n**Por género:**\n"
    for k, v in d.get("by_genre", {}).items():
        t += f"  {k}: {v}\n"
    return [types.TextContent(type="text", text=t)]


async def _gateway_health(client: httpx.AsyncClient) -> list[types.TextContent]:
    if not GATEWAY_URL:
        return [types.TextContent(type="text", text="❌ MODAL_GATEWAY_URL no configurada.")]
    resp = await client.get(
        f"{GATEWAY_URL}/v1/system/health",
        headers={"X-GenAudius-Key": os.environ.get("GATEWAY_INTERNAL_KEY", "")},
        timeout=30,
    )
    resp.raise_for_status()
    d = resp.json()
    t  = f"🌐 **API Gateway — Estado completo**\n\n"
    t += f"**Gateway:** {d.get('gateway', '?')} | {d.get('timestamp', '')[:19]}\n\n"
    t += "**Módulos:**\n"
    for name, status in d.get("modules", {}).items():
        icon = "✅" if status.get("status") == "ok" else "⚠️" if status.get("status") == "not_configured" else "❌"
        t += f"  {icon} {name}: {status.get('status', '?')}\n"
    return [types.TextContent(type="text", text=t)]


# ── Memoria GAU Handlers ───────────────────────────────────────────────────

async def _store_user_memory(args: dict) -> list[types.TextContent]:
    from genaudius_mcp.memory import memory_engine
    
    user_id = args.get("user_id", "global_user")
    category = args.get("category", "other")
    content = args.get("content", "")
    metadata = args.get("metadata", {})
    
    if not content:
        return [types.TextContent(type="text", text="❌ El contenido no puede estar vacío.")]
        
    success = await memory_engine.store_memory(user_id, category, content, metadata)
    
    if success:
        return [types.TextContent(type="text", text=f"🧠 **Memoria guardada**\n\nCategoría: `{category}`\nContenido: {content}")]
    else:
        return [types.TextContent(type="text", text="❌ No se pudo guardar la memoria. ¿Está MongoDB conectado?")]

async def _get_user_memories(args: dict) -> list[types.TextContent]:
    from genaudius_mcp.memory import memory_engine
    
    user_id = args.get("user_id", "global_user")
    limit = args.get("limit", 10)
    
    memories = await memory_engine.get_recent_memories(user_id, limit)
    
    if not memories:
        return [types.TextContent(type="text", text=f"🔍 No se encontraron recuerdos para el usuario `{user_id}`.")]
        
    t = f"🧠 **Recuerdos de `{user_id}` (últimos {len(memories)})**\n\n"
    for m in memories:
        date = m["timestamp"].strftime("%Y-%m-%d %H:%M")
        t += f"• **[{m['category']}]** ({date}): {m['content']}\n"
        if m.get("metadata"):
            t += f"  _Meta: {json.dumps(m['metadata'])}_\n"
            
    return [types.TextContent(type="text", text=t)]
