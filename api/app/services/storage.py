import os
import shutil
import hashlib
from pathlib import Path


class StorageService:
    def __init__(self, root_dir: str):
        self.root = Path(root_dir).resolve()
        self.quarantine_dir = self.root / "quarantine"
        self.raw_audio_dir = self.root / "assets" / "audio"
        self.derived_dir = self.root / "assets" / "derived"

    def init_directories(self) -> None:
        """Ensure all required storage directories exist."""
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.raw_audio_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)

    def safe_resolve(self, relative_path: str) -> Path:
        """Resolve a path safely, preventing directory traversal attacks."""
        target = (self.root / relative_path).resolve()
        if not str(target).startswith(str(self.root)):
            raise ValueError(f"Security error: path traversal attempt detected for '{relative_path}'")
        return target

    def create_upload_session_file(self, session_id: str) -> Path:
        """Create a quarantined temporary file for an upload session."""
        self.init_directories()
        temp_file = self.quarantine_dir / f"upload_{session_id}.tmp"
        if temp_file.exists():
            temp_file.unlink()
        temp_file.touch(mode=0o600)
        return temp_file

    def append_chunk(self, temp_path: Path, chunk_bytes: bytes, offset: int) -> int:
        """Append a chunk to the temporary file at the verified offset."""
        if not temp_path.exists():
            raise FileNotFoundError(f"Upload file {temp_path} not found")

        current_size = temp_path.stat().st_size
        if current_size != offset:
            raise ValueError(f"Offset mismatch: expected offset {current_size}, got {offset}")

        with open(temp_path, "ab") as f:
            f.write(chunk_bytes)

        return temp_path.stat().st_size

    def compute_sha256(self, file_path: Path) -> str:
        """Compute the SHA-256 hash of a file using streaming reads."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):  # 1MB buffer
                hasher.update(chunk)
        return hasher.hexdigest()

    def finalize_asset(self, temp_path: Path, asset_id: str, original_filename: str) -> tuple[str, Path]:
        """Atomically move a validated audio file from quarantine to permanent raw audio storage."""
        ext = Path(original_filename).suffix.lower() or ".audio"
        final_filename = f"{asset_id}{ext}"
        final_rel_path = f"assets/audio/{final_filename}"
        final_abs_path = self.raw_audio_dir / final_filename

        shutil.move(str(temp_path), str(final_abs_path))
        return final_rel_path, final_abs_path

    def delete_file(self, file_path: Path) -> None:
        """Delete a file if it exists."""
        if file_path.exists():
            file_path.unlink()
