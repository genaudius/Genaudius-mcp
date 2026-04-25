"""
GenAudius SaaS — MCP Client
==============================
Cómo el SaaS en genaudius.com llama al MCP en genaudius.app.

Instalar en el backend FastAPI del SaaS (genaudius.com / AWS):
  pip install httpx

Este archivo es el SDK cliente que va en el backend del SaaS.
"""

import httpx
import asyncio
from typing import Any, Optional

# ── Config (variables de entorno en AWS) ──────────────────────────
MCP_BASE_URL = "https://api.genaudius.app"   # genaudius.app VPS
MCP_API_KEY  = "tu-api-key-privada"          # GENAUDIUS_API_KEY del VPS


class GenAudiusMCPClient:
    """
    Cliente para llamar al MCP de genaudius.app desde el SaaS en genaudius.com.

    Uso en el backend FastAPI del SaaS:

        client = GenAudiusMCPClient()

        # Generar canción
        result = await client.generate_song(
            prompt="bachata romántica, guitarra, 128bpm",
            genre="bachata",
            seconds_total=30,
        )
        audio_url = result["audio_url"]

        # Producción completa
        result = await client.full_production(
            prompt="bachata sobre el atardecer",
            genre="bachata",
        )
        video_url = result["video"]["video_url"]
    """

    def __init__(
        self,
        base_url: str = MCP_BASE_URL,
        api_key: str = MCP_API_KEY,
        timeout: int = 660,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers  = {
            "X-GenAudius-Key": api_key,
            "Content-Type":    "application/json",
            "Origin":          "https://genaudius.com",
        }
        self.timeout = timeout

    async def _call_tool(self, tool: str, arguments: dict = {}) -> dict:
        """Llama a una tool del MCP via HTTP POST /tool/{tool_name}."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/mcp/tool/{tool}",
                headers=self.headers,
                json={"arguments": arguments},
            )
            resp.raise_for_status()
            data = resp.json()
            return data

    async def _call_gateway(self, endpoint: str, payload: dict = {}) -> dict:
        """Llama directamente a un endpoint del Gateway via /v1/."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/{endpoint}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Audio ─────────────────────────────────────────────────────
    async def generate_song(
        self,
        prompt: str,
        genre: str = "bachata",
        seconds_total: float = 30,
        steps: int = 100,
        cfg_scale: float = 6.5,
        seed: int = -1,
        version: str = "GenAudius_V1",
    ) -> dict:
        return await self._call_gateway("generate/song", {
            "prompt": prompt, "genre": genre,
            "seconds_total": seconds_total, "steps": steps,
            "cfg_scale": cfg_scale, "seed": seed, "version": version,
            "upload_to_r2": True,
        })

    async def generate_bgm(
        self,
        prompt: str,
        seconds_total: float = 60,
        steps: int = 85,
        seed: int = -1,
    ) -> dict:
        return await self._call_gateway("generate/bgm", {
            "prompt": prompt,
            "seconds_total": seconds_total,
            "steps": steps,
            "seed": seed,
            "upload_to_r2": True,
        })

    # ── Imagen ────────────────────────────────────────────────────
    async def generate_image(
        self,
        prompt: str,
        style: str = "auto",
        model: str = "flux",
        width: int = 1024,
        height: int = 1024,
    ) -> dict:
        return await self._call_gateway("generate/image", {
            "prompt": prompt, "style": style,
            "model": model, "width": width, "height": height,
            "upload_to_r2": True,
        })

    async def generate_cover(
        self,
        song_prompt: str,
        genre: str = "bachata",
        style: str = "album_cover",
        artist_name: str = "GenAudius",
    ) -> dict:
        return await self._call_gateway("generate/cover", {
            "song_prompt": song_prompt,
            "genre": genre, "style": style,
            "artist_name": artist_name,
        })

    # ── Video ─────────────────────────────────────────────────────
    async def generate_video(
        self,
        audio_r2_key: str,
        image_r2_key: str,
        title: str = "",
        artist: str = "GenAudius",
        resolution: str = "1080x1080",
    ) -> dict:
        return await self._call_gateway("generate/video", {
            "audio_r2_key": audio_r2_key,
            "image_r2_key": image_r2_key,
            "title": title, "artist": artist,
            "resolution": resolution, "visualizer": True,
        })

    # ── Producción completa ───────────────────────────────────────
    async def full_production(
        self,
        prompt: str,
        genre: str = "bachata",
        title: str = "",
        artist: str = "GenAudius",
        audio_seconds: float = 30,
        resolution: str = "1080x1080",
        version: str = "GenAudius_V1",
    ) -> dict:
        """Genera audio + cover + video en un solo llamado."""
        return await self._call_gateway("generate/full", {
            "prompt": prompt, "genre": genre,
            "title": title or prompt[:40],
            "artist": artist,
            "audio_seconds": audio_seconds,
            "resolution": resolution,
            "version": version,
        })

    # ── Letras (Composer Lyric) ───────────────────────────────────
    async def compose_lyrics(
        self,
        prompt: str,
        genre: str = "bachata",
        mood: str = "",
        mode: str = "professional",
    ) -> dict:
        return await self._call_gateway("lyrics/compose", {
            "prompt": prompt, "genre": genre,
            "mood": mood, "mode": mode,
        })

    async def refine_lyrics(
        self,
        original_lyrics: str,
        instructions: str,
        genre: str = "bachata",
    ) -> dict:
        return await self._call_gateway("lyrics/refine", {
            "original_lyrics": original_lyrics,
            "instructions": instructions,
            "genre": genre,
        })

    # ── Stems ─────────────────────────────────────────────────────
    async def separate_stems(
        self,
        audio_r2_key: str,
        stems: list[str] = ["vocals", "drums", "bass", "other"],
    ) -> dict:
        return await self._call_gateway("stems/separate", {
            "audio_r2_key": audio_r2_key,
            "stems": stems,
            "model": "htdemucs_ft",
        })

    # ── MIDI ──────────────────────────────────────────────────────
    async def export_midi(self, audio_r2_key: str) -> dict:
        return await self._call_gateway("midi/export", {
            "audio_r2_key": audio_r2_key,
            "generate_piano_roll": True,
        })

    # ── Prompt Builder ────────────────────────────────────────────
    async def build_prompt(
        self,
        genre: str,
        mood: str,
        bpm: Optional[int] = None,
        instruments: list[str] = [],
        reference_artist: str = "",
        is_bgm: bool = False,
        duration_seconds: int = 30,
    ) -> dict:
        return await self._call_gateway("prompt/build", {
            "genre": genre, "mood": mood, "bpm": bpm,
            "instruments": instruments,
            "reference_artist": reference_artist,
            "is_bgm": is_bgm,
            "duration_seconds": duration_seconds,
        })

    # ── ChatGAU ───────────────────────────────────────────────────
    async def chat_support(
        self,
        message: str,
        history: list[dict] = [],
        session_id: str = "",
    ) -> dict:
        return await self._call_gateway("chat/support", {
            "message": message,
            "history": history,
            "use_rag": True,
            "session_id": session_id,
        })

    async def chat_quick(self, query: str) -> dict:
        return await self._call_gateway("chat/quick", {"query": query})

    # ── Analytics ─────────────────────────────────────────────────
    async def get_analytics(self, days: int = 30) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/v1/analytics/summary?days={days}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_analytics(self, user_id: str, days: int = 30) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/v1/analytics/user/{user_id}?days={days}",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def rate_generation(
        self,
        r2_key: str,
        user_id: str,
        rating: int,
        feedback: str = "",
        genre: str = "",
    ) -> dict:
        return await self._call_gateway("analytics/rate", {
            "generation_r2_key": r2_key,
            "user_id": user_id,
            "rating": rating,
            "feedback": feedback,
            "genre": genre,
        })

    # ── Health ────────────────────────────────────────────────────
    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/health",
                headers=self.headers,
            )
            return resp.json()

    async def system_health(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/v1/system/health",
                headers=self.headers,
            )
            return resp.json()


