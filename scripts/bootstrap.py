#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Download and verify a regional Pi Maps data edition atomically."""
import hashlib, json, logging, os, shutil, subprocess, tempfile, time, urllib.request
from pathlib import Path

DATA = Path(os.environ.get("MAPS_DATA", "/data"))
MANIFEST = Path(os.environ.get("EDITION_MANIFEST", "/app/edition.json"))
MARKER = DATA / ".edition-complete"
CHUNK_SIZE = 1024 * 1024
PROGRESS_INTERVAL = 10.0
LOG = logging.getLogger("pi-maps-bootstrap")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def download_rate_bytes():
    raw = os.environ.get("ZIM_DOWNLOAD_RATE_MIB", "5")
    try: rate = float(raw)
    except ValueError as exc: raise ValueError("ZIM_DOWNLOAD_RATE_MIB must be a positive number") from exc
    if rate <= 0: raise ValueError("ZIM_DOWNLOAD_RATE_MIB must be greater than zero")
    return rate * 1024 * 1024

def lower_priority():
    try: os.nice(10)
    except (AttributeError, OSError): pass
    try: subprocess.run(["ionice", "-c", "3", "-p", str(os.getpid())], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError): pass

def resolve_url(asset):
    url = asset["url"]
    if not url.startswith(("https://", "http://")):
        raise ValueError("release asset URL must be absolute")
    return url

def zim_existing_path(asset):
    rel = Path(asset["path"])
    if not (rel.parts and rel.parts[0] == "zim"): return None
    directory = os.environ.get("WIKI_ZIM_DIR")
    return Path(directory) / os.environ.get("WIKI_ZIM_NAME", rel.name) if directory else None

def matches_expected(path, asset):
    if not path.is_file(): return False
    expected_size = asset.get("size", 0)
    if expected_size and path.stat().st_size != expected_size: return False
    expected = asset.get("sha256", "")
    if not expected or expected.startswith("REPLACE_"): return False
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(CHUNK_SIZE), b""): h.update(block)
    return h.hexdigest() == expected

def asset_available(asset):
    external = zim_existing_path(asset)
    return matches_expected(external, asset) if external is not None else (DATA / asset["path"]).is_file()

def fetch(asset, root, rate):
    rel = Path(asset["path"])
    if rel.is_absolute() or ".." in rel.parts: raise ValueError("unsafe asset path")
    external = zim_existing_path(asset)
    if external is not None and matches_expected(external, asset):
        LOG.info("reusing validated existing ZIM: %s", external); return False
    target = root / rel; target.parent.mkdir(parents=True, exist_ok=True); part = target.with_name(target.name + ".part")
    started = time.monotonic(); last_log = started; downloaded = 0; h = hashlib.sha256()
    try:
        with urllib.request.urlopen(resolve_url(asset), timeout=120) as src, part.open("wb") as dst:
            while True:
                block = src.read(CHUNK_SIZE)
                if not block: break
                dst.write(block); h.update(block); downloaded += len(block)
                target_elapsed = downloaded / rate; elapsed = time.monotonic() - started
                if target_elapsed > elapsed: time.sleep(target_elapsed - elapsed)
                now = time.monotonic()
                if now - last_log >= PROGRESS_INTERVAL:
                    total = asset.get("size", 0); pct = f"{downloaded * 100 / total:.1f}%" if total else "unknown"
                    effective = downloaded / max(now - started, 0.001) / 1024 / 1024
                    LOG.info("downloaded %d/%s bytes (%s), %.2f MiB/s, destination %s", downloaded, total or "?", pct, effective, part); last_log = now
        if asset.get("size", 0) and downloaded != asset["size"]: raise ValueError(f"size mismatch: {rel}")
        expected = asset.get("sha256", "")
        if not expected or expected.startswith("REPLACE_") or h.hexdigest() != expected: raise ValueError(f"checksum mismatch: {rel}")
        os.replace(part, target); LOG.info("download complete: %s (%d bytes)", target, downloaded); return True
    except Exception:
        try: part.unlink()
        except FileNotFoundError: pass
        raise

def main():
    lower_priority(); rate = download_rate_bytes(); manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1: raise ValueError("unsupported edition manifest")
    DATA.mkdir(parents=True, exist_ok=True); include_optional = os.environ.get("INCLUDE_OPTIONAL", "0").lower() in {"1", "true", "yes"}
    selected = [a for a in manifest.get("assets", []) if include_optional or not a.get("optional")]
    if MARKER.exists() and (DATA / "edition.json").exists():
        installed = json.loads((DATA / "edition.json").read_text(encoding="utf-8"))
        if installed.get("edition_id") == manifest.get("edition_id") and installed.get("data_version") == manifest.get("data_version") and all(asset_available(a) for a in selected): return
    minimum = int(manifest.get("minimum_free_bytes", 0))
    if minimum and shutil.disk_usage(DATA).free < minimum: raise OSError("insufficient free space for edition")
    with tempfile.TemporaryDirectory(prefix="pi-maps-edition-", dir=DATA) as td:
        stage = Path(td); downloaded = []
        for asset in selected:
            if fetch(asset, stage, rate): downloaded.append(asset)
        staged_manifest = stage / "edition.json"; staged_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for asset in downloaded:
            src = stage / asset["path"]; dst = DATA / asset["path"]; dst.parent.mkdir(parents=True, exist_ok=True); os.replace(src, dst)
        os.replace(staged_manifest, DATA / "edition.json")
    MARKER.write_text(manifest["edition_id"] + "/" + manifest["data_version"] + "\n", encoding="utf-8")

if __name__ == "__main__": main()
