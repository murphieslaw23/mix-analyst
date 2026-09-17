"""Deployment contract: installable PWA identity + HTTPS ingress (PWA Task 1)."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DIR = PROJECT_ROOT / "web" / "public"


def _manifest() -> dict:
    return json.loads((PUBLIC_DIR / "manifest.webmanifest").read_text())


def test_manifest_declares_stable_identity():
    manifest = _manifest()
    assert manifest["id"] == "/"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"


def test_manifest_declares_raster_and_maskable_icons():
    manifest = _manifest()
    icons = manifest["icons"]
    raster = [i for i in icons if i.get("type") == "image/png"]
    assert any(i["sizes"] == "192x192" for i in raster)
    assert any(i["sizes"] == "512x512" for i in raster)
    maskable = [
        i
        for i in icons
        if i.get("purpose") == "maskable" and i.get("type") == "image/png"
    ]
    assert len(maskable) >= 1
    for icon in raster + maskable:
        path = PUBLIC_DIR / icon["src"].lstrip("/")
        assert path.is_file(), f"missing manifest asset {icon['src']}"
        assert path.stat().st_size > 1024, f"suspiciously small {icon['src']}"


def test_apple_touch_icon_exists():
    assert (PUBLIC_DIR / "apple-touch-icon.png").is_file()


def test_https_ingress_proxies_operational_paths():
    caddyfile = (PROJECT_ROOT / "infra" / "caddy" / "Caddyfile").read_text()
    assert "reverse_proxy /api/*" in caddyfile
    assert "PUBLIC_ORIGIN" in caddyfile
