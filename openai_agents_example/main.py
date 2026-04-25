"""
GenAudius + OpenAI Agents SDK
================================
Demo completo usando el motor GenAudius vía MCP.

Setup:
    pip install openai-agents
    modal serve modal/api.py  (en otra terminal)
    GENAUDIUS_API_KEY="tu-key" MODAL_API_URL="https://xxx.modal.run" python main.py
"""

import os
import asyncio

GENAUDIUS_API_KEY = os.environ.get("GENAUDIUS_API_KEY", "")
MODAL_API_URL      = os.environ.get("MODAL_API_URL", "")
MODAL_TOKEN        = os.environ.get("MODAL_WEBHOOK_TOKEN", "")

if not GENAUDIUS_API_KEY:
    raise ValueError("Falta GENAUDIUS_API_KEY")
if not MODAL_API_URL:
    raise ValueError("Falta MODAL_API_URL — ejecuta: modal serve modal/api.py")

try:
    from agents import Agent, Runner
    from agents.mcp import MCPServerStdio
except ImportError:
    raise ImportError("Instala: pip install openai-agents")


async def main():
    print("🎵 GenAudius + OpenAI Agents Demo\n")

    async with MCPServerStdio(
        params={
            "command": "uvx",
            "args": ["genaudius-mcp"],
            "env": {
                "GENAUDIUS_API_KEY": GENAUDIUS_API_KEY,
                "MODAL_API_URL": MODAL_API_URL,
                "MODAL_WEBHOOK_TOKEN": MODAL_TOKEN,
                "GENAUDIUS_VERSION": "GenAudius_V1",
                "TIME_OUT_SECONDS": "300",
            },
        }
    ) as mcp:

        agent = Agent(
            name="GenAudius Music Agent",
            instructions=(
                "Eres el asistente creativo del motor de música GenAudius. "
                "Puedes generar canciones, BGM y letras usando el modelo GAU (Stable Audio Tools finetune). "
                "Siempre confirma los parámetros antes de generar (consume GPU). "
                "Después de generar, presenta el URL de descarga claramente."
            ),
            mcp_servers=[mcp],
        )

        tasks = [
            "¿Cuál es el estado actual del sistema GenAudius y qué versiones están listas?",
            "Genera una bachata romántica de 30 segundos con el prompt 'amor perdido, guitarra acústica, 120bpm'",
            "Genera una BGM lofi de 60 segundos para una sesión de estudio nocturna",
        ]

        for task in tasks:
            print(f"👤 {task}\n")
            result = await Runner.run(starting_agent=agent, input=task)
            print(f"🤖 {result.final_output}\n")
            print("─" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