# ── Batch helper ──────────────────────────────────────────────────
class GenAudiusBatch:
    """Construye y ejecuta workflows de múltiples tools."""

    def __init__(self, client: GenAudiusMCPClient):
        self.client = client
        self._steps: list[dict] = []

    def add(self, tool: str, arguments: dict = {}, pass_result_as: str = ""):
        self._steps.append({
            "tool": tool,
            "arguments": arguments,
            "pass_result_as": pass_result_as,
        })
        return self   # chainable

    async def run(self, stop_on_error: bool = True) -> dict:
        async with httpx.AsyncClient(timeout=900) as client:
            resp = await client.post(
                f"{self.client.base_url}/mcp/batch",
                headers=self.client.headers,
                json={"steps": self._steps, "stop_on_error": stop_on_error},
            )
            resp.raise_for_status()
            return resp.json()


# ── Ejemplo de uso ────────────────────────────────────────────────
async def ejemplo():
    mcp = GenAudiusMCPClient(
        base_url="https://api.genaudius.app",
        api_key="tu-api-key",
    )

    # Health check
    health = await mcp.health()
    print(f"MCP Status: {health['status']}")

    # Generación simple
    song = await mcp.generate_song(
        prompt="bachata romántica, guitarra eléctrica, noche caribeña, 128bpm",
        genre="bachata",
        seconds_total=30,
    )
    print(f"Audio URL: {song['audio_url']}")

    # Producción completa
    production = await mcp.full_production(
        prompt="bachata sobre el primer amor",
        genre="bachata",
        title="Primer Amor",
        artist="GenAudius",
        resolution="1920x1080",  # YouTube
    )
    print(f"Video: {production['video']['video_url']}")

    # Batch workflow
    result = await (
        GenAudiusBatch(mcp)
        .add("compose_lyrics", {"prompt": "bachata triste", "genre": "bachata"})
        .add("generate_song",  {"genre": "bachata", "seconds_total": 30}, pass_result_as="prompt")
        .run()
    )
    print(f"Batch: {result['steps_ok']}/{result['steps_total']} pasos OK")


if __name__ == "__main__":
    asyncio.run(ejemplo())
