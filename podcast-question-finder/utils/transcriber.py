"""Transcription module — wraps OpenAI Whisper to produce timestamped segments."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from typing import Optional

import whisper

from utils.audio import format_timestamp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TranscriptSegment:
    """A single timed slice of the transcript."""

    start_time: float       # seconds
    end_time: float         # seconds
    text: str               # spoken content (stripped)

    # Convenience properties -------------------------------------------------
    @property
    def start_display(self) -> str:
        return format_timestamp(self.start_time)

    @property
    def end_display(self) -> str:
        return format_timestamp(self.end_time)

    @property
    def duration(self) -> float:
        return round(self.end_time - self.start_time, 2)

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "start_display": self.start_display,
            "end_display": self.end_display,
            "duration": self.duration,
        }

    def __str__(self) -> str:
        return f"[{self.start_display} → {self.end_display}] {self.text}"


# ---------------------------------------------------------------------------
# Model cache — avoids reloading on every Streamlit rerun
# ---------------------------------------------------------------------------

_model_cache: dict[str, whisper.Whisper] = {}


def _load_model(model_name: str) -> whisper.Whisper:
    """Load a Whisper model, caching it for the lifetime of the process."""
    if model_name not in _model_cache:
        logger.info("Loading Whisper model '%s' …", model_name)
        _model_cache[model_name] = whisper.load_model(model_name)
        logger.info("Model '%s' loaded.", model_name)
    return _model_cache[model_name]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio(
    file_path: str,
    *,
    model_name: Optional[str] = None,
    language: Optional[str] = None,
    verbose: bool = False,
) -> list[TranscriptSegment]:
    """Transcribe an audio file and return timestamped segments.

    Parameters
    ----------
    file_path:
        Path to the audio file on disk (mp3, wav, m4a, etc.).
    model_name:
        Whisper model size.  Falls back to the ``WHISPER_MODEL`` env var,
        then defaults to ``"base"``.
    language:
        Optional ISO-639-1 code (e.g. ``"en"``).  When ``None`` Whisper
        auto-detects the language from the first 30 s of audio.
    verbose:
        If ``True``, Whisper prints progress to stdout while decoding.

    Returns
    -------
    list[TranscriptSegment]
        Chronologically ordered segments with start/end times in seconds.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    RuntimeError
        If Whisper fails to decode the audio.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    model_name = model_name or os.getenv("WHISPER_MODEL", "base")
    model = _load_model(model_name)

    logger.info("Transcribing '%s' with model '%s' …", file_path, model_name)

    # ---- Run Whisper --------------------------------------------------------
    # `fp16=False` avoids a warning on CPU-only machines.
    decode_options: dict = {"fp16": False, "verbose": verbose}
    if language:
        decode_options["language"] = language

    try:
        result = model.transcribe(file_path, **decode_options)
    except Exception as exc:
        raise RuntimeError(f"Whisper transcription failed: {exc}") from exc

    # ---- Convert raw segments → dataclass ----------------------------------
    segments: list[TranscriptSegment] = []
    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start_time=round(seg["start"], 2),
                end_time=round(seg["end"], 2),
                text=text,
            )
        )

    logger.info(
        "Transcription complete — %d segments, detected language: %s",
        len(segments),
        result.get("language", "unknown"),
    )
    return segments


def segments_to_plain_text(segments: list[TranscriptSegment]) -> str:
    """Join all segment texts into a single plain-text transcript."""
    return " ".join(seg.text for seg in segments)


def segments_to_timestamped_text(segments: list[TranscriptSegment]) -> str:
    """Return a human-readable, timestamped transcript block.

    Example output::

        [00:00 → 00:05] Welcome to the show.
        [00:05 → 00:12] Today we're talking about AI.
    """
    return "\n".join(str(seg) for seg in segments)
