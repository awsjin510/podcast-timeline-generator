"""Podcast 時間軸產生器 — Flask 本地版"""

import json
import os
import shutil
import uuid

from flask import Flask, Response, render_template, request, jsonify

from utils.audio import save_upload_to_disk, AudioValidationError, format_timestamp
from utils.transcriber import transcribe_audio
from utils.question_detector import extract_chapters, format_youtube_chapters, match_outline_to_timecodes

# ---------------------------------------------------------------------------
# FFmpeg setup
# ---------------------------------------------------------------------------

if shutil.which("ffmpeg") is None:
    try:
        import imageio_ffmpeg
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["PATH"] = os.path.dirname(_ffmpeg_exe) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Load API key from .env or environment
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

# In-memory storage for uploaded files (local use only)
_uploads: dict[str, dict] = {}
# Store transcription segments per file_id so we can reuse them
_segments: dict[str, list] = {}


@app.route("/")
def index():
    has_ffmpeg = shutil.which("ffmpeg") is not None
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return render_template("index.html", has_ffmpeg=has_ffmpeg, has_api_key=has_api_key)


@app.route("/api/upload", methods=["POST"])
def upload():
    """Accept an audio file upload and return a file_id."""
    if "file" not in request.files:
        return jsonify(error="No file provided"), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify(error="Empty filename"), 400

    file_bytes = f.read()
    file_id = uuid.uuid4().hex[:12]

    try:
        audio_file = save_upload_to_disk(file_bytes, f.filename)
    except AudioValidationError as exc:
        return jsonify(error=str(exc)), 400

    _uploads[file_id] = {
        "path": str(audio_file.path),
        "filename": f.filename,
        "size_mb": audio_file.size_mb,
        "audio_file": audio_file,  # keep ref so temp dir isn't cleaned
    }

    return jsonify(file_id=file_id, filename=f.filename, size_mb=audio_file.size_mb)


def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.route("/api/generate/<file_id>")
def generate(file_id: str):
    """SSE stream: transcribe audio + generate chapters."""
    if file_id not in _uploads:
        return jsonify(error="File not found. Please re-upload."), 404

    whisper_model = request.args.get("whisper_model", "base")
    language = request.args.get("language", "") or None
    llm_model = request.args.get("llm_model", "claude-sonnet-4-20250514")

    upload_info = _uploads[file_id]

    def stream():
        # Step 1: Transcribe
        yield _sse_event("progress", {"pct": 5, "msg": "載入 Whisper 模型中..."})

        try:
            if file_id in _segments:
                segments = _segments[file_id]
                yield _sse_event("progress", {"pct": 50, "msg": f"已有逐字稿 — 共 {len(segments)} 個段落。"})
            else:
                yield _sse_event("progress", {"pct": 10, "msg": "轉錄中（使用 faster-whisper，較長音檔可能需30秒至幾分鐘）..."})
                segments = transcribe_audio(
                    upload_info["path"],
                    model_name=whisper_model,
                    language=language,
                )
                _segments[file_id] = segments
                yield _sse_event("progress", {"pct": 50, "msg": f"轉錄完成 — 共 {len(segments)} 個段落。"})
        except Exception as exc:
            yield _sse_event("error", {"msg": f"轉錄失敗：{exc}"})
            return

        # Step 2: AI analysis
        yield _sse_event("progress", {"pct": 55, "msg": "Claude 分析節目結構中..."})

        def on_progress(pct, msg):
            pass  # Can't yield from nested callback; progress updates above cover it

        try:
            chapters = extract_chapters(
                segments,
                model=llm_model,
            )
        except EnvironmentError as exc:
            yield _sse_event("error", {"msg": str(exc)})
            return
        except Exception as exc:
            yield _sse_event("error", {"msg": f"分析失敗：{exc}"})
            return

        yield _sse_event("progress", {"pct": 100, "msg": f"完成 — 產出 {len(chapters)} 個章節。"})

        # Build result
        duration = segments[-1].end_time if segments else 0
        yt_text = format_youtube_chapters(chapters)

        yield _sse_event("result", {
            "chapters": chapters,
            "chapter_count": len(chapters),
            "duration": format_timestamp(duration),
            "youtube_text": yt_text,
        })

    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/match/<file_id>")
def match_outline(file_id: str):
    """SSE stream: transcribe audio + match outline items."""
    if file_id not in _uploads:
        return jsonify(error="File not found. Please re-upload."), 404

    whisper_model = request.args.get("whisper_model", "base")
    language = request.args.get("language", "") or None
    llm_model = request.args.get("llm_model", "claude-sonnet-4-20250514")
    outline = request.args.get("outline", "")

    if not outline.strip():
        return jsonify(error="請提供訪綱內容。"), 400

    upload_info = _uploads[file_id]

    def stream():
        # Step 1: Transcribe
        yield _sse_event("progress", {"pct": 5, "msg": "載入 Whisper 模型中..."})

        try:
            if file_id in _segments:
                segments = _segments[file_id]
                yield _sse_event("progress", {"pct": 50, "msg": f"已有逐字稿，跳過轉錄。"})
            else:
                yield _sse_event("progress", {"pct": 10, "msg": "轉錄中（使用 faster-whisper，較長音檔可能需30秒至幾分鐘）..."})
                segments = transcribe_audio(
                    upload_info["path"],
                    model_name=whisper_model,
                    language=language,
                )
                _segments[file_id] = segments
                yield _sse_event("progress", {"pct": 50, "msg": f"轉錄完成 — 共 {len(segments)} 個段落。"})
        except Exception as exc:
            yield _sse_event("error", {"msg": f"轉錄失敗：{exc}"})
            return

        # Step 2: Match outline
        yield _sse_event("progress", {"pct": 55, "msg": "Claude 比對訪綱與逐字稿中..."})

        try:
            results = match_outline_to_timecodes(
                segments,
                outline,
                model=llm_model,
            )
        except EnvironmentError as exc:
            yield _sse_event("error", {"msg": str(exc)})
            return
        except Exception as exc:
            yield _sse_event("error", {"msg": f"比對失敗：{exc}"})
            return

        yield _sse_event("progress", {"pct": 100, "msg": f"完成 — 比對了 {len(results)} 個訪綱題目。"})

        # Build YouTube text from matched items
        yt_lines = [f'{r["timestamp"]} {r["title"]}' for r in results if not r.get("not_found")]
        yt_text = "\n".join(yt_lines)

        yield _sse_event("result", {
            "items": results,
            "youtube_text": yt_text,
        })

    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Podcast 時間軸產生器")
    print(f"  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
