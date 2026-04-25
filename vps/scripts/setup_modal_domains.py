"""
GenAudius — Modal Custom Domain Setup
========================================
Configura genaudius.studio como dominio personalizado para todos
los endpoints de Modal.

Uso:
  python vps/scripts/setup_modal_domains.py

Requisito: modal CLI autenticado
  modal token new

Este script:
  1. Despliega todos los módulos en Modal
  2. Configura genaudius.studio como dominio personalizado
  3. Genera las URLs finales para el .env del VPS
"""

import subprocess
import json

STUDIO_DOMAIN = "genaudius.studio"

# Mapeo: nombre del módulo → archivo Modal → subdominio
MODULES = [
    ("audio",    "modal/api.py",                  "audio"),
    ("image",    "modal/image_api.py",             "image"),
    ("video",    "modal/video_api.py",             "video"),
    ("composer", "modal/composer_lyric_api.py",    "composer"),
    ("chatgau",  "modal/chatgau_api.py",           "chatgau"),
    ("stems",    "modal/stems_api.py",             "stems"),
    ("midi",     "modal/midi_api.py",              "midi"),
    ("builder",  "modal/prompt_builder_api.py",    "builder"),
    ("analytics","modal/analytics_api.py",         "analytics"),
    ("gateway",  "modal/gateway.py",               "gateway"),
]


def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def deploy_module(name: str, filepath: str) -> str:
    """Despliega un módulo y devuelve su URL."""
    print(f"  📦 Desplegando {name} ({filepath})...")
    output = run(f"modal deploy {filepath}")
    # Modal imprime la URL al final
    for line in output.split("\n"):
        if "modal.run" in line or STUDIO_DOMAIN in line:
            url = line.strip().split()[-1]
            return url
    return ""


def setup_custom_domain(app_name: str, subdomain: str) -> str:
    """Configura un subdominio de genaudius.studio para un app de Modal."""
    custom_url = f"https://{subdomain}.{STUDIO_DOMAIN}"
    print(f"  🌐 Configurando {custom_url}...")
    # Modal CLI: modal domain create
    run(f"modal domain create {app_name} {subdomain}.{STUDIO_DOMAIN}")
    return custom_url


def main():
    print("🎵 GenAudius — Modal Domain Setup")
    print(f"   Dominio: {STUDIO_DOMAIN}")
    print()

    env_lines = [
        "# ── Modal endpoints (genaudius.studio) ──────────────────────────",
    ]

    module_urls = {}

    for env_key, filepath, subdomain in MODULES:
        app_name = f"genaudius-{env_key}-api"
        if env_key == "gateway":
            app_name = "genaudius-gateway"

        # Desplegar
        modal_url = deploy_module(env_key, filepath)

        # Configurar dominio personalizado
        try:
            custom_url = setup_custom_domain(app_name, env_key)
        except Exception as e:
            print(f"  ⚠️  Dominio personalizado falló para {env_key}: {e}")
            custom_url = modal_url

        env_var = f"MODAL_{env_key.upper()}_URL"
        env_lines.append(f"{env_var}={custom_url}")
        module_urls[env_key] = custom_url
        print(f"  ✅ {env_key}: {custom_url}")

    # Generar el bloque .env actualizado
    print()
    print("=" * 60)
    print("Copia estas líneas en tu vps/.env:")
    print("=" * 60)
    for line in env_lines:
        print(line)
    print()

    # Guardar en archivo
    with open("vps/.modal_urls.env", "w") as f:
        f.write("\n".join(env_lines))
    print("✅ Guardado en vps/.modal_urls.env")

    # Actualizar el gateway con todas las URLs
    print()
    print("📋 Configura el Gateway con las URLs de los módulos:")
    gateway_env = {
        f"MODAL_{k.upper()}_URL": v
        for k, v in module_urls.items()
        if k != "gateway"
    }
    print(f"modal secret put gen-audius-secrets \\")
    for k, v in gateway_env.items():
        print(f"  {k}={v} \\")
    print()


if __name__ == "__main__":
    main()
