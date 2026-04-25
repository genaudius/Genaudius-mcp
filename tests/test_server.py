"""
GenAudius MCP — Tests
======================
Sin API key real. Usa mocks de httpx.

Run:
    pip install -e . pytest pytest-asyncio
    pytest tests/ -v
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("GENAUDIUS_API_KEY", "test-key")
os.environ.setdefault("MODAL_AUDIO_URL", "https://test.modal.run")
os.environ.setdefault("MODAL_IMAGE_URL", "https://test-image.modal.run")
os.environ.setdefault("MODAL_VIDEO_URL", "https://test-video.modal.run")
os.environ.setdefault("MODAL_COMPOSER_URL", "https://test-composer.modal.run")
os.environ.setdefault("MODAL_WEBHOOK_TOKEN", "test-token")
os.environ.setdefault("GENAUDIUS_VERSION", "GenAudius_V1")

from genaudius_mcp.server import (
    _gen_audio,
    _gen_lyrics,
    _system_status,
    _list_versions,
)


def make_client(json_return: dict):
    client = AsyncMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = json_return

    async def mock_post(*a, **kw):
        return resp

    async def mock_get(*a, **kw):
        return resp

    client.post = mock_post
    client.get = mock_get
    return client


@pytest.mark.asyncio
async def test_generate_song():
    client = make_client(
        {
            "audio_url": "https://r2.example.com/output.wav",
            "r2_key": "GenAudius_V1/outputs/123_abc.wav",
            "model": "/checkpoints/bachata_smoke_v1/exports/model.safetensors",
            "prompt": "bachata romántica",
            "seconds_total": 30,
            "steps": 100,
        }
    )
    result = await _gen_audio(client, {"prompt": "bachata romántica"}, mode="song")
    assert len(result) == 1
    assert "output.wav" in result[0].text
    assert "GenAudius_V1" in result[0].text


@pytest.mark.asyncio
async def test_generate_bgm_adds_instrumental():
    client = make_client(
        {
            "audio_url": "https://r2.example.com/bgm.wav",
            "r2_key": "GenAudius_V1/outputs/bgm.wav",
            "model": "/checkpoints/bachata_smoke_v1/exports/model.safetensors",
            "prompt": "lofi para estudiar, instrumental, no vocals",
            "seconds_total": 60,
            "steps": 80,
        }
    )
    result = await _gen_audio(client, {"prompt": "lofi para estudiar"}, mode="bgm")
    assert "bgm.wav" in result[0].text


def test_generate_lyrics_returns_prompt():
    result = _gen_lyrics(
        {
            "prompt": "canción de cumpleaños para Jessica",
            "genre": "bachata",
            "language": "Español",
        }
    )
    assert "Jessica" in result[0].text
    assert "bachata" in result[0].text.lower()


@pytest.mark.asyncio
async def test_system_status():
    client = make_client(
        {
            "active_version": "GenAudius_V1",
            "pending_retrain": 3,
            "versions": {
                "GenAudius_V1": {
                    "description": "Bachata baseline",
                    "genres": ["bachata"],
                    "exports": ["model.safetensors"],
                    "ready": True,
                }
            },
        }
    )
    result = await _system_status(client)
    assert "GenAudius_V1" in result[0].text
    assert "✅" in result[0].text


@pytest.mark.asyncio
async def test_list_versions():
    client = make_client(
        {
            "active": "GenAudius_V1",
            "config": {
                "GenAudius_V1": {"description": "Bachata", "genres": ["bachata"]},
                "GenAudius_V2": {"description": "Multi-género", "genres": ["bachata", "pop"]},
            },
        }
    )
    result = await _list_versions(client)
    assert "GenAudius_V1" in result[0].text
    assert "GenAudius_V2" in result[0].text
