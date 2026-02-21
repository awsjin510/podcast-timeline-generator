"""Audio file utilities — validation, temp-file handling, and format support."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from streamlit.runtime.uploaded_file_manager import UploadedFile

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}
MAX_FILE_SIZE_MB = 500


@dataclass
class AudioFile:
    """Wrapper around a validated audio file living on disk."""

    path: Path
    original_name: str
    size_mb: float
    _temp_dir: tempfile.TemporaryDirectory | None = None

    # ------------------------------------------------------------------
    # Context-manager so callers can do:
    #   with save_upload_to_disk(uploaded) as audio_file:
    #       transcribe(audio_file.path)
    # and the temp file is cleaned up automatically.
    # ------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()

    def cleanup(self) -> None:
        """Remove the temporary directory and its contents."""
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None


class AudioValidationError(Exception):
    """Raised when an uploaded file fails validation."""


def validate_extension(filename: str) -> str:
    """Return the lowercased extension or raise on unsupported formats."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise AudioValidationError(
            f"Unsupported file format '{ext}'. Supported: {supported}"
        )
    return ext


def validate_file_size(size_bytes: int) -> float:
    """Return size in MB or raise if the file is too large."""
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise AudioValidationError(
            f"File is {size_mb:.1f} MB — maximum allowed is {MAX_FILE_SIZE_MB} MB."
        )
    return round(size_mb, 2)


def save_upload_to_disk(uploaded_file: UploadedFile) -> AudioFile:
    """Persist a Streamlit ``UploadedFile`` to a temp directory on disk.

    Whisper (and most audio libraries) require a real filesystem path.
    This function:
      1. Validates the file extension and size.
      2. Writes the bytes to a named temp file, preserving the original
         extension so ffmpeg / Whisper can infer the codec.
      3. Returns an ``AudioFile`` whose ``.cleanup()`` (or context-manager
         exit) removes the temp directory.

    Usage::

        audio = save_upload_to_disk(st_file)
        try:
            segments = transcribe_audio(str(audio.path))
        finally:
            audio.cleanup()

        # — or —
        with save_upload_to_disk(st_file) as audio:
            segments = transcribe_audio(str(audio.path))
    """
    filename = uploaded_file.name
    ext = validate_extension(filename)

    raw_bytes = uploaded_file.read()
    size_mb = validate_file_size(len(raw_bytes))

    tmp_dir = tempfile.TemporaryDirectory(prefix="podcast_qf_")
    tmp_path = Path(tmp_dir.name) / f"upload{ext}"
    tmp_path.write_bytes(raw_bytes)

    return AudioFile(
        path=tmp_path,
        original_name=filename,
        size_mb=size_mb,
        _temp_dir=tmp_dir,
    )


def format_timestamp(seconds: float) -> str:
    """Convert seconds → ``HH:MM:SS`` (or ``MM:SS`` if under an hour)."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
