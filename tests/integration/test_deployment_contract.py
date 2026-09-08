"""Regression contracts for the HTTPS-only PWA deployment boundary."""

from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAFE_TEST_SECRET = "test-only-compose-secret-with-at-least-32-bytes"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_size(path: Path) -> tuple[int, int]:
    """Read a PNG IHDR without accepting a renamed non-PNG asset."""
    payload = path.read_bytes()
    assert payload.startswith(PNG_SIGNATURE), f"{path} is not a PNG"
    assert payload[12:16] == b"IHDR", f"{path} has no PNG IHDR"
    return struct.unpack(">II", payload[16:24])


def _compose_config() -> dict:
    environment = os.environ | {
        "AUTH_JWT_SECRET": SAFE_TEST_SECRET,
        "PUBLIC_ORIGIN": "mix.example.test",
    }
    rendered = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config", "--format", "json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    return json.loads(rendered.stdout)


def test_manifest_declares_stable_identity_raster_icons_and_safe_shortcuts():
    manifest = json.loads(
        (REPOSITORY_ROOT / "web/public/manifest.webmanifest").read_text()
    )

    assert manifest["id"] == "/"
    assert manifest["start_url"] == "/process"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"

    icons = {icon["src"]: icon for icon in manifest["icons"]}
    for asset, expected_size in (
        ("/icon-192.png", (192, 192)),
        ("/icon-512.png", (512, 512)),
        ("/icon-maskable-512.png", (512, 512)),
    ):
        icon = icons[asset]
        assert icon["type"] == "image/png"
        assert (
            _png_size(REPOSITORY_ROOT / "web/public" / asset.removeprefix("/"))
            == expected_size
        )

    assert icons["/icon-maskable-512.png"]["purpose"] == "maskable"
    assert icons["/icon-192.png"]["purpose"] == "any"
    assert icons["/icon-512.png"]["purpose"] == "any"

    screenshot = manifest["screenshots"][0]
    assert screenshot["src"] == "/pwa-screenshot-process.png"
    assert _png_size(REPOSITORY_ROOT / "web/public/pwa-screenshot-process.png") == (
        1280,
        720,
    )
    assert _png_size(REPOSITORY_ROOT / "web/public/apple-touch-icon.png") == (180, 180)

    shortcuts = {shortcut["url"] for shortcut in manifest["shortcuts"]}
    assert shortcuts == {"/process", "/jobs"}


def test_https_ingress_is_the_only_public_application_entrypoint():
    config = _compose_config()
    services = config["services"]

    assert "ports" not in services["api"]
    assert "ports" not in services["web"]
    assert {port["published"] for port in services["caddy"]["ports"]} == {"80", "443"}
    assert services["caddy"]["environment"]["PUBLIC_ORIGIN"] == "mix.example.test"
    assert (
        services["api"]["environment"]["CORS_ORIGINS"] == '["https://mix.example.test"]'
    )

    caddyfile = (REPOSITORY_ROOT / "infra/caddy/Caddyfile").read_text()
    assert "{$PUBLIC_ORIGIN:localhost}" in caddyfile
    assert "@api path /api/*" in caddyfile
    assert "reverse_proxy @api api:8000" in caddyfile
    assert "reverse_proxy web:80" in caddyfile
    assert "Strict-Transport-Security" in caddyfile
    assert "path /docs" not in caddyfile

    nginx = (REPOSITORY_ROOT / "web/nginx.conf").read_text()
    assert "location ^~ /api/" in nginx
    assert "proxy_pass http://api:8000" not in nginx


def test_html_uses_the_raster_apple_touch_asset_and_docs_refuse_http_install_claims():
    index = (REPOSITORY_ROOT / "web/index.html").read_text()
    readme = (REPOSITORY_ROOT / "README.md").read_text()

    assert 'href="/apple-touch-icon.png"' in index
    assert "not** release-installable from a plain HTTP LAN" in readme
    assert "Local development (not an install acceptance path)" in readme
    assert "/api/v1/docs" not in readme


def test_vercel_serves_the_generated_worker_without_a_spa_rewrite():
    vercel = (REPOSITORY_ROOT / "web/vercel.json").read_text()

    assert "service-worker\\\\.js" in vercel
    assert '"source": "/service-worker.js"' in vercel
    assert '"source": "/sw.js"' not in vercel
