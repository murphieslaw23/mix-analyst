"""Server-owned filesystem storage for media ingest.

Callers exchange opaque relative object keys only. This keeps path handling in
one place and prevents API input from ever selecting a host filesystem path.
"""

import hashlib
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import BinaryIO


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def derived_object_key(project_id: str, sha256: str, role: str, version: str) -> str:
    """Build the only final-asset key shape accepted by the storage port."""
    if not _SHA256.fullmatch(sha256):
        raise ValueError("sha256 must be a lowercase 64-character hex digest")
    for name, value in (("project_id", project_id), ("role", role), ("version", version)):
        if not _KEY_SEGMENT.fullmatch(value):
            raise ValueError(f"{name} contains an unsafe object-key segment")
    return f"projects/{project_id}/artifacts/{role}/{version}/{sha256}"


class ChunkTooLargeError(ValueError):
    pass


class StorageService:
    def __init__(self, root_dir: str):
        self.root = Path(root_dir).resolve()

    def init_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for_key(self, key: str) -> Path:
        """Resolve a relative object key under storage, rejecting traversal."""
        key_path = PurePosixPath(key)
        if key_path.is_absolute() or not key or any(part in {"", ".", ".."} for part in key_path.parts):
            raise ValueError("object key must be a non-empty relative path")
        target = (self.root / Path(*key_path.parts)).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("object key escapes storage root") from exc
        return target

    def create_quarantine_object(self, key: str) -> None:
        path = self.path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "xb"):
            pass
        os.chmod(path, 0o600)

    def object_exists(self, key: str) -> bool:
        return self.path_for_key(key).is_file()

    def object_size(self, key: str) -> int:
        return self.path_for_key(key).stat().st_size

    def write_limited_chunk(self, key: str, chunk: BinaryIO, max_bytes: int) -> int:
        """Append at most ``max_bytes`` from a seekable/non-seekable stream."""
        if max_bytes <= 0:
            raise ChunkTooLargeError("chunk limit must be positive")
        payload = chunk.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ChunkTooLargeError(f"Chunk exceeds maximum size of {max_bytes} bytes")
        if not payload:
            raise ValueError("Chunk is empty")
        path = self.path_for_key(key)
        if not path.is_file():
            raise FileNotFoundError("quarantine object not found")
        with open(path, "ab") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        return len(payload)

    def compute_sha256(self, key: str) -> str:
        hasher = hashlib.sha256()
        with open(self.path_for_key(key), "rb") as source:
            while payload := source.read(1024 * 1024):
                hasher.update(payload)
        return hasher.hexdigest()

    def object_path(self, key: str) -> Path:
        """Provide a trusted local path to server-side validators only."""
        return self.path_for_key(key)

    def promote(self, quarantine_key: str, final_key: str) -> None:
        """Atomically promote a validated object without overwriting a final key."""
        source = self.path_for_key(quarantine_key)
        destination = self.path_for_key(final_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, destination)
        source.unlink()

    def delete_object(self, key: str) -> None:
        path = self.path_for_key(key)
        if path.is_file():
            path.unlink()

    # Legacy helpers remain for non-upload callers during migration. New upload
    # endpoints use the object-key methods above exclusively.
    def safe_resolve(self, relative_path: str) -> Path:
        return self.path_for_key(relative_path)

    def create_upload_session_file(self, session_id: str) -> Path:
        key = f"quarantine/legacy/{session_id}"
        self.create_quarantine_object(key)
        return self.path_for_key(key)

    def append_chunk(self, temp_path: Path, chunk_bytes: bytes, offset: int) -> int:
        current_size = temp_path.stat().st_size
        if current_size != offset:
            raise ValueError(f"Offset mismatch: expected offset {current_size}, got {offset}")
        with open(temp_path, "ab") as destination:
            destination.write(chunk_bytes)
        return temp_path.stat().st_size

    def finalize_asset(self, temp_path: Path, asset_id: str, original_filename: str) -> tuple[str, Path]:
        final_rel_path = f"assets/audio/{asset_id}{Path(original_filename).suffix.lower() or '.audio'}"
        final_abs_path = self.path_for_key(final_rel_path)
        final_abs_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_path), str(final_abs_path))
        return final_rel_path, final_abs_path

    def delete_file(self, file_path: Path) -> None:
        if file_path.exists():
            file_path.unlink()
